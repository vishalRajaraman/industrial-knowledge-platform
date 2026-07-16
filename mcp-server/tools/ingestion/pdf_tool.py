"""
Ingestion tools — PDF documents.
ingest_pdf: extract text + tables → chunk → embed → store in Qdrant + Neo4j + S3.
"""
import logging
import os
import uuid
import requests
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from core import embeddings, neo4j_client, object_store
from core import pinecone_client as vc
from tools.knowledge.ner_tool import _extract_entities_impl
from tools.knowledge.chunker_tool import _chunk_text

logger = logging.getLogger("ikp.ingest.pdf")


async def ingest_pdf(
    file_path: str,
    doc_type: str = "general",
    upload_to_s3: bool = True,
) -> dict:
    """
    Ingest a PDF document into the knowledge platform.
    Extracts text and tables, chunks, embeds (1536-dim), stores in
    Qdrant Cloud (vector DB), Neo4j AuraDB (knowledge graph), and AWS S3.

    Args:
        file_path: Absolute path to the PDF file (local path or S3 key).
        doc_type: One of: maintenance, procedure, inspection, incident,
                  regulation, manual, drawing, general.
        upload_to_s3: If True, upload original file to S3 raw asset bucket.

    Returns:
        doc_id, chunk_count, entity_count, s3_url, kg_nodes_created.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {"error": "PyMuPDF not installed. pip install pymupdf"}

    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    doc_id = str(uuid.uuid4())
    path = Path(file_path)

    # ── 1. Extract text ──────────────────────────────────────────────────
    pdf = fitz.open(file_path)
    pages_text = []
    for page_num, page in enumerate(pdf):
        text = page.get_text("text")
        if text.strip():
            pages_text.append({"page": page_num + 1, "text": text})
            
    full_text = "\n\n".join(p["text"] for p in pages_text)
    extraction_method = "PyMuPDF (Digital Text)"

    # Check if scanned (fewer than 50 chars per page on average)
    num_pages = len(pdf)
    if len(full_text.strip()) < 50 * num_pages:
        extraction_method = "OCR.space API (Scanned Image)"
        logger.info(f"PDF appears to be scanned (< 50 chars/page). Falling back to OCR for {num_pages} pages.")
        pages_text = []
        for page_num, page in enumerate(pdf):
            logger.info(f"OCRing page {page_num + 1}/{num_pages}...")
            pix = page.get_pixmap()
            img_bytes = pix.tobytes("jpeg")
            
            # Send to OCR.space API
            api_key = "K88154536588957"
            url = "https://api.ocr.space/parse/image"
            payload = {"apikey": api_key, "language": "eng", "OCREngine": "3"}
            files = {"file": (f"page_{page_num+1}.jpg", img_bytes, "image/jpeg")}
            
            try:
                response = requests.post(url, data=payload, files=files)
                response.raise_for_status()
                result = response.json()
                
                if result.get("IsErroredOnProcessing"):
                    error_msg = result.get("ErrorMessage", ["Unknown OCR error"])[0]
                    logger.error(f"OCR Error on page {page_num+1}: {error_msg}")
                    continue
                
                parsed_results = result.get("ParsedResults", [])
                if parsed_results:
                    page_text = parsed_results[0].get("ParsedText", "")
                    if page_text.strip():
                        pages_text.append({"page": page_num + 1, "text": page_text})
            except Exception as e:
                logger.error(f"Failed to OCR page {page_num+1}: {e}")
                
        full_text = "\n\n".join(p["text"] for p in pages_text)

    pdf.close()

    if not full_text.strip():
        return {"error": "No text extracted even after OCR fallback."}

    # Print extraction method and text preview to terminal for testing
    text_preview = full_text[:500].replace('\n', ' ') + ("..." if len(full_text) > 500 else "")
    logger.info("==================================================")
    logger.info(f"EXTRACTION METHOD USED: {extraction_method}")
    logger.info(f"TEXT PREVIEW:\n{text_preview}")
    logger.info("==================================================")

    # ── 2. Upload to S3 ──────────────────────────────────────────────────
    s3_url = None
    if upload_to_s3:
        try:
            s3_url = await object_store.upload_file(
                file_path, doc_id, metadata={"doc_type": doc_type, "filename": path.name}
            )
        except Exception as e:
            logger.warning("S3 upload failed (non-fatal): %s", e)
            s3_url = f"local://{file_path}"

    # ── 3. Extract entities ───────────────────────────────────────────────
    entities = await _extract_entities_impl(full_text[:50000], doc_id)  # limit for NER

    # ── 4. Chunk document ─────────────────────────────────────────────────
    chunks = _chunk_text(full_text, doc_id, doc_type, max_size=512, overlap=64)

    # ── 5. Generate embeddings (1536-dim) ─────────────────────────────────
    chunk_texts = [c["text"] for c in chunks]
    vectors = embeddings.embed_documents(chunk_texts)

    enriched_chunks = []
    for chunk, vec in zip(chunks, vectors):
        enriched_chunks.append({
            **chunk,
            "embedding": vec,
            "doc_type": doc_type,
            "equipment_tags": [e["text"] for e in entities.get("equipment_tags", [])],
            "source_path": s3_url or file_path,
            "filename": path.name,
        })

    # ── 6. Upsert into Qdrant Cloud ───────────────────────────────────────
    upsert_result = await vc.upsert_chunks(enriched_chunks)

    # ── 7. Create Document node in Neo4j AuraDB ───────────────────────────
    kg_nodes = 1
    await neo4j_client.upsert_node(
        node_id=doc_id,
        labels=["Document"],
        properties={
            "title": path.stem,
            "doc_type": doc_type,
            "filename": path.name,
            "source_path": s3_url or file_path,
            "page_count": len(pages_text),
            "chunk_count": len(chunks),
        },
    )

    # Create Equipment nodes and link to document
    for eq in entities.get("equipment_tags", []):
        tag = eq["text"].upper()
        await neo4j_client.upsert_node(
            node_id=tag, labels=["Equipment"], properties={"tag": tag, "status": "unknown"}
        )
        await neo4j_client.upsert_edge(tag, doc_id, "MENTIONED_IN")
        kg_nodes += 2

    return {
        "doc_id": doc_id,
        "filename": path.name,
        "doc_type": doc_type,
        "pages": len(pages_text),
        "chunk_count": len(chunks),
        "vectors_upserted": upsert_result.get("upserted", 0),
        "entity_count": sum(len(v) for v in entities.values() if isinstance(v, list)),
        "kg_nodes_created": kg_nodes,
        "s3_url": s3_url,
    }

def register(mcp: FastMCP):
    mcp.tool()(ingest_pdf)
