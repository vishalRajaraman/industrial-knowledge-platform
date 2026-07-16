from __future__ import annotations

import asyncio
import hashlib
import os
import re
from io import BytesIO
from typing import Any

from ..core.task_store import (
    mark_document_task_completed,
    mark_document_task_failed,
    update_document_task,
)


async def run_document_pipeline(
    task_id: str,
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    submitted_by: str,
    role: str,
) -> None:
    try:
        await update_document_task(task_id, status="PROCESSING", current_step="extract_text")
        extracted_text = await _extract_text(file_bytes=file_bytes, filename=filename, content_type=content_type)

        await update_document_task(task_id, current_step="generate_embeddings")
        embedding_vector = await _generate_embedding_stub(extracted_text)
        vector_result = await _simulate_vector_upsert(
            task_id=task_id,
            filename=filename,
            extracted_text=extracted_text,
            embedding_vector=embedding_vector,
        )

        await update_document_task(task_id, current_step="update_knowledge_graph")
        graph_result = await _simulate_graph_update(
            task_id=task_id,
            filename=filename,
            extracted_text=extracted_text,
        )

        result = {
            "submitted_by": submitted_by,
            "role": role,
            "source_file": filename,
            "content_type": content_type,
            "steps": [
                {"name": "extract_text", "status": "completed", "characters": len(extracted_text)},
                {"name": "generate_embeddings", "status": "completed", "vector_dim": len(embedding_vector)},
                {"name": "upsert_vector_db", "status": "stubbed", **vector_result},
                {"name": "update_knowledge_graph", "status": "stubbed", **graph_result},
            ],
        }
        await mark_document_task_completed(task_id, result=result)
    except Exception as exc:  # pragma: no cover - defensive async worker guard
        await mark_document_task_failed(task_id, error=str(exc), current_step="failed")


async def _extract_text(*, file_bytes: bytes, filename: str, content_type: str | None) -> str:
    suffix = os.path.splitext(filename.lower())[1]

    if suffix == ".pdf" or (content_type or "").lower() == "application/pdf":
        pdf_text = await _try_extract_pdf_text(file_bytes)
        if pdf_text.strip():
            return pdf_text

    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        ocr_text = await _try_extract_image_text(file_bytes)
        if ocr_text.strip():
            return ocr_text

    return _decode_text(file_bytes)


async def _try_extract_pdf_text(file_bytes: bytes) -> str:
    loop = asyncio.get_event_loop()

    def _run() -> str:
        try:
            import fitz  # type: ignore
        except Exception:
            return ""

        try:
            document = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception:
            return ""

        pages = []
        for page in document:
            try:
                pages.append(page.get_text())
            except Exception:
                continue
        return "\n".join(pages)

    return await loop.run_in_executor(None, _run)


async def _try_extract_image_text(file_bytes: bytes) -> str:
    loop = asyncio.get_event_loop()

    def _run() -> str:
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
        except Exception:
            return ""

        try:
            image = Image.open(BytesIO(file_bytes))
            return pytesseract.image_to_string(image)
        except Exception:
            return ""

    return await loop.run_in_executor(None, _run)


def _decode_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            decoded = file_bytes.decode(encoding)
            if decoded.strip():
                return decoded
        except Exception:
            continue
    return f"[binary document payload of {len(file_bytes)} bytes]"


async def _generate_embedding_stub(text: str, dimension: int = 16) -> list[float]:
    loop = asyncio.get_event_loop()

    def _run() -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        vector: list[float] = []
        for index in range(dimension):
            byte_value = digest[index % len(digest)]
            vector.append(round(byte_value / 255.0, 6))
        return vector

    return await loop.run_in_executor(None, _run)


async def _simulate_vector_upsert(
    *,
    task_id: str,
    filename: str,
    extracted_text: str,
    embedding_vector: list[float],
) -> dict[str, Any]:
    chunk = {
        "task_id": task_id,
        "filename": filename,
        "chunk_count": 1,
        "character_count": len(extracted_text),
        "vector_dim": len(embedding_vector),
        "collection": os.getenv("QDRANT_COLLECTION", "ikp_documents"),
        "mode": "stub",
    }
    return chunk


async def _simulate_graph_update(*, task_id: str, filename: str, extracted_text: str) -> dict[str, Any]:
    entities = _extract_entities(extracted_text)
    return {
        "task_id": task_id,
        "filename": filename,
        "entities_detected": entities,
        "node_count": len(entities),
        "edge_count": max(len(entities) - 1, 0),
        "graph_backend": os.getenv("NEO4J_URI", "neo4j://stub"),
        "mode": "stub",
    }


def _extract_entities(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", text)
    seen: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.append(candidate)
    return seen[:25]
