"""Router Agent — classifies queries and dispatches to sub-agents using Ollama."""
import logging
import os
import sys
from typing import Any

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../shared"))
import ollama_client as ollama

logger = logging.getLogger("router-agent")

SYSTEM_PROMPT = """You are the Industrial Knowledge Intelligence Router Agent.

Analyze the user query and classify it into exactly ONE category:

KNOWLEDGE_QUERY    — General questions about equipment, procedures, documents, specifications, SOPs
MAINTENANCE_QUERY  — Equipment failures, maintenance, RCA, vibration, bearing, seal issues
COMPLIANCE_QUERY   — Regulatory requirements, audit prep, compliance gaps, standards (OISD, ISO, etc.)
LESSONS_QUERY      — Safety incidents, near-misses, historical patterns, warnings
INGESTION          — New document to process (triggered programmatically)

You MUST respond with ONLY valid JSON. No explanation. No markdown.
Required keys: category, reasoning, entities_detected (list), intent"""

CLASSIFY_PROMPT = """Classify this query and extract any equipment tags or regulation names mentioned:

Query: {query}

Respond ONLY with JSON like:
{{"category": "MAINTENANCE_QUERY", "reasoning": "User asks about pump failure", "entities_detected": ["P-2003A"], "intent": "understand seal failure root cause"}}"""


class RouterAgent:
    def __init__(self, mcp_manager):
        self.mcp = mcp_manager

    async def classify(self, query: str) -> dict[str, Any]:
        """Classify a user query into a routing category using Ollama."""
        import asyncio
        loop = asyncio.get_event_loop()

        def _classify():
            result = ollama.json_chat(
                prompt=CLASSIFY_PROMPT.format(query=query),
                system=SYSTEM_PROMPT,
                temperature=0.0,        # Zero temp for deterministic routing
            )

            if not result or not isinstance(result, dict):
                logger.warning(f"Router returned invalid JSON, defaulting to KNOWLEDGE_QUERY")
                return {
                    "category": "KNOWLEDGE_QUERY",
                    "reasoning": "Classification failed, defaulting",
                    "entities_detected": [],
                    "intent": query,
                }

            # Validate category
            valid_categories = {"KNOWLEDGE_QUERY", "MAINTENANCE_QUERY", "COMPLIANCE_QUERY", "LESSONS_QUERY", "INGESTION"}
            if result.get("category") not in valid_categories:
                result["category"] = "KNOWLEDGE_QUERY"

            return result

        try:
            return await loop.run_in_executor(None, _classify)
        except Exception as e:
            logger.error(f"Router error: {e}")
            return {
                "category": "KNOWLEDGE_QUERY",
                "reasoning": f"Router error: {e}",
                "entities_detected": [],
                "intent": query,
            }
