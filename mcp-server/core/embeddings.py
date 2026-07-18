"""
Embedding core — Cohere embed-multilingual-v3.0 (1024-dim).

Why Cohere instead of local nomic-embed-text:
  - Cloud API → no GPU/CPU load on the deployment server
  - embed-multilingual-v3.0 supports 100+ languages including Hindi
    (critical for Indian industrial docs with bilingual field notes)
  - 1024-dim vectors → richer semantic representation than 768-dim
  - Input type separation: 'search_document' vs 'search_query' (asymmetric)

API reference: https://docs.cohere.com/reference/embed
Free tier: 1000 API calls/month (sufficient for dev + demo)

EMBEDDING_DIM must be 1024 — this matches the Qdrant Cloud collection size.
Changing this requires wiping and recreating the Qdrant collection.
"""
import logging
import os
import time

import cohere

logger = logging.getLogger("ikp.embeddings")

# ── Config ────────────────────────────────────────────────────────────────────
COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
EMBED_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL", "embed-multilingual-v3.0")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))
EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "96"))  # Cohere max batch = 96

# ── Singleton client ──────────────────────────────────────────────────────────
_client: cohere.Client | None = None


def _get_client() -> cohere.Client:
    global _client
    if _client is None:
        if not COHERE_API_KEY:
            raise RuntimeError(
                "COHERE_API_KEY is not set. Add it to your .env file.\n"
                "Get a free key at: https://dashboard.cohere.com/api-keys"
            )
        _client = cohere.Client(api_key=COHERE_API_KEY)
        logger.info(
            "Cohere client initialised — model=%s dim=%d",
            EMBED_MODEL_NAME,
            EMBEDDING_DIM,
        )
    return _client


def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of document texts for storage in Qdrant.

    Uses input_type='search_document' — Cohere's asymmetric embedding:
    Documents and queries are embedded differently so that a query vector
    points towards its most relevant documents in the vector space.

    Handles Cohere's 96-text batch limit internally — you can pass any
    number of texts and they will be chunked automatically.

    Args:
        texts: List of raw text strings. Do NOT add any prefix manually.

    Returns:
        List of 1024-dimensional float vectors, one per input text.
        Already normalised for cosine similarity.
    """
    if not texts:
        return []

    client = _get_client()
    all_embeddings: list[list[float]] = []

    # Chunk into Cohere's 96-text batch limit
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        if i > 0:
            logger.info("Processing next batch of chunks (delay removed)...")
        batch = texts[i: i + EMBED_BATCH_SIZE]
        try:
            response = client.embed(
                texts=batch,
                model=EMBED_MODEL_NAME,
                input_type="search_document",   # MUST be 'search_document' for stored chunks
                embedding_types=["float"],
            )
            all_embeddings.extend(response.embeddings.float)
        except Exception as e:
            logger.error("Cohere embed (documents) failed for batch %d: %s", i // EMBED_BATCH_SIZE, e)
            raise

    return all_embeddings


def embed_query(text: str) -> list[float]:
    """
    Embed a single user query for similarity search against Qdrant.

    Uses input_type='search_query' — DIFFERENT from embed_documents().
    Cohere's v3 models are trained with asymmetric input types:
      - 'search_document' is used when storing chunks (at ingestion time)
      - 'search_query'    is used when searching  (at query time)
    Mixing them reduces retrieval quality significantly.

    Args:
        text: The user's raw query string (no prefix needed).

    Returns:
        Single 1024-dimensional float vector.
    """
    client = _get_client()
    try:
        response = client.embed(
            texts=[text],
            model=EMBED_MODEL_NAME,
            input_type="search_query",    # MUST be 'search_query' for queries
            embedding_types=["float"],
        )
        return response.embeddings.float[0]
    except Exception as e:
        logger.error("Cohere embed (query) failed: %s", e)
        raise


def get_embedding_info() -> dict:
    """Return metadata about the embedding configuration for health checks."""
    return {
        "provider": "cohere",
        "model": EMBED_MODEL_NAME,
        "dim": EMBEDDING_DIM,
        "batch_size": EMBED_BATCH_SIZE,
        "api_key_set": bool(COHERE_API_KEY),
        "input_types": {
            "documents": "search_document",
            "queries": "search_query",
        },
    }
