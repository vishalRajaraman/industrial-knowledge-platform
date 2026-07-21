import json
import logging
import os
import httpx
from typing import Any

from mcp_client import MCPClientManager

logger = logging.getLogger("orchestrator.router")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "mistralai/mistral-medium-3.5-128b")

class RouterAgent:
    """
    Supervisor Agent that analyzes the user's raw query and classifies intent.
    Routes queries to specific agent domains (KNOWLEDGE_QUERY, COMPLIANCE_QUERY, DIRECT_SEARCH).
    """

    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager

    async def classify(self, query: str) -> dict[str, Any]:
        """
        Use an LLM to classify intent and extract basic entities.
        """
        if not NVIDIA_API_KEY:
            logger.warning("NVIDIA_API_KEY not set. Defaulting to KNOWLEDGE_QUERY.")
            return {"category": "KNOWLEDGE_QUERY", "entities_detected": []}

        system_prompt = (
            "You are a routing agent for an industrial plant intelligence platform. "
            "Analyze the user's query and classify it into exactly one of these categories: "
            "1. 'COMPLIANCE_QUERY': Questions about regulations, standards, audits, gaps (e.g., OISD, Factory Act). "
            "2. 'DIRECT_SEARCH': Requests explicitly asking for a file, P&ID, manual, or drawing without needing a summarized answer. "
            "3. 'KNOWLEDGE_QUERY': General questions about operations, troubleshooting, equipment status, or how things work. "
            "Also, extract any mentioned equipment tags (e.g., P-101A, TK-200) into a list. "
            "Respond ONLY with valid JSON in this format: {\"category\": \"...\", \"entities_detected\": [\"...\"]}"
        )

        headers = {
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "temperature": 0.1,
            "max_tokens": 512,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{NVIDIA_BASE_URL}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Strip markdown fences if present
                content = content.strip()
                if content.startswith("```"):
                    parts = content.split("```")
                    if len(parts) >= 3:
                        inner = parts[1]
                        if inner.startswith("json"):
                            inner = inner[4:]
                        content = inner.strip()
                        
                return json.loads(content)
        except Exception as e:
            logger.error(f"Router LLM classification failed: {e}")
            return {"category": "KNOWLEDGE_QUERY", "entities_detected": []}
