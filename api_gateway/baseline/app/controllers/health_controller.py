from ..schemas.health import HealthResponse


def build_health_response() -> HealthResponse:
    return HealthResponse(
        dependencies={
            "vector_search": False,
            "graph_search": False,
        }
    )
