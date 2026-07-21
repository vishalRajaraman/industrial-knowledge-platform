from fastapi import APIRouter, Depends

from ...core.identity import SYSTEM_ROLES
from ...dependencies.auth import require_roles
from ...controllers.search_controller import build_graph_search_stub, build_vector_search_stub
from ...schemas.auth import AuthenticatedUser
from ...schemas.search import GraphSearchRequest, SearchStubResponse, VectorSearchRequest


router = APIRouter(prefix="/search", tags=["search"])


@router.post("/vector", response_model=SearchStubResponse)
async def post_vector_search(
    request: VectorSearchRequest,
    current_user: AuthenticatedUser = Depends(require_roles(*SYSTEM_ROLES)),
) -> SearchStubResponse:
    return await build_vector_search_stub(request)


@router.post("/graph", response_model=SearchStubResponse)
async def post_graph_search(
    request: GraphSearchRequest,
    current_user: AuthenticatedUser = Depends(require_roles("manager", "engineer")),
) -> SearchStubResponse:
    return await build_graph_search_stub(request)
