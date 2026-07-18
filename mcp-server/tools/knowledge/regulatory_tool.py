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

def load_ontologies() -> dict:
    ontology_dir = Path(__file__).parent.parent.parent / "ontology"
    ontologies = {}
    if ontology_dir.exists():
        for file in ontology_dir.glob("*.json"):
            # skip asset types
            if file.name == "asset_types.json": continue
            try:
                with open(file) as f:
                    data = json.load(f)
                    if "id" in data:
                        ontologies[data["id"]] = data
            except Exception as e:
                logger.warning(f"Failed to load ontology {file.name}: {e}")
    return ontologies

_ONTOLOGIES = load_ontologies()

def register(mcp: FastMCP):

    @mcp.tool()
    async def align_regulations(text: str, frameworks: list[str]) -> dict:
        """
        Map document content against multiple regulatory frameworks simultaneously.
        Identifies which clauses are addressed and which are missing.

        Supported frameworks: OISD-154, OISD-STD-144, Factory_Act_1948,
        PESO, API-RP-686, API-RP-580, OISD-244.

        Args:
            text: Procedure or document text to align.
            frameworks: List of target regulation identifiers.

        Returns:
            JSON containing covered_standards and gaps.
        """
        clauses_str_parts = []
        total_clauses = 0
        for fw in frameworks:
            fw_data = _ONTOLOGIES.get(fw)
            if not fw_data:
                continue
            clauses = fw_data.get("clauses", [])
            total_clauses += len(clauses)
            clauses_str_parts.append(f"--- {fw} ---")
            for c in clauses:
                clauses_str_parts.append(f"- {fw} Clause {c}")
                
        if not clauses_str_parts:
            return {"error": "No valid frameworks provided or no clauses found."}

        clauses_str = "\n".join(clauses_str_parts)

        prompt = f"""Analyse how well this document text covers the following regulatory clauses:

CLAUSES:
{clauses_str}

DOCUMENT TEXT:
{text[:8000]}

For each clause, determine if it is COVERED or NOT_COVERED by the text.
Respond with JSON matching this exact structure:
{{
  "covered_standards": ["List of completely or partially covered clauses (e.g. 'API RP 686 Section 5.3')"],
  "gaps": ["List of NOT covered clauses with brief reason (e.g. 'OISD-STD-144 Clause 12 - annual thermal imaging not mentioned')"]
}}"""

        result = await llm_client.json_chat(prompt, temperature=0.1)

        if result and "covered_standards" in result:
            return result

        # Structured fallback
        return {
            "covered_standards": [],
            "gaps": ["LLM evaluation failed or timed out"],
            "note": "LLM alignment failed — check LLM provider connectivity."
        }
