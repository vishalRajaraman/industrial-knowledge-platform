"""
Regulatory alignment tool — maps document content against
regulatory frameworks (OISD, Factory Act, PESO, API, IS standards).
"""
import json
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from core import llm_client

logger = logging.getLogger("ikp.knowledge.regulatory")

# Load regulatory ontology
_ONTOLOGY_PATH = Path(__file__).parent.parent.parent / "ontology" / "regulatory_frameworks.json"
_ONTOLOGY: dict = {}
if _ONTOLOGY_PATH.exists():
    with open(_ONTOLOGY_PATH) as f:
        _ONTOLOGY = json.load(f)


def register(mcp: FastMCP):

    @mcp.tool()
    async def align_regulatory(text: str, regulation: str) -> dict:
        """
        Map document content against a regulatory framework.
        Identifies which clauses are addressed and which are missing.

        Supported frameworks: OISD-154, OISD-STD-144, Factory_Act_1948,
        PESO, API-RP-686, IS-2825, ISO-55001, ISO-14224.

        Args:
            text: Procedure or document text to align.
            regulation: Target regulation identifier.

        Returns:
            Matched clauses, coverage percentage, and gap list.
        """
        framework_data = _ONTOLOGY.get("frameworks", {}).get(regulation, {})
        clauses = framework_data.get("clauses", [framework_data.get("name", regulation)])
        clauses_str = "\n".join(f"- {c}" for c in clauses[:20])

        prompt = f"""Analyse how well this document text covers the following {regulation} clauses:

CLAUSES:
{clauses_str}

DOCUMENT TEXT:
{text[:6000]}

For each clause, state: COVERED / PARTIALLY_COVERED / NOT_COVERED with brief evidence.
Respond with JSON:
{{"coverage": [{{"clause": "...", "status": "COVERED|PARTIALLY_COVERED|NOT_COVERED", "evidence": "..."}}],
 "overall_coverage_pct": 0-100,
 "gaps": ["list of uncovered clause IDs"]}}"""

        result = await llm_client.json_chat(prompt, temperature=0.1)

        if result and "coverage" in result:
            return {**result, "regulation": regulation, "clauses_checked": len(clauses)}

        # Structured fallback
        return {
            "regulation": regulation,
            "clauses_checked": len(clauses),
            "coverage": [{"clause": c, "status": "UNKNOWN", "evidence": ""} for c in clauses],
            "overall_coverage_pct": 0,
            "gaps": clauses,
            "note": "LLM alignment failed — check LLM provider connectivity.",
        }
