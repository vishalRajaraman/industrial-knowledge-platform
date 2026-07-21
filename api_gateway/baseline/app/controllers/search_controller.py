from __future__ import annotations

import os
import httpx
from typing import Any

from ..schemas.search import GraphSearchRequest, SearchStubResponse, VectorSearchRequest

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")
_CLIENT_TIMEOUT = 20.0


def _normalize_hits(raw: Any) -> list[dict]:
    """Normalize different MCP response shapes into a list of hit dicts."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("results", "hits", "documents", "combined_sources"):
            if isinstance(raw.get(key), list):
                return raw[key]
    return []


async def build_vector_search_stub(request: VectorSearchRequest) -> SearchStubResponse:
    """Proxy the vector search to the MCP server's hybrid_search tool."""
    hits: list[dict] = []
    meta: dict[str, Any] = {"top_k": request.top_k, "filters": request.filters or {}, "backend": "mcp-vector"}

    try:
        async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT) as client:
            response = await client.post(
                f"{MCP_SERVER_URL}/tools/call",
                json={
                    "tool": "hybrid_search",
                    "arguments": {
                        "query": request.query,
                        "top_k": request.top_k or 8,
                        "filters": request.filters or {},
                    },
                },
            )
            if response.status_code == 200:
                data = response.json()
                hits = _normalize_hits(data.get("result", data))
                meta["status"] = "live"
            else:
                meta["status"] = "mcp_error"
                meta["mcp_status_code"] = response.status_code
    except httpx.ConnectError:
        meta["status"] = "mcp_offline"
    except Exception as exc:
        meta["status"] = "error"
        meta["error"] = str(exc)

    return SearchStubResponse(
        mode="vector",
        query=request.query,
        session_id=request.session_id,
        results=hits,
        meta=meta,
    )


async def build_graph_search_stub(request: GraphSearchRequest) -> SearchStubResponse:
    """Proxy the graph search to the MCP server's graph_search tool."""
    hits: list[dict] = []
    meta: dict[str, Any] = {"depth": request.depth, "params": request.params or {}, "backend": "mcp-graph"}

    try:
        async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT) as client:
            # Try the graph traversal tool
            response = await client.post(
                f"{MCP_SERVER_URL}/tools/call",
                json={
                    "tool": "graph_search",
                    "arguments": {
                        "query": request.query,
                        "depth": request.depth or 2,
                        "params": request.params or {},
                    },
                },
            )
            if response.status_code == 200:
                data = response.json()
                hits = _normalize_hits(data.get("result", data))
                meta["status"] = "live"
            else:
                # Fallback: try hybrid_search with graph mode
                fb = await client.post(
                    f"{MCP_SERVER_URL}/tools/call",
                    json={
                        "tool": "hybrid_search",
                        "arguments": {"query": request.query, "top_k": 8, "mode": "graph"},
                    },
                )
                if fb.status_code == 200:
                    data = fb.json()
                    hits = _normalize_hits(data.get("result", data))
                    meta["status"] = "live_fallback"
                else:
                    meta["status"] = "mcp_error"
    except httpx.ConnectError:
        meta["status"] = "mcp_offline"
    except Exception as exc:
        meta["status"] = "error"
        meta["error"] = str(exc)

    return SearchStubResponse(
        mode="graph",
        query=request.query,
        session_id=request.session_id,
        results=hits,
        meta=meta,
    )
