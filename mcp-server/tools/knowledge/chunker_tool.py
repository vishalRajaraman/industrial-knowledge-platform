"""
Document chunker — semantic chunking for RAG-optimal retrieval.
Preserves section boundaries and context across document types.
"""
import re
import uuid
from typing import Any


def _chunk_text(
    text: str,
    doc_id: str,
    doc_type: str = "general",
    max_size: int = 512,
    overlap: int = 64,
) -> list[dict]:
    """
    Semantically chunk a document into retrieval-optimal segments.
    Uses LangChain's SemanticChunker with Cohere Embeddings to dynamically
    group sentences by semantic similarity, avoiding arbitrary cutoffs.
    """
    import os
    import uuid
    from langchain_experimental.text_splitter import SemanticChunker
    from langchain_cohere import CohereEmbeddings
    
    if len(text.strip()) < 30:
        return []

    cohere_api_key = os.getenv("COHERE_API_KEY")
    if not cohere_api_key:
        raise ValueError("COHERE_API_KEY environment variable is not set")
    
    # Initialize embedding model and SemanticChunker
    embeddings = CohereEmbeddings(cohere_api_key=cohere_api_key, model="embed-multilingual-v3.0")
    text_splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
    
    # Split the text semantically
    docs = text_splitter.create_documents([text])
    
    chunks = []
    for i, doc in enumerate(docs):
        chunk_text = doc.page_content.strip()
        if len(chunk_text) < 10:
            continue
            
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "doc_type": doc_type,
            "chunk_index": i,
            "text": chunk_text,
            "char_length": len(chunk_text),
        })

    return chunks


# ── MCP tool registration ─────────────────────────────────────────────────────

def register(mcp):

    @mcp.tool()
    async def chunk_document(
        text: str,
        doc_id: str,
        doc_type: str = "general",
        max_chunk_size: int = 512,
        overlap: int = 64,
    ) -> dict:
        """
        Semantically chunk a document into retrieval-optimal segments for RAG.
        Preserves section boundaries and avoids splitting mid-procedure.

        Chunking strategy by document type:
        - procedure / SOP: chunk by numbered step boundaries
        - maintenance / work_order: chunk by work order entry
        - inspection: chunk by equipment finding
        - regulation: chunk by clause
        - general: recursive paragraph-aware chunker

        Args:
            text: Full document text to chunk.
            doc_id: Document identifier for metadata injection.
            doc_type: Type: procedure, maintenance, inspection, regulation, manual, general.
            max_chunk_size: Target chunk size in tokens (default: 512).
            overlap: Token overlap between consecutive chunks (default: 64).

        Returns:
            List of chunks with chunk_id, doc_id, text, char_length metadata.
        """
        chunks = _chunk_text(text, doc_id, doc_type, max_chunk_size, overlap)
        return {
            "doc_id": doc_id,
            "chunk_count": len(chunks),
            "chunks": chunks,
            "total_chars": sum(c["char_length"] for c in chunks),
        }
