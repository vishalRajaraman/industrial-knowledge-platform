"""
Embedding MCP tool — generate_embeddings for batch processing.
Wraps core/embeddings.py for MCP tool exposure.
"""
import asyncio
import logging

from mcp.server.fastmcp import FastMCP
from core import embeddings

logger = logging.getLogger("ikp.knowledge.embedding")


def register(mcp: FastMCP):

    @mcp.tool()
    async def generate_embeddings(chunks: list[dict]) -> dict:
        """
        Generate 1536-dim vector embeddings for document chunks.
        Uses nomic-ai/nomic-embed-text-v1.5 with Matryoshka truncation.
        Runs locally — no external API calls for embedding.

        The embedding dimension is controlled by the EMBEDDING_DIM environment
        variable (default: 1536). Higher dimensions = richer semantic representation
        but more Qdrant Cloud storage.

        Args:
            chunks: List of chunk dicts from chunk_document tool.
                    Each chunk must have a 'text' field.

        Returns:
            Chunks with 'embedding' field added (list of 1536 floats).
        """
        if not chunks:
            return {"error": "No chunks provided", "chunks_with_embeddings": []}

        loop = asyncio.get_event_loop()
        texts = [c.get("text", "") for c in chunks]

        vecs = await loop.run_in_executor(None, embeddings.embed_documents, texts)

        enriched = []
        for chunk, vec in zip(chunks, vecs):
            enriched.append({**chunk, "embedding": vec})

        return {
            "chunks_with_embeddings": enriched,
            "embedding_dim": len(vecs[0]) if vecs else 0,
            "model": embeddings.EMBED_MODEL_NAME,
            "total_chunks": len(enriched),
        }
