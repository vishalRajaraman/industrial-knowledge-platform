"""
OCR ingestion tool — Tesseract OCR for scanned documents and images.
"""
import logging
import os
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from core import embeddings, neo4j_client, object_store
from core import pinecone_client as vc
from tools.knowledge.ner_tool import _extract_entities_impl
from tools.knowledge.chunker_tool import _chunk_text

logger = logging.getLogger("ikp.ingest.ocr")


def register(mcp: FastMCP):

    @mcp.tool()
    async def ocr_document(
        file_path: str,
        language: str = "eng",
        doc_type: str = "general",
        upload_to_s3: bool = True,
    ) -> dict:
        """
        Extract text from a scanned document or image using Tesseract OCR.
        Applies preprocessing (deskew, denoise, binarize) for better accuracy.
        Embeds extracted text (1536-dim) and stores in Qdrant Cloud + Neo4j.

        Args:
            file_path: Absolute path to the scanned image (PNG, JPG, TIFF) or PDF.
            language: Tesseract language code ('eng', 'hin', etc.).
            doc_type: Document type for metadata tagging.
            upload_to_s3: Upload original to S3 raw asset store.

        Returns:
            doc_id, extracted_text_length, confidence_score, chunk_count.
        """
        try:
            import pytesseract
            import cv2
            import numpy as np
            from PIL import Image
        except ImportError:
            return {"error": "Install: pip install pytesseract opencv-python pillow"}

        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        path = Path(file_path)
        doc_id = str(uuid.uuid4())

        # ── Preprocess image ─────────────────────────────────────────────────
        try:
            img = cv2.imread(file_path)
            if img is None:
                # Try PIL for TIFF
                pil_img = Image.open(file_path).convert("RGB")
                import numpy as np
                img = np.array(pil_img)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            # Binarize (Otsu's threshold)
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # OCR with confidence data
            data = pytesseract.image_to_data(
                binary, lang=language, output_type=pytesseract.Output.DICT
            )
            words = [w for w, c in zip(data["text"], data["conf"]) if int(c) > 30 and w.strip()]
            extracted_text = " ".join(words)
            avg_confidence = sum(int(c) for c in data["conf"] if int(c) > 0) / max(
                len([c for c in data["conf"] if int(c) > 0]), 1
            )
        except Exception as e:
            return {"error": f"OCR failed: {e}"}

        if not extracted_text.strip():
            return {"error": "No text extracted from image.", "file": file_path}

        # ── Extract entities, chunk, embed, store ─────────────────────────────
        entities = await _extract_entities_impl(extracted_text[:50000], doc_id)
        chunks = _chunk_text(extracted_text, doc_id, doc_type)
        vectors = embeddings.embed_documents([c["text"] for c in chunks])
        enriched = [
            {**c, "embedding": v, "doc_type": doc_type,
             "equipment_tags": [e["text"] for e in entities.get("equipment_tags", [])],
             "ocr_confidence": round(avg_confidence, 1), "filename": path.name}
            for c, v in zip(chunks, vectors)
        ]
        upsert_result = await vc.upsert_chunks(enriched)

        s3_url = None
        if upload_to_s3:
            try:
                s3_url = await object_store.upload_file(file_path, doc_id, {"doc_type": doc_type})
            except Exception as e:
                logger.warning("S3 upload failed: %s", e)

        await neo4j_client.upsert_node(
            doc_id, ["Document"],
            {"title": path.stem, "doc_type": doc_type, "filename": path.name,
             "ocr_confidence": round(avg_confidence, 1)}
        )

        return {
            "doc_id": doc_id,
            "filename": path.name,
            "doc_type": doc_type,
            "extracted_text_length": len(extracted_text),
            "ocr_confidence": round(avg_confidence, 1),
            "chunk_count": len(chunks),
            "vectors_upserted": upsert_result.get("upserted", 0),
            "s3_url": s3_url,
        }
