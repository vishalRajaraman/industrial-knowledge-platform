from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Literal
import asyncio

from .identity import SystemRole


TaskStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class DocumentTaskRecord:
    task_id: str
    status: TaskStatus
    filename: str
    username: str
    role: SystemRole
    created_at: str
    updated_at: str
    current_step: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TASKS: dict[str, DocumentTaskRecord] = {}
_LOCK = asyncio.Lock()


async def create_document_task(task_id: str, filename: str, username: str, role: SystemRole) -> DocumentTaskRecord:
    record = DocumentTaskRecord(
        task_id=task_id,
        status="PENDING",
        filename=filename,
        username=username,
        role=role,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    async with _LOCK:
        _TASKS[task_id] = record
    return record


async def get_document_task(task_id: str) -> DocumentTaskRecord | None:
    async with _LOCK:
        return _TASKS.get(task_id)


async def update_document_task(
    task_id: str,
    *,
    status: TaskStatus | None = None,
    current_step: str | None = None,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> DocumentTaskRecord | None:
    async with _LOCK:
        record = _TASKS.get(task_id)
        if record is None:
            return None

        if status is not None:
            record.status = status
        if current_step is not None:
            record.current_step = current_step
        if error is not None:
            record.error = error
        if result is not None:
            record.result = result
        record.updated_at = _now_iso()
        return record


async def mark_document_task_failed(task_id: str, error: str, current_step: str | None = None) -> None:
    await update_document_task(task_id, status="FAILED", current_step=current_step, error=error)


async def mark_document_task_completed(task_id: str, result: dict[str, Any]) -> None:
    await update_document_task(task_id, status="COMPLETED", current_step="completed", result=result)
