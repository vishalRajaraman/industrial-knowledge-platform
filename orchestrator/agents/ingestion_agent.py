"""
Ingestion Agent — LangGraph workflow for processing new documents.
Pipeline: Parse -> Extract Entities -> Chunk -> Embed -> Store (Vector + Graph + Raw)
"""
import logging
from typing import Any

from mcp_client import MCPClientManager

logger = logging.getLogger("ingestion-agent")


class IngestionAgent:
    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager

    async def run(self, file_path: str, filename: str, doc_id: str, doc_type: str, plant_id: str) -> dict[str, Any]:
        """Run the full ingestion pipeline."""
        logger.info(f"Starting ingestion pipeline for {filename} (ID: {doc_id})")
        results = {}

        # 1. Parse Document (Server 1)
        suffix = filename.lower().split(".")[-1]
        if suffix in ["pdf"]:
            # Check if scanned or digital
            parse_res = await self.mcp.call_tool("ingestion", "pdf_extract_text", {"file_path": file_path})
            if "error" in parse_res or len(parse_res.get("full_text", "")) < 50:
                # Fallback to OCR if empty or error
                logger.info(f"PDF {filename} seems scanned. Falling back to OCR.")
                parse_res = await self.mcp.call_tool("ingestion", "ocr_extract_text", {"file_path": file_path})
        elif suffix in ["jpg", "jpeg", "png", "tiff"]:
            parse_res = await self.mcp.call_tool("ingestion", "ocr_extract_text", {"file_path": file_path})
        elif suffix in ["xlsx", "csv"]:
            parse_res = await self.mcp.call_tool("ingestion", "excel_parse", {"file_path": file_path})
        elif suffix in ["eml", "msg"]:
            parse_res = await self.mcp.call_tool("ingestion", "email_parse", {"file_path": file_path})
        else:
            return {"error": f"Unsupported file type: {suffix}"}

        if "error" in parse_res:
            return {"status": "failed", "step": "parsing", "error": parse_res["error"]}

        full_text = parse_res.get("full_text", "")
        if not full_text and "sheets" in parse_res:
            # Simple text rendering for excel
            full_text = str(parse_res["sheets"])

        results["parsing"] = {"method": parse_res.get("engine", "pdf"), "length": len(full_text)}

        # 2. Extract Entities & Triplet generation (Server 2)
        ner_res = await self.mcp.call_tool("knowledge", "extract_entities", {"text": full_text, "doc_id": doc_id})
        entities = ner_res.get("entities", [])
        
        # Triplet extraction (slow, but needed for graph)
        triplets_res = await self.mcp.call_tool("knowledge", "build_knowledge_triplets", {
            "text": full_text, "entities": entities, "doc_id": doc_id
        })
        triplets = triplets_res.get("triplets", [])
        results["knowledge"] = {"entities_found": len(entities), "triplets_extracted": len(triplets)}

        # 3. Chunking & Embedding (Server 2)
        chunk_res = await self.mcp.call_tool("knowledge", "chunk_document", {
            "text": full_text, "doc_id": doc_id, "doc_type": doc_type
        })
        chunks = chunk_res.get("chunks", [])
        
        embed_res = await self.mcp.call_tool("knowledge", "generate_embeddings", {"chunks": chunks})
        embedded_chunks = embed_res.get("chunks", [])
        results["processing"] = {"chunks": len(embedded_chunks)}

        # 4. Storage (Server 3)
        # 4a. Store Raw Asset
        store_res = await self.mcp.call_tool("storage", "store_raw_asset", {
            "file_path": file_path, "doc_id": doc_id, 
            "metadata": {"filename": filename, "type": doc_type, "plant": plant_id}
        })
        
        # 4b. Vector Upsert
        vec_res = await self.mcp.call_tool("storage", "vector_upsert", {"chunks": embedded_chunks})
        
        # 4c. Graph Upsert
        # Add Document node
        await self.mcp.call_tool("storage", "graph_upsert_node", {
            "node_id": doc_id, "labels": ["Document", doc_type.capitalize()], 
            "properties": {"filename": filename, "plant": plant_id, "url": store_res.get("url", "")}
        })
        
        # Add entity relationships based on NER
        for eq in ner_res.get("equipment_tags", []):
            await self.mcp.call_tool("storage", "graph_upsert_node", {"node_id": eq, "labels": ["Equipment"], "properties": {}})
            await self.mcp.call_tool("storage", "graph_upsert_edge", {
                "from_id": eq, "to_id": doc_id, "relationship": "MENTIONED_IN", "properties": {}
            })
            
        # Add triplets
        edges_created = 0
        for t in triplets:
            if t.get("subject") and t.get("object") and t.get("predicate"):
                # Very basic normalization - in prod, use the hierarchy tool to ensure node types are correct
                sub = str(t["subject"])
                obj = str(t["object"])
                pred = str(t["predicate"])
                await self.mcp.call_tool("storage", "graph_upsert_node", {"node_id": sub, "labels": ["Entity"], "properties": {}})
                await self.mcp.call_tool("storage", "graph_upsert_node", {"node_id": obj, "labels": ["Entity"], "properties": {}})
                await self.mcp.call_tool("storage", "graph_upsert_edge", {
                    "from_id": sub, "to_id": obj, "relationship": pred, "properties": {"source_doc": doc_id}
                })
                edges_created += 1

        results["storage"] = {
            "vector_chunks": vec_res.get("upserted", 0), 
            "graph_edges_from_triplets": edges_created,
            "raw_stored": store_res.get("stored", False)
        }

        logger.info(f"Ingestion complete for {doc_id}")
        return results
