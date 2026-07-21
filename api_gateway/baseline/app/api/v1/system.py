"""System stats endpoint — proxies to orchestrator for dashboard KPI data."""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
_CLIENT_TIMEOUT = 8.0


@router.get("/stats")
async def get_system_stats() -> dict[str, Any]:
    """Return live platform statistics from the orchestrator and MCP server."""
    stats: dict[str, Any] = {
        "orchestrator_status": "offline",
        "mcp_status": "offline",
        "graph_nodes": None,
        "graph_edges": None,
        "document_count": None,
    }

    try:
        async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT) as client:
            health_res = await client.get(f"{ORCHESTRATOR_URL}/health")
            if health_res.status_code == 200:
                health_data = health_res.json()
                stats["orchestrator_status"] = "online"
                mcp_servers = health_data.get("mcp_servers", {})
                all_ok = all(v for v in mcp_servers.values()) if mcp_servers else False
                stats["mcp_status"] = "online" if all_ok else "degraded"
                stats["mcp_servers"] = mcp_servers

        async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT) as client:
            graph_res = await client.get(f"{ORCHESTRATOR_URL}/graph/stats")
            if graph_res.status_code == 200:
                graph_data = graph_res.json()
                nodes = graph_data.get("nodes", {})
                node_result = nodes.get("result", nodes) if isinstance(nodes, dict) else nodes
                if isinstance(node_result, list):
                    stats["graph_nodes"] = sum(int(r.get("cnt", 0)) for r in node_result)
                    doc_row = next(
                        (r for r in node_result if "Document" in (r.get("lbls") or [])),
                        None,
                    )
                    stats["document_count"] = int(doc_row["cnt"]) if doc_row else None

                edges = graph_data.get("edges", {})
                edge_result = edges.get("result", edges) if isinstance(edges, dict) else edges
                if isinstance(edge_result, list) and edge_result:
                    stats["graph_edges"] = int(edge_result[0].get("total_edges", 0))
                elif isinstance(edge_result, dict):
                    stats["graph_edges"] = int(edge_result.get("total_edges", 0))
    except Exception as exc:
        stats["error"] = str(exc)

    return stats
