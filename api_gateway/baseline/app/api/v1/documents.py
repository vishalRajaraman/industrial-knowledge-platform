from __future__ import annotations

import asyncio
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ...core.identity import SystemRole
from ...core.task_store import create_document_task, get_document_task
from ...dependencies.auth import require_roles
from ...schemas.auth import AuthenticatedUser
from ...schemas.documents import DocumentTaskResponse, UploadAcceptedResponse
from ...workers.document_pipeline import run_document_pipeline


UPLOAD_ROLES: tuple[SystemRole, ...] = ("manager", "engineer")

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_roles(*UPLOAD_ROLES)),
) -> UploadAcceptedResponse:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    task_id = str(uuid.uuid4())
    await create_document_task(
        task_id=task_id,
        filename=file.filename or "document",
        username=current_user.username,
        role=current_user.role,
    )

    asyncio.create_task(
        run_document_pipeline(
            task_id,
            file_bytes=file_bytes,
            filename=file.filename or "document",
            content_type=file.content_type,
            submitted_by=current_user.username,
            role=current_user.role,
        )
    )

    return UploadAcceptedResponse(
        task_id=task_id,
        filename=file.filename or "document",
        submitted_by=current_user.username,
        role=current_user.role,
    )


@router.get("/tasks/{task_id}", response_model=DocumentTaskResponse)
async def get_upload_task(
    task_id: str,
    current_user: AuthenticatedUser = Depends(require_roles(*UPLOAD_ROLES)),
) -> DocumentTaskResponse:
    record = await get_document_task(task_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return DocumentTaskResponse(
        task_id=record.task_id,
        status=record.status,
        filename=record.filename,
        submitted_by=record.username,
        role=record.role,
        created_at=record.created_at,
        updated_at=record.updated_at,
        current_step=record.current_step,
        error=record.error,
        result=record.result,
    )
