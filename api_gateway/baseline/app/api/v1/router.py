from fastapi import APIRouter

from .auth import router as auth_router
from .health import router as health_router
from .search import router as search_router


api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(health_router)
