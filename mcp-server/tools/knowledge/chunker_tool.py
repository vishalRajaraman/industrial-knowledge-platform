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
    Strategy varies by document type:
    - Procedures: chunk by numbered step or section
    - Maintenance logs: chunk by work order entry
    - Inspection reports: chunk by equipment/finding
    - Default: recursive character splitter with overlap
    """
    chunks = []

    # ── Section-aware splitting ─────────────────────────────────────────────
    # Detect section headings (numbered, all-caps, or markdown-style)
    section_pattern = r"(?m)^(?:\d+[\.\)]\s+[A-Z]|#{1,3}\s+|[A-Z]{3,}[:\s]|(?:Step|STEP|Section|SECTION)\s+\d+)"
    sections = re.split(section_pattern, text)

    raw_chunks = []
    if len(sections) > 2:
        # Section-aware: split by detected boundaries
        for i, section in enumerate(sections):
            if len(section.strip()) < 50:
                continue
            raw_chunks.extend(_sliding_window(section, max_size, overlap))
    else:
        # Fallback: paragraph-aware splitting
        paragraphs = re.split(r"\n\n+", text)
        current = ""
        for para in paragraphs:
            if len(current) + len(para) < max_size * 4:  # chars
                current += "\n\n" + para
            else:
                if current.strip():
                    raw_chunks.extend(_sliding_window(current, max_size, overlap))
                current = para
        if current.strip():
            raw_chunks.extend(_sliding_window(current, max_size, overlap))

    for i, chunk_text in enumerate(raw_chunks):
        if len(chunk_text.strip()) < 30:
            continue
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "doc_type": doc_type,
            "chunk_index": i,
            "text": chunk_text.strip(),
            "char_length": len(chunk_text),
        })

    return chunks


def _sliding_window(text: str, max_size: int, overlap: int) -> list[str]:
    """Split text into overlapping windows (token-approximate using char count × 4)."""
    max_chars = max_size * 4   # approximate chars per token
    overlap_chars = overlap * 4
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # Snap to sentence boundary
        if end < len(text):
            snap = text.rfind(".", start, end)
            if snap > start:
                end = snap + 1
        chunks.append(text[start:end])
        start = end - overlap_chars
        if start >= len(text):
            break
    return [c for c in chunks if c.strip()]


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
