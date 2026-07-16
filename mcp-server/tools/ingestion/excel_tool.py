"""
Excel / CSV ingestion tool.
Parses spreadsheets, converts rows to text chunks, embeds and stores.
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from core import embeddings, neo4j_client, object_store
from core import pinecone_client as vc
from tools.knowledge.ner_tool import _extract_entities_impl
from tools.knowledge.chunker_tool import _chunk_text

logger = logging.getLogger("ikp.ingest.excel")


def register(mcp: FastMCP):

    @mcp.tool()
    async def ingest_excel(
        file_path: str,
        sheet_name: str | None = None,
        doc_type: str = "maintenance",
        upload_to_s3: bool = True,
    ) -> dict:
        """
        Ingest an Excel (.xlsx, .xls) or CSV file.
        Each row is converted to a natural-language text chunk, embedded (1536-dim),
        and stored in Qdrant Cloud. Column headers are used as context prefixes.

        Args:
            file_path: Absolute path to the Excel or CSV file.
            sheet_name: Specific sheet to parse (default: all sheets).
            doc_type: Document type tag for metadata.
            upload_to_s3: Upload original file to S3 raw asset store.

        Returns:
            doc_id, rows_processed, chunk_count, vectors_upserted.
        """
        try:
            import pandas as pd
        except ImportError:
            return {"error": "pandas not installed. pip install pandas openpyxl"}

        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        path = Path(file_path)
        doc_id = str(uuid.uuid4())

        # ── Read file ────────────────────────────────────────────────────────
        try:
            if path.suffix.lower() in (".xlsx", ".xls"):
                dfs = pd.read_excel(file_path, sheet_name=sheet_name or None)
                if isinstance(dfs, pd.DataFrame):
                    dfs = {"Sheet1": dfs}
            else:  # CSV
                dfs = {"data": pd.read_csv(file_path)}
        except Exception as e:
            return {"error": f"Failed to parse file: {e}"}

        # ── Convert rows to text ──────────────────────────────────────────────
        all_texts = []
        total_rows = 0
        for sheet, df in dfs.items():
            df = df.fillna("").astype(str)
            for idx, row in df.iterrows():
                row_text = f"[{sheet} | Row {idx + 1}] " + " | ".join(
                    f"{col}: {val}" for col, val in row.items() if val.strip()
                )
                all_texts.append(row_text)
                total_rows += 1

        combined_text = "\n".join(all_texts)

        # ── Extract entities from combined text ───────────────────────────────
        entities = await _extract_entities_impl(combined_text[:40000], doc_id)

        # ── Chunk (by row groups) ─────────────────────────────────────────────
        chunks = _chunk_text(combined_text, doc_id, doc_type, max_size=512, overlap=32)

        # ── Embed & upsert ────────────────────────────────────────────────────
        chunk_texts = [c["text"] for c in chunks]
        vectors = embeddings.embed_documents(chunk_texts)
        enriched_chunks = [
            {**c, "embedding": v, "doc_type": doc_type,
             "equipment_tags": [e["text"] for e in entities.get("equipment_tags", [])],
             "filename": path.name}
            for c, v in zip(chunks, vectors)
        ]
        upsert_result = await vc.upsert_chunks(enriched_chunks)

        # ── S3 upload ─────────────────────────────────────────────────────────
        s3_url = None
        if upload_to_s3:
            try:
                s3_url = await object_store.upload_file(file_path, doc_id, {"doc_type": doc_type})
            except Exception as e:
                logger.warning("S3 upload failed: %s", e)

        # ── Neo4j document node ───────────────────────────────────────────────
        await neo4j_client.upsert_node(
            doc_id, ["Document"],
            {"title": path.stem, "doc_type": doc_type, "filename": path.name,
             "row_count": total_rows, "chunk_count": len(chunks)}
        )
        for eq in entities.get("equipment_tags", []):
            tag = eq["text"].upper()
            await neo4j_client.upsert_node(tag, ["Equipment"], {"tag": tag})
            await neo4j_client.upsert_edge(tag, doc_id, "MENTIONED_IN")

        return {
            "doc_id": doc_id,
            "filename": path.name,
            "doc_type": doc_type,
            "sheets_parsed": list(dfs.keys()),
            "rows_processed": total_rows,
            "chunk_count": len(chunks),
            "vectors_upserted": upsert_result.get("upserted", 0),
            "s3_url": s3_url,
        }
