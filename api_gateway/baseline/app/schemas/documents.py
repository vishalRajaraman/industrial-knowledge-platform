from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentTaskStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


class UploadAcceptedResponse(BaseModel):
    task_id: str
    status: DocumentTaskStatus = "PENDING"
    message: str = "Upload accepted for asynchronous processing"
    filename: str
    submitted_by: str
    role: Literal["manager", "engineer"]


class DocumentTaskResponse(BaseModel):
    task_id: str
    status: DocumentTaskStatus
    filename: str
    submitted_by: str
    role: Literal["manager", "engineer"]
    created_at: str
    updated_at: str
    current_step: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
