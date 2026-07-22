"""
Hybrid search — combines Qdrant Cloud vector similarity + Neo4j AuraDB graph traversal.
The core search brain for the RAG pipeline.
"""
import asyncio
import logging

from mcp.server.fastmcp import FastMCP
from core import embeddings, neo4j_client
from core import pinecone_client as vc
from tools.knowledge.ner_tool import _extract_entities_impl

logger = logging.getLogger("ikp.search.hybrid")


def register(mcp: FastMCP):

    @mcp.tool()
    async def hybrid_search(
        query: str,
        top_k: int = 10,
        doc_types: list[str] | None = None,
        equipment_tags: list[str] | None = None,
        date_range: dict | None = None,
    ) -> dict:
        """
        Combined vector similarity + knowledge graph search.
        This is the primary search tool for the RAG pipeline.

        Step 1: Extract equipment tags from query (NER).
        Step 2: Embed query using Cohere embed-multilingual-v3.0 (1024-dim).
        Step 3: Semantic search in Qdrant Cloud with optional metadata filters.
        Step 4: Traverse Neo4j AuraDB for graph context around detected equipment.
        Step 5: Merge and re-rank results by relevance score.

        Args:
            query: Natural language search query.
            top_k: Number of vector search results (default: 10).
            doc_types: Filter by document types (e.g., ['procedure', 'maintenance']).
            equipment_tags: Explicit equipment tags to include in graph search.
            date_range: Dict with 'start' and 'end' ISO date strings.

        Returns:
            vector_hits: Ranked semantic search results.
            graph_context: Related entities from knowledge graph.
            combined_sources: Merged unique sources for RAG.
        """
        import asyncio

        # ── Step 1: Extract entities from query ──────────────────────────────
        entities = await _extract_entities_impl(query)
        detected_tags = [e["text"] for e in entities.get("equipment_tags", [])]
        all_tags = list(set((equipment_tags or []) + detected_tags))

        # ── Step 2: Embed query (1536-dim) ────────────────────────────────────
        loop = asyncio.get_event_loop()
        query_vec = await loop.run_in_executor(None, embeddings.embed_query, query)

        # ── Step 3: Vector search in Qdrant Cloud ─────────────────────────────
        filters = {}
        if doc_types:
            filters["doc_type"] = doc_types[0]  # single filter for now; extend with OR
        vector_results = await vc.semantic_search(query_vec, top_k=top_k,
                                                   filter_conditions=filters if filters else None)
        vector_hits = vector_results.get("hits", [])

        # ── Step 4: Graph context from Neo4j AuraDB ───────────────────────────
        graph_context = {}
        if all_tags:
            graph_tasks = [neo4j_client.get_subgraph(tag, depth=2) for tag in all_tags[:3]]
            subgraphs = await asyncio.gather(*graph_tasks, return_exceptions=True)
            for tag, sg in zip(all_tags[:3], subgraphs):
                if isinstance(sg, dict):
                    graph_context[tag] = sg

        # ── Step 5: Merge sources ─────────────────────────────────────────────
        combined_sources = []
        for hit in vector_hits:
            doc_id = hit.get("doc_id", "")
            filename = hit.get("metadata", {}).get("filename")
            
            # Additional fallback to source_path if filename is missing
            if not filename:
                source_path = hit.get("metadata", {}).get("source_path")
                if source_path:
                    filename = source_path.split("/")[-1].split("\\")[-1]
            
            # Fallback to Graph DB if filename is missing from vector metadata
            if not filename and doc_id:
                try:
                    res = await neo4j_client.run_cypher(
                        "MATCH (d:Document {id: $doc_id}) RETURN d.filename AS fname, d.title AS title",
                        {"doc_id": doc_id}
                    )
                    if res:
                        filename = res[0].get("fname") or (f"{res[0].get('title')}.pdf" if res[0].get("title") else doc_id)
                except Exception as e:
                    logger.warning(f"Failed to lookup filename for {doc_id}: {e}")
            
            filename = filename or doc_id

            combined_sources.append({
                "doc_id": doc_id,
                "score": hit.get("score", 0.0),
                "text": hit.get("text", ""),
                "section_title": hit.get("section_title", ""),
                "doc_type": hit.get("doc_type", ""),
                "equipment_tags": hit.get("equipment_tags", []),
                "filename": filename,
            })

        return {
            "query": query,
            "detected_equipment_tags": all_tags,
            "vector_hits": vector_hits,
            "graph_context": graph_context,
            "combined_sources": combined_sources,
            "total_sources": len(combined_sources),
        }

    @mcp.tool()
    async def expand_query(user_query: str, user_role: str = "operator") -> dict:
        """
        Rewrite and expand a user query for better retrieval.
        Adds industrial synonyms, equipment tag variations, and domain context.

        Examples:
        - "pump not working" → "pump failure trip malfunction centrifugal P-series
           mechanical seal bearing vibration cavitation"
        - "check procedure" → "standard operating procedure SOP startup shutdown
           operational steps work instruction"

        Args:
            user_query: Original user query string.
            user_role: User role for context-appropriate expansion.

        Returns:
            expanded_query, keywords list, original query.
        """
        from core import llm_client
        EXPAND_SYSTEM = (
            "You are an industrial search query optimizer. "
            "Given a user query, produce an expanded version with synonyms, "
            "equipment tag variations, and related industrial terms. "
            "Respond ONLY with JSON: {\"expanded_query\": \"...\", \"keywords\": [\"...\"]}"
        )
        result = await llm_client.json_chat(
            f"Expand this industrial plant query for a {user_role}: '{user_query}'",
            system=EXPAND_SYSTEM,
            temperature=0.2,
        )
        if result and isinstance(result, dict):
            return {
                "expanded_query": result.get("expanded_query", user_query),
                "keywords": result.get("keywords", []),
                "original": user_query,
            }
        return {"expanded_query": user_query, "keywords": [], "original": user_query}
