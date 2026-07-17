import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles

from .api.v1.documents import get_upload_task, upload_document
from .api.v1.auth import login, get_me, logout
from .api.v1.health import get_health
from .api.v1.search import post_graph_search, post_vector_search
from .core.config import settings
from .core.middleware import configure_middleware
from .schemas.auth import AuthenticatedUser, LoginRequest, TokenResponse
from .schemas.documents import DocumentTaskResponse, UploadAcceptedResponse
from .schemas.health import HealthResponse
from .schemas.search import GraphSearchRequest, SearchStubResponse, VectorSearchRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        default_response_class=ORJSONResponse,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )
    configure_middleware(app, settings)
    
    app.add_api_route(
        f"{settings.api_prefix}/auth/login",
        login,
        methods=["POST"],
        response_model=TokenResponse,
        tags=["auth"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/auth/me",
        get_me,
        methods=["GET"],
        response_model=AuthenticatedUser,
        tags=["auth"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/auth/logout",
        logout,
        methods=["POST"],
        tags=["auth"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/search/vector",
        post_vector_search,
        methods=["POST"],
        response_model=SearchStubResponse,
        tags=["search"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/search/graph",
        post_graph_search,
        methods=["POST"],
        response_model=SearchStubResponse,
        tags=["search"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/system/health",
        get_health,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["system"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/documents/upload",
        upload_document,
        methods=["POST"],
        response_model=UploadAcceptedResponse,
        status_code=202,
        tags=["documents"],
    )
    app.add_api_route(
        f"{settings.api_prefix}/documents/tasks/{{task_id}}",
        get_upload_task,
        methods=["GET"],
        response_model=DocumentTaskResponse,
        tags=["documents"],
    )

    # Mount the Next.js static export
    frontend_dir = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "out"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    
    return app


app = create_app()
