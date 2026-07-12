"""
Storage tools — Qdrant Cloud vector operations exposed as MCP tools.
vector_upsert, vector_search, vector_delete, vector_collection_info.
"""
from mcp.server.fastmcp import FastMCP
from core import qdrant_client as vc


def register(mcp: FastMCP):

    @mcp.tool()
    async def vector_upsert(chunks: list[dict], collection: str | None = None) -> dict:
        """
        Store document chunks with embeddings in Qdrant Cloud (cloud-hosted vector DB).
        Chunks must have 'embedding' field (1024-dim float list) from generate_embeddings tool.

        Args:
            chunks: List of chunk dicts with 'embedding' and metadata fields.
            collection: Qdrant collection name (defaults to QDRANT_COLLECTION env var).

        Returns:
            Upsert confirmation with count of vectors stored.
        """
        return await vc.upsert_chunks(chunks, collection)

    @mcp.tool()
    async def vector_search(
        query_embedding: list[float],
        top_k: int = 10,
        filter: dict | None = None,
        collection: str | None = None,
    ) -> dict:
        """
        Semantic similarity search over stored document embeddings in Qdrant Cloud.
        Returns top-k most similar chunks with their metadata and similarity scores.

        Args:
            query_embedding: Query vector (1024-dim, from generate_embeddings with is_query=True).
            top_k: Number of results to return (default: 10).
            filter: Optional metadata filter conditions (dict of field→value).
            collection: Qdrant collection name.

        Returns:
            Ranked hits with score, doc_id, text, doc_type, equipment_tags, metadata.
        """
        return await vc.semantic_search(query_embedding, top_k, filter, collection)

    @mcp.tool()
    async def vector_delete(doc_id: str) -> dict:
        """
        Delete all vectors for a document from Qdrant Cloud.
        Used when re-ingesting a document or removing outdated content.

        Args:
            doc_id: Document ID whose chunks should be deleted.
        """
        return await vc.delete_document(doc_id)

    @mcp.tool()
    async def vector_collection_info() -> dict:
        """
        Get statistics for the Qdrant Cloud collection:
        vector count, embedding dimension, collection status.
        """
        return await vc.collection_info()
