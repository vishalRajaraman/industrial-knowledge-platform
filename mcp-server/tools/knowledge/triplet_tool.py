"""
Knowledge triplet extractor — builds (subject, predicate, object) triples
from text using LLM, for knowledge graph population.
"""
import logging

from mcp.server.fastmcp import FastMCP
from core import llm_client, neo4j_client

logger = logging.getLogger("ikp.knowledge.triplet")

TRIPLET_SYSTEM = """You are a knowledge graph builder for industrial plant operations.
Extract factual (subject, predicate, object) knowledge triplets from the text.
Focus on: equipment relationships, failure events, maintenance actions, regulatory compliance.
Respond ONLY with valid JSON:
{"triplets": [{"subject": "...", "predicate": "...", "object": "...", "confidence": 0.0-1.0}]}
"""


def register(mcp: FastMCP):

    @mcp.tool()
    async def build_knowledge_triplets(text: str, entities: list[dict] = None, doc_id: str = "") -> dict:
        """
        Extract (subject, predicate, object) knowledge triplets from text using LLM.
        Automatically creates corresponding nodes and edges in Neo4j AuraDB.

        Example triplets:
        - (P-101A, HAS_FAILURE, bearing_failure)
        - (P-101A, GOVERNED_BY, OISD-154-Clause-5.1)
        - (John Smith, PERFORMED, WO-2024-1234)
        - (Procedure-SOP-001, APPLIES_TO, P-101A)

        Args:
            text: Text to extract triplets from.
            entities: Pre-extracted entities from extract_entities (guides extraction).
            doc_id: Source document ID for provenance tracking.

        Returns:
            Extracted triplets and count of KG nodes/edges created.
        """
        entity_context = ""
        if entities:
            tags = [e.get("text", "") for e in entities if e.get("text")]
            entity_context = f"\nKnown entities in this text: {', '.join(tags[:20])}"

        prompt = f"""Extract knowledge triplets from this industrial document text:

{text[:8000]}
{entity_context}

Focus on: equipment failures, maintenance actions, compliance mappings, personnel assignments.
Respond with JSON only."""

        result = await llm_client.json_chat(prompt, system=TRIPLET_SYSTEM, temperature=0.1)

        if not result or "triplets" not in result:
            return {"triplets": [], "kg_edges_created": 0, "error": "LLM failed to extract triplets"}

        triplets = result["triplets"]
        kg_edges = 0

        for t in triplets:
            subj = str(t.get("subject", "")).strip()
            pred = str(t.get("predicate", "")).replace(" ", "_").upper()
            obj = str(t.get("object", "")).strip()

            if not subj or not pred or not obj:
                continue

            # Create nodes
            await neo4j_client.upsert_node(subj, ["Entity"], {"name": subj})
            await neo4j_client.upsert_node(obj, ["Entity"], {"name": obj})
            # Create relationship
            await neo4j_client.upsert_edge(subj, obj, pred, {"source_doc": doc_id})
            kg_edges += 1

        return {
            "triplets": triplets,
            "triplet_count": len(triplets),
            "kg_edges_created": kg_edges,
            "doc_id": doc_id,
        }
