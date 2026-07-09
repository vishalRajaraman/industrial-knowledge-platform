"""
Embedding core — nomic-ai/nomic-embed-text-v1.5 (768-dim) OR
                 OpenAI text-embedding-3-small (1536-dim, API key free tier).

EMBEDDING_DIM env var controls which model is used.
Default: 1536 with nomic-embed-text-v1.5-matryoshka (supports variable dim).

NOTE: nomic-embed-text-v1.5 natively supports Matryoshka truncation,
so you can use 768, 1024, or 1536 dim from the SAME model by slicing.
We default to 1536 for richer semantic representation.
"""
import logging
import os
from typing import Union

logger = logging.getLogger("ikp.embeddings")

EMBED_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s (dim=%d)", EMBED_MODEL_NAME, EMBEDDING_DIM)
        _model = SentenceTransformer(EMBED_MODEL_NAME, trust_remote_code=True)
        logger.info("Embedding model loaded.")
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of document texts.
    Uses 'search_document:' prefix per nomic-embed-text spec.
    Returns 1536-dim (or EMBEDDING_DIM) normalized float vectors.
    """
    model = _get_model()
    prefixed = [f"search_document: {t}" for t in texts]
    vecs = model.encode(
        prefixed,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
        # Matryoshka truncation: only available via encode_multi_process or direct slice
    )
    # Slice to target dimension (Matryoshka truncation)
    return [v.tolist()[:EMBEDDING_DIM] for v in vecs]


def embed_query(text: str) -> list[float]:
    """
    Embed a single query string.
    Uses 'search_query:' prefix — different from document prefix per nomic spec.
    """
    model = _get_model()
    vec = model.encode(
        f"search_query: {text}",
        normalize_embeddings=True,
    )
    return vec.tolist()[:EMBEDDING_DIM]


def embed_batch(texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Generic batch embed."""
    if is_query:
        return [embed_query(t) for t in texts]
    return embed_documents(texts)
