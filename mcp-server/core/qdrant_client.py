"""
Core client — Qdrant Cloud (cloud-hosted vector DB).
Embedding provider: Cohere embed-multilingual-v3.0 (1024-dim).
Dimension is read from EMBEDDING_DIM env var (default: 1024).
"""
import asyncio
import os
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

# ── Config ────────────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL")           # e.g. https://xxxx.cloud.qdrant.io
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")   # from Qdrant Cloud dashboard
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ikp_documents")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))    # Cohere embed-multilingual-v3.0 native dim

# NOTE: Credentials are validated lazily in get_client(), not at import time.
# This allows server.py to finish importing all modules before connectivity is checked.

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _url = os.getenv("QDRANT_URL")
        _key = os.getenv("QDRANT_API_KEY")
        if not _url or not _key:
            raise EnvironmentError(
                "QDRANT_URL and QDRANT_API_KEY must be set for Qdrant Cloud. "
                "Sign up free at https://cloud.qdrant.io"
            )
        _client = QdrantClient(url=_url, api_key=_key)
    return _client


def ensure_collection(client: QdrantClient, collection: str = DEFAULT_COLLECTION):
    existing = [c.name for c in client.get_collections().collections]
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


# ── Public async API ──────────────────────────────────────────────────────────

async def upsert_chunks(chunks: list[dict[str, Any]], collection: str | None = None) -> dict:
    col = collection or DEFAULT_COLLECTION
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        ensure_collection(client, col)
        points = []
        for chunk in chunks:
            embedding = chunk.get("embedding")
            if not embedding:
                continue
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.get("chunk_id", str(uuid.uuid4()))))
            payload = {k: v for k, v in chunk.items() if k != "embedding"}
            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        if not points:
            return {"error": "No valid chunks with embeddings", "upserted": 0}

        batch_size = 100
        total = 0
        for i in range(0, len(points), batch_size):
            client.upsert(collection_name=col, points=points[i : i + batch_size])
            total += len(points[i : i + batch_size])
        return {"collection": col, "upserted": total, "total_chunks": len(chunks)}

    return await loop.run_in_executor(None, _run)


async def semantic_search(
    query_embedding: list[float],
    top_k: int = 10,
    filter_conditions: dict | None = None,
    collection: str | None = None,
) -> dict:
    col = collection or DEFAULT_COLLECTION
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        qdrant_filter = None
        if filter_conditions:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_conditions.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = client.search(
            collection_name=col,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        hits = [
            {
                "score": round(float(r.score), 4),
                "chunk_id": r.payload.get("chunk_id", ""),
                "doc_id": r.payload.get("doc_id", ""),
                "text": r.payload.get("text", ""),
                "doc_type": r.payload.get("doc_type", ""),
                "section_title": r.payload.get("section_title", ""),
                "equipment_tags": r.payload.get("equipment_tags", []),
                "metadata": {
                    k: v
                    for k, v in r.payload.items()
                    if k not in ("text", "chunk_id", "doc_id", "doc_type", "section_title", "equipment_tags")
                },
            }
            for r in results
        ]
        return {"collection": col, "total_hits": len(hits), "hits": hits}

    return await loop.run_in_executor(None, _run)


async def delete_document(doc_id: str) -> dict:
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        client.delete(
            collection_name=DEFAULT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
            ),
        )
        return {"deleted": True, "doc_id": doc_id}

    return await loop.run_in_executor(None, _run)


async def collection_info() -> dict:
    loop = asyncio.get_event_loop()

    def _run():
        client = get_client()
        info = client.get_collection(DEFAULT_COLLECTION)
        return {
            "collection": DEFAULT_COLLECTION,
            "embedding_dim": EMBEDDING_DIM,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": str(info.status),
        }

    return await loop.run_in_executor(None, _run)
