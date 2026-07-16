from typing import Any

from pydantic import BaseModel, Field


class VectorSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] | None = None
    session_id: str | None = None


class GraphSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    depth: int = Field(default=2, ge=1, le=8)
    params: dict[str, Any] | None = None
    session_id: str | None = None


class SearchStubResponse(BaseModel):
    status: str = Field(default="stub")
    mode: str
    query: str
    session_id: str | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
