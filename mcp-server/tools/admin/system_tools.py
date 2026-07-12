"""
Admin / system tools:
- admin_health_check: Overall system health
- admin_list_documents: All ingested documents
- admin_get_stats: Platform-wide statistics
- admin_keepalive: Neo4j AuraDB keepalive ping
"""
import logging
import os

from mcp.server.fastmcp import FastMCP
from core import neo4j_client
from core import qdrant_client as vc

logger = logging.getLogger("ikp.admin")


def register(mcp: FastMCP):

    @mcp.tool()
    async def admin_health_check() -> dict:
        """
        Check the health of all platform components:
        - Qdrant Cloud (vector DB)
        - Neo4j AuraDB (knowledge graph)
        - LLM providers (Groq, Google AI Studio, Ollama)
        - Embedding model
        - AWS S3

        Returns:
            Component-level health status and overall platform status.
        """
        health = {"overall": "healthy", "components": {}}

        # ── Qdrant Cloud ─────────────────────────────────────────────────────
        try:
            info = await vc.collection_info()
            health["components"]["qdrant_cloud"] = {
                "status": "healthy",
                "vectors": info.get("vectors_count", 0),
                "embedding_dim": info.get("embedding_dim", 0),
            }
        except Exception as e:
            health["components"]["qdrant_cloud"] = {"status": "unhealthy", "error": str(e)}
            health["overall"] = "degraded"

        # ── Neo4j AuraDB ─────────────────────────────────────────────────────
        try:
            counts = await neo4j_client.run_cypher("MATCH (n) RETURN count(n) as total LIMIT 1")
            health["components"]["neo4j_auradb"] = {
                "status": "healthy",
                "total_nodes": counts[0]["total"] if counts else 0,
            }
        except Exception as e:
            health["components"]["neo4j_auradb"] = {"status": "unhealthy", "error": str(e)}
            health["overall"] = "degraded"

        # ── LLM provider (Mistral via NVIDIA NIM) ───────────────────────────────────────────
        nvidia_key = bool(os.getenv("NVIDIA_API_KEY"))
        health["components"]["llm_provider"] = {
            "provider": "NVIDIA NIM",
            "model": os.getenv("LLM_MODEL", "mistralai/mistral-medium-3.5-128b"),
            "status": "configured" if nvidia_key else "not_configured",
        }

        # ── Embedding provider (Cohere Cloud API) ─────────────────────────────────────
        from core import embeddings
        cohere_key = bool(os.getenv("COHERE_API_KEY"))
        health["components"]["embedding_provider"] = {
            "provider": "Cohere Cloud",
            "model": embeddings.EMBED_MODEL_NAME,
            "dim": embeddings.EMBEDDING_DIM,
            "status": "configured" if cohere_key else "not_configured",
        }

        # ── S3 / Object Store ─────────────────────────────────────────────────
        health["components"]["object_storage"] = {
            "type": "aws_s3" if os.getenv("AWS_ACCESS_KEY_ID") else "minio_local",
            "bucket": os.getenv("S3_BUCKET", "not_configured"),
        }

        return health

    @mcp.tool()
    async def admin_list_documents(doc_type: str | None = None, limit: int = 50) -> dict:
        """
        List all ingested documents in the knowledge base.
        Optionally filter by document type.

        Args:
            doc_type: Filter by type (procedure, maintenance, inspection, regulation, etc.).
            limit: Maximum results to return (default: 50).

        Returns:
            List of documents with doc_id, title, type, chunk_count, ingestion date.
        """
        if doc_type:
            cypher = "MATCH (d:Document {doc_type: $doc_type}) RETURN d LIMIT $limit"
            rows = await neo4j_client.run_cypher(cypher, {"doc_type": doc_type, "limit": limit})
        else:
            cypher = "MATCH (d:Document) RETURN d LIMIT $limit"
            rows = await neo4j_client.run_cypher(cypher, {"limit": limit})

        docs = []
        for row in rows:
            node = row.get("d", {})
            if hasattr(node, "items"):
                docs.append(dict(node))
            elif isinstance(node, dict):
                docs.append(node)

        return {"documents": docs, "count": len(docs), "filter": doc_type or "all"}

    @mcp.tool()
    async def admin_get_stats() -> dict:
        """
        Get platform-wide statistics:
        - Document counts by type
        - Knowledge graph node/relationship counts
        - Vector store size
        - Equipment registry stats
        """
        # KG stats
        node_counts = await neo4j_client.run_cypher(
            "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC"
        )
        rel_counts = await neo4j_client.run_cypher(
            "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC LIMIT 10"
        )

        # Vector stats
        try:
            vector_info = await vc.collection_info()
        except Exception:
            vector_info = {}

        return {
            "knowledge_graph": {
                "nodes_by_label": node_counts,
                "relationships_by_type": rel_counts,
            },
            "vector_store": {
                "total_vectors": vector_info.get("vectors_count", "unknown"),
                "embedding_dim": vector_info.get("embedding_dim", "unknown"),
                "collection": vector_info.get("collection", "unknown"),
            },
        }

    @mcp.tool()
    async def admin_keepalive() -> dict:
        """
        Ping Neo4j AuraDB to prevent auto-pause (AuraDB free tier pauses after 3 days of inactivity).
        Schedule this to run every 2 days via a cron job.
        Returns ping confirmation.
        """
        success = await neo4j_client.keepalive_ping()
        return {"neo4j_keepalive": "success" if success else "failed", "auradb_auto_pause": "prevented"}
