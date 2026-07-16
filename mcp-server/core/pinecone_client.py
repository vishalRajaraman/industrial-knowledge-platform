"""
Core client — Pinecone (cloud-hosted vector DB).
Embedding provider: Cohere embed-multilingual-v3.0 (1024-dim).
Dimension is read from EMBEDDING_DIM env var (default: 1024).
"""
import asyncio
import os
import uuid
from typing import Any

from pinecone import Pinecone, ServerlessSpec

# ── Config ────────────────────────────────────────────────────────────────────
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
DEFAULT_INDEX = os.getenv("PINECONE_INDEX", "ikp-documents")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

_pc: Pinecone | None = None


def get_client() -> Pinecone:
    global _pc
    if _pc is None:
        _key = os.getenv("PINECONE_API_KEY")
        if not _key:
            raise EnvironmentError(
                "PINECONE_API_KEY must be set in the environment variables."
            )
        _pc = Pinecone(api_key=_key)
    return _pc


def ensure_index(client: Pinecone, index_name: str = DEFAULT_INDEX):
    existing_indexes = [info.name for info in client.list_indexes()]
    if index_name not in existing_indexes:
        client.create_index(
            name=index_name,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )


# ── Public async API ──────────────────────────────────────────────────────────

async def upsert_chunks(chunks: list[dict[str, Any]], collection: str | None = None) -> dict:
    index_name = collection or DEFAULT_INDEX
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        ensure_index(client, index_name)
        index = client.Index(index_name)
        
        vectors = []
        for chunk in chunks:
            embedding = chunk.get("embedding")
            if not embedding:
                continue
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.get("chunk_id", str(uuid.uuid4()))))
            payload = {k: v for k, v in chunk.items() if k != "embedding"}
            vectors.append({"id": point_id, "values": embedding, "metadata": payload})

        if not vectors:
            return {"error": "No valid chunks with embeddings", "upserted": 0}

        batch_size = 100
        total = 0
        for i in range(0, len(vectors), batch_size):
            index.upsert(vectors=vectors[i : i + batch_size])
            total += len(vectors[i : i + batch_size])
            
        return {"collection": index_name, "upserted": total, "total_chunks": len(chunks)}

    return await loop.run_in_executor(None, _run)


async def semantic_search(
    query_embedding: list[float],
    top_k: int = 10,
    filter_conditions: dict | None = None,
    collection: str | None = None,
) -> dict:
    index_name = collection or DEFAULT_INDEX
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        index = client.Index(index_name)
        
        pinecone_filter = None
        if filter_conditions:
            pinecone_filter = {k: {"$eq": v} for k, v in filter_conditions.items()}

        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=pinecone_filter,
            include_metadata=True,
        )

        hits = []
        if hasattr(results, "matches"):
            for r in results.matches:
                meta = r.metadata or {}
                hits.append({
                    "score": round(float(r.score), 4),
                    "chunk_id": meta.get("chunk_id", ""),
                    "doc_id": meta.get("doc_id", ""),
                    "text": meta.get("text", ""),
                    "doc_type": meta.get("doc_type", ""),
                    "section_title": meta.get("section_title", ""),
                    "equipment_tags": meta.get("equipment_tags", []),
                    "metadata": {
                        k: v for k, v in meta.items()
                        if k not in ("text", "chunk_id", "doc_id", "doc_type", "section_title", "equipment_tags")
                    },
                })
                
        return {"collection": index_name, "total_hits": len(hits), "hits": hits}

    return await loop.run_in_executor(None, _run)


async def delete_document(doc_id: str) -> dict:
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        index = client.Index(DEFAULT_INDEX)
        
        # Pinecone doesn't support directly deleting by filter on Starter/Serverless sometimes,
        # but the standard filter syntax is: index.delete(filter={"doc_id": {"$eq": doc_id}})
        # We will attempt the filter deletion.
        index.delete(filter={"doc_id": {"$eq": doc_id}})
        
        return {"deleted": True, "doc_id": doc_id}

    return await loop.run_in_executor(None, _run)


async def collection_info() -> dict:
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        stats = client.Index(DEFAULT_INDEX).describe_index_stats()
        return {
            "collection": DEFAULT_INDEX,
            "embedding_dim": EMBEDDING_DIM,
            "vectors_count": stats.total_vector_count,
            "points_count": stats.total_vector_count,
            "status": "ready"
        }

    return await loop.run_in_executor(None, _run)
