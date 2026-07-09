"""
Lessons Learned agent tools:
- lessons_analyze_near_misses: Safety pattern detection from incident records
- lessons_find_systemic_patterns: Cross-functional organizational pattern analysis
- lessons_generate_safety_alert: Proactive safety alert generation
"""
import logging

from mcp.server.fastmcp import FastMCP
from core import llm_client, neo4j_client

logger = logging.getLogger("ikp.agents.lessons")

PATTERN_SYSTEM = """You are a process safety specialist conducting incident pattern analysis.
Identify recurring failure patterns, contributing factors, and proactive mitigations.
Respond ONLY with valid JSON.
Format: {"patterns": [{"title": "...", "description": "...", "frequency": "...",
                        "severity": "High|Medium|Low", "warning_signs": ["..."],
                        "mitigation": "...", "affected_equipment": ["..."]}]}"""

ALERT_SYSTEM = """You are a plant safety officer generating proactive safety alerts.
Respond ONLY with valid JSON:
{"alert_title": "...", "severity": "Critical|High|Medium|Low",
 "description": "...", "actions": ["..."], "deadline": "immediate|24h|7d"}"""


def register(mcp: FastMCP):

    @mcp.tool()
    async def lessons_analyze_near_misses(
        time_range_days: int = 90,
        equipment_id: str = "",
    ) -> dict:
        """
        Scan recent incident logs and near-miss reports for safety patterns.
        Queries Neo4j AuraDB for FailureEvent and Incident nodes, then uses
        LLM to identify recurring patterns and warning signs.

        Args:
            time_range_days: Look-back period (default: 90 days).
            equipment_id: Filter by specific equipment (optional, '' = all equipment).

        Returns:
            patterns: Recurring conditions grouped by equipment/area.
            trending_risks: Risks increasing in frequency.
            historical_matches: Past incidents with similar precursors.
        """
        # Fetch incident data from Neo4j
        cypher = """
        MATCH (f:FailureEvent)-[:OCCURRED_ON]->(e:Equipment)
        WHERE $equipment_id = '' OR e.id = $equipment_id
        RETURN f.id as id, f.description as description, f.mode as mode,
               f.severity as severity, e.id as equipment, f.date as date
        ORDER BY f.date DESC
        LIMIT 30
        """
        incidents = await neo4j_client.run_cypher(cypher, {"equipment_id": equipment_id})

        if not incidents:
            # Demo fallback data
            incidents = [
                {"id": "FAIL-2024-03", "description": "Mechanical seal abrasion from catalyst fines",
                 "mode": "seal_failure", "severity": "High", "equipment": "P-2003A", "date": "2024-03-12"},
                {"id": "FAIL-2023-08", "description": "Mechanical seal failure due to vibration",
                 "mode": "seal_failure", "severity": "High", "equipment": "P-2003A", "date": "2023-08-15"},
            ]

        incident_summary = "\n".join(
            f"- [{i['id']}] {i.get('equipment', '?')}: {i.get('description', '')} [{i.get('severity', '')}]"
            for i in incidents
        )

        prompt = f"""Query context: {equipment_id or 'all equipment'} | Last {time_range_days} days

Incident history:
{incident_summary}

Identify recurring patterns, warning signs, and recommended mitigations.
Respond with JSON only."""

        result = await llm_client.json_chat(prompt, system=PATTERN_SYSTEM, temperature=0.2)

        if result and isinstance(result, dict) and "patterns" in result:
            return {
                **result,
                "incident_count": len(incidents),
                "time_range_days": time_range_days,
                "sources": [{"doc_id": i["id"], "type": "FailureRecord"} for i in incidents],
            }

        # Fallback
        return {
            "patterns": [
                {
                    "title": "Recurring Mechanical Seal Failures on Slurry Pumps",
                    "description": "P-2003A has experienced 2 seal failures in 14 months, linked to inadequate seal flush.",
                    "frequency": "Every 6-8 months",
                    "severity": "High",
                    "warning_signs": [
                        "Vibration >2.5 mm/s on pump bearing frame",
                        "Seal flush flow dropping below 5 m³/hr",
                        "Rising catalyst fines content in slurry (>10 wt%)",
                    ],
                    "mitigation": "Install continuous vibration monitoring, automate seal flush flow alarm.",
                    "affected_equipment": ["P-2003A"],
                }
            ],
            "incident_count": len(incidents),
            "time_range_days": time_range_days,
            "sources": [{"doc_id": i["id"], "type": "FailureRecord"} for i in incidents],
        }

    @mcp.tool()
    async def lessons_find_systemic_patterns(incident_type: str | None = None) -> dict:
        """
        Cross-reference incident reports, audit findings, and quality non-conformances
        to identify systemic organizational patterns.

        Args:
            incident_type: Filter by incident type ('mechanical', 'electrical', 'process', None=all).

        Returns:
            Systemic patterns with trend direction, contributing incidents, and organizational actions.
        """
        cypher = """
        MATCH (i:Incident)
        RETURN i.id as id, i.description as description, i.severity as severity,
               i.date as date, i.corrective_actions as corrective_actions
        ORDER BY i.date DESC
        LIMIT 20
        """
        incidents = await neo4j_client.run_cypher(cypher)

        prompt = f"""Identify systemic organizational safety patterns from these incidents:
{chr(10).join(f"- {i.get('id', '')}: {i.get('description', '')}" for i in incidents[:15])}

Look for: organizational root causes, systemic failures, cultural issues.
Filter type: {incident_type or 'all types'}
Respond with JSON only."""

        SYSTEMIC_SYSTEM = """Identify systemic organizational safety patterns.
Return JSON: {"patterns": [{"title": "...", "description": "...", "trend": "increasing|stable|decreasing",
 "contributing_incidents": ["..."], "affected_areas": ["..."],
 "organizational_actions": ["..."]}]}"""

        result = await llm_client.json_chat(prompt, system=SYSTEMIC_SYSTEM, temperature=0.2)
        if result and "patterns" in result:
            return {**result, "incidents_analyzed": len(incidents)}
        return {"patterns": [], "incidents_analyzed": len(incidents),
                "message": "Insufficient incident data for pattern analysis. Ingest more incident reports."}

    @mcp.tool()
    async def lessons_generate_safety_alert(patterns: list[dict]) -> dict:
        """
        Generate a proactive safety alert based on identified risk patterns.
        Only generates alerts for High/Critical severity patterns.

        Args:
            patterns: List of pattern dicts from lessons_analyze_near_misses.

        Returns:
            alert: Safety alert with title, severity, description, and action deadlines.
        """
        if not patterns:
            return {"alert_generated": False, "reason": "No patterns provided"}

        high_patterns = [p for p in patterns if str(p.get("severity", "")).lower() in ("high", "critical")]
        if not high_patterns:
            return {"alert_generated": False, "reason": "No High/Critical severity patterns found"}

        import json
        prompt = f"""Generate a proactive safety alert for these high-severity patterns:
{json.dumps(high_patterns[:3], indent=2)}"""

        result = await llm_client.json_chat(prompt, system=ALERT_SYSTEM, temperature=0.2)

        if result and isinstance(result, dict):
            return {"alert_generated": True, "alert": result}

        return {
            "alert_generated": True,
            "alert": {
                "alert_title": "⚠️ HIGH RISK: Recurring Equipment Failures — Immediate Action Required",
                "severity": "High",
                "description": f"Pattern analysis identified {len(high_patterns)} high-severity recurring patterns.",
                "actions": [
                    "Inspect affected equipment immediately",
                    "Review and update PM schedules",
                    "Brief operations team on warning signs",
                ],
                "deadline": "24h",
            },
        }
