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

def _is_data_sheet(sheet_name: str) -> bool:
    """Determine if a sheet is a data sheet or a configuration/reference sheet."""
    skip_keywords = ['config', 'ref', 'dropdown', 'list', 'setting', 'meta', 'lookup', 'validation']
    sheet_lower = str(sheet_name).lower()
    return not any(kw in sheet_lower for kw in skip_keywords)

def _extract_table_metadata(df) -> dict:
    """Extract metadata (column names, types, value ranges) from a dataframe."""
    import pandas as pd
    metadata = {}
    for col in df.columns:
        col_type = str(df[col].dtype)
        col_meta = {"type": col_type}
        try:
            if pd.api.types.is_numeric_dtype(df[col]):
                col_meta["min"] = float(df[col].min()) if not pd.isna(df[col].min()) else None
                col_meta["max"] = float(df[col].max()) if not pd.isna(df[col].max()) else None
            else:
                unique_count = df[col].nunique()
                col_meta["unique_values_count"] = int(unique_count)
                if unique_count < 10:
                    # Provide some sample categorical values
                    col_meta["sample_values"] = df[col].dropna().astype(str).unique()[:5].tolist()
        except Exception as e:
            logger.debug(f"Failed to extract metadata for column {col}: {e}")
            pass
        metadata[str(col)] = col_meta
    return metadata

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
            sheet_name: Specific sheet to parse (default: all data sheets).
            doc_type: Document type tag for metadata.
            upload_to_s3: Upload original file to S3 raw asset store.

        Returns:
            doc_id, rows_processed, chunk_count, vectors_upserted, sheet_metadata.
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
        dfs = {}
        try:
            if path.suffix.lower() in (".xlsx", ".xls"):
                # By default read all sheets
                excel_dfs = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
                if isinstance(excel_dfs, pd.DataFrame):
                    # Single sheet returned
                    dfs = {sheet_name or "Sheet1": excel_dfs}
                else:
                    # Filter sheets based on name if all sheets were loaded
                    dfs = {name: df for name, df in excel_dfs.items() if _is_data_sheet(name)}
            else:  # CSV
                dfs = {"data": pd.read_csv(file_path, header=None)}
        except Exception as e:
            return {"error": f"Failed to parse file: {e}"}

        # ── Process DataFrames & extract metadata ─────────────────────────────
        sheet_metadata = {}
        processed_dfs = {}
        for sheet, df in dfs.items():
            if df.empty:
                continue
            
            # Assume first row is header, drop fully empty columns
            df = df.dropna(how='all', axis=1)
            
            if df.empty or len(df) < 2:
                continue
                
            # Set first row as columns
            raw_columns = df.iloc[0].astype(str).tolist()
            
            # Deduplicate column names
            seen = {}
            deduped_columns = []
            for col in raw_columns:
                col = col.strip()
                if col in seen:
                    seen[col] += 1
                    deduped_columns.append(f"{col}_{seen[col]}")
                else:
                    seen[col] = 0
                    deduped_columns.append(col)
                    
            df.columns = deduped_columns
            df = df[1:].reset_index(drop=True)
            
            sheet_metadata[sheet] = _extract_table_metadata(df)
            processed_dfs[sheet] = df

        # ── Convert rows to text ──────────────────────────────────────────────
        all_texts = []
        total_rows = 0
        for sheet, df in processed_dfs.items():
            for idx, row in df.iterrows():
                row_parts = []
                for col, val in row.items():
                    val_str = str(val).strip()
                    if val_str and val_str.lower() not in ('nan', 'none', 'nat'):
                        row_parts.append(f"{col}={val_str}")
                
                if row_parts:
                    # Row-to-text serialization format
                    row_text = f"Sheet: {sheet} | Row: {idx + 1} | " + ", ".join(row_parts)
                    all_texts.append(row_text)
                    total_rows += 1

        if not all_texts:
            return {"error": "No data rows found in the file."}

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
             "process_parameters": [e["text"] for e in entities.get("process_parameters", [])],
             "regulatory_references": [e["text"] for e in entities.get("regulatory_references", [])],
             "failure_modes": [e["text"] for e in entities.get("failure_modes", [])],
             "chemicals": [e["text"] for e in entities.get("chemicals", [])],
             "persons": [e["text"] for e in entities.get("persons", [])],
             "dates": [e["text"] for e in entities.get("dates", [])],
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
             "row_count": total_rows, "chunk_count": len(chunks), "sheets": list(processed_dfs.keys()),
             "equipment_tags": [e["text"] for e in entities.get("equipment_tags", [])],
             "process_parameters": [e["text"] for e in entities.get("process_parameters", [])],
             "regulatory_references": [e["text"] for e in entities.get("regulatory_references", [])],
             "failure_modes": [e["text"] for e in entities.get("failure_modes", [])],
             "chemicals": [e["text"] for e in entities.get("chemicals", [])]}
        )
        for eq in entities.get("equipment_tags", []):
            tag = eq["text"].upper()
            await neo4j_client.upsert_node(tag, ["Equipment"], {"tag": tag})
            await neo4j_client.upsert_edge(tag, doc_id, "MENTIONED_IN")

        return {
            "doc_id": doc_id,
            "filename": path.name,
            "doc_type": doc_type,
            "sheets_parsed": list(processed_dfs.keys()),
            "rows_processed": total_rows,
            "chunk_count": len(chunks),
            "vectors_upserted": upsert_result.get("upserted", 0),
            "s3_url": s3_url,
            "metadata": sheet_metadata
        }
