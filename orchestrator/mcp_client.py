"""
MCP Client Manager — connects the orchestrator to all 6 MCP servers.
Uses SSE transport for server-sent events communication.
"""
import asyncio
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("mcp-client")

MCP_SERVERS = {
    "ingestion": os.getenv("MCP_INGESTION_URL", "http://localhost:8001"),
    "knowledge": os.getenv("MCP_KNOWLEDGE_URL", "http://localhost:8002"),
    "storage": os.getenv("MCP_STORAGE_URL", "http://localhost:8003"),
    "copilot": os.getenv("MCP_COPILOT_URL", "http://localhost:8004"),
    "maintenance": os.getenv("MCP_MAINTENANCE_URL", "http://localhost:8005"),
    "compliance": os.getenv("MCP_COMPLIANCE_URL", "http://localhost:8006"),
}


class MCPClientManager:
    """
    Manages HTTP connections to all MCP servers.
    Uses a simple REST-over-HTTP adapter since the MCP servers expose
    their tools via SSE. For the orchestrator, we call tools via direct
    HTTP POST to the MCP SSE endpoint.

    For production, use the official MCP Python client with SSE transport.
    This implementation uses a lightweight HTTP JSON-RPC style approach
    suitable for the hackathon prototype.
    """

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._health: dict[str, bool] = {}

    async def connect_all(self):
        """Initialize HTTP clients for all MCP servers."""
        for name, url in MCP_SERVERS.items():
            self._clients[name] = httpx.AsyncClient(
                base_url=url,
                timeout=120.0,  # Long timeout for OCR/embedding operations
            )
            logger.info(f"MCP client ready: {name} → {url}")

    async def disconnect_all(self):
        for client in self._clients.values():
            await client.aclose()

    async def health_check_all(self) -> dict[str, str]:
        """Check health of all MCP servers."""
        status = {}
        for name, client in self._clients.items():
            try:
                resp = await client.get("/health", timeout=5.0)
                status[name] = "ok" if resp.status_code == 200 else "error"
            except Exception as e:
                status[name] = f"unreachable: {str(e)[:50]}"
        return status

    async def call_tool(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call an MCP tool on a specific server.
        Sends a JSON-RPC style request to the server's tool endpoint.
        """
        if server not in self._clients:
            return {"error": f"Unknown MCP server: {server}"}

        client = self._clients[server]

        # JSON-RPC 2.0 format used by MCP protocol
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            response = await client.post("/call", json=payload)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return {"error": data["error"]}

            # Extract text content from MCP response
            result = data.get("result", {})
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                text = content[0]["text"]
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw_text": text}

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {server}/{tool_name}: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error calling {server}/{tool_name}: {e}", exc_info=True)
            return {"error": str(e)}

    def get_client(self, server: str) -> httpx.AsyncClient | None:
        return self._clients.get(server)
