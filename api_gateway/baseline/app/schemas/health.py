from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    service: str = Field(default="api-gateway")
    version: str = Field(default="0.1.0")
    ready: bool = Field(default=True)
    dependencies: dict[str, bool] = Field(default_factory=dict)
