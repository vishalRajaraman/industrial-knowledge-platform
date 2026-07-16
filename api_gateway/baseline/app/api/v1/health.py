from fastapi import APIRouter

from ...controllers.health_controller import build_health_response
from ...schemas.health import HealthResponse


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return build_health_response()
