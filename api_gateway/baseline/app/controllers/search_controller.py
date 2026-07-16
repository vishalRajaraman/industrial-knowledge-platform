from ..schemas.search import GraphSearchRequest, SearchStubResponse, VectorSearchRequest


def build_vector_search_stub(request: VectorSearchRequest) -> SearchStubResponse:
    return SearchStubResponse(
        mode="vector",
        query=request.query,
        session_id=request.session_id,
        results=[],
        meta={
            "top_k": request.top_k,
            "filters": request.filters or {},
            "status": "stub",
            "backend": "vector-db",
        },
    )


def build_graph_search_stub(request: GraphSearchRequest) -> SearchStubResponse:
    return SearchStubResponse(
        mode="graph",
        query=request.query,
        session_id=request.session_id,
        results=[],
        meta={
            "depth": request.depth,
            "params": request.params or {},
            "status": "stub",
            "backend": "knowledge-graph",
        },
    )
