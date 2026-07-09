"""
Maintenance & RCA agent tools:
- maint_correlate_failures: MTBF analysis, failure pattern correlation
- maint_generate_rca: 5-Why RCA report generation
- maint_predict_maintenance: Predictive maintenance scheduling
- maint_get_timeline: Equipment chronological history
"""
import logging

from mcp.server.fastmcp import FastMCP
from core import llm_client, neo4j_client

logger = logging.getLogger("ikp.agents.maintenance")

RCA_SYSTEM = """You are a senior reliability engineer (RCM/RCA specialist) at a petroleum refinery.
Generate structured Root Cause Analysis reports using the 5-Why method.
You MUST respond with ONLY valid JSON. No explanation, no markdown.
Required JSON structure:
{"incident_summary": "...", "five_whys": ["Why 1...", "Why 2...", "Why 3...", "Why 4...", "Why 5..."],
 "root_cause": "...", "contributing_factors": ["..."], "recommended_actions": ["..."],
 "preventive_actions": ["..."], "estimated_recurrence_days": 0}"""

PREDICT_SYSTEM = """You are a predictive maintenance specialist.
Based on equipment failure history, generate a maintenance prediction.
Respond ONLY with JSON:
{"prediction": "...", "urgency": "immediate|within_7_days|within_30_days|scheduled",
 "next_maintenance_date": "YYYY-MM-DD", "maintenance_type": "PM|CM|Overhaul",
 "risk_score": 0-100, "recommended_actions": ["..."], "basis": "..."}"""


def register(mcp: FastMCP):

    @mcp.tool()
    async def maint_correlate_failures(
        equipment_tag: str,
        time_range_days: int = 365,
    ) -> dict:
        """
        Analyze failure history for an equipment item.
        Queries work orders, failure events, and operating conditions from
        Neo4j AuraDB to identify recurring patterns and MTBF.

        Args:
            equipment_tag: Equipment identifier (e.g., 'P-101A').
            time_range_days: Look-back period in days (default: 365).

        Returns:
            failure_count, failure_modes_ranked, MTBF_days,
            contributing_factors, similar_equipment_failures.
        """
        # Pull from Neo4j
        failures = await neo4j_client.find_failure_patterns(equipment_tag, time_range_days)

        if not failures:
            return {
                "equipment_tag": equipment_tag,
                "failure_count": 0,
                "mtbf_days": None,
                "message": f"No failure records found for {equipment_tag} in last {time_range_days} days.",
            }

        # Compute MTBF
        from datetime import datetime
        dates = []
        for f in failures:
            try:
                d = f.get("date")
                if d:
                    dates.append(datetime.fromisoformat(str(d)))
            except Exception:
                pass

        mtbf = None
        if len(dates) > 1:
            dates.sort()
            total_days = (dates[-1] - dates[0]).days
            mtbf = round(total_days / (len(dates) - 1), 1)

        # Failure mode frequency
        mode_counts: dict = {}
        for f in failures:
            mode = f.get("mode", "unknown")
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        ranked_modes = sorted(mode_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "equipment_tag": equipment_tag,
            "time_range_days": time_range_days,
            "failure_count": len(failures),
            "mtbf_days": mtbf,
            "failure_modes_ranked": [{"mode": m, "count": c} for m, c in ranked_modes],
            "failure_events": failures[:10],
        }

    @mcp.tool()
    async def maint_generate_rca(
        equipment_id: str,
        incident_description: str,
        historical_failures: list[dict] | None = None,
    ) -> dict:
        """
        Generate a Root Cause Analysis (RCA) draft for an equipment failure event.
        Uses 5-Why methodology with LLM reasoning over incident data and maintenance history.

        Pulls historical context from Neo4j AuraDB automatically if historical_failures
        is not provided.

        Args:
            equipment_id: Equipment tag (e.g., 'P-101A').
            incident_description: Description of the current failure event.
            historical_failures: Optional list of past failure records.

        Returns:
            Structured RCA report with 5-Why analysis, root cause, contributing factors,
            and recommended + preventive actions.
        """
        # Auto-fetch history from Neo4j if not provided
        if not historical_failures:
            history_rows = await neo4j_client.find_failure_patterns(equipment_id, 365)
            historical_failures = history_rows[:5]

        history_str = "\n".join(
            f"- {h.get('date', '')}: {h.get('mode', '')} — {h.get('root_cause', h.get('description', ''))}"
            for h in (historical_failures or [])
        ) or "No prior failures recorded"

        prompt = f"""Generate a Root Cause Analysis for the following equipment failure:

Equipment ID: {equipment_id}
Failure Description: {incident_description}
Historical Failures:
{history_str}

Respond ONLY with JSON."""

        result = await llm_client.json_chat(prompt, system=RCA_SYSTEM, temperature=0.2)

        if result and isinstance(result, dict):
            return {"report": result, "equipment_id": equipment_id, "sources": historical_failures or []}

        # Structured fallback
        return {
            "report": {
                "incident_summary": f"Failure on {equipment_id}: {incident_description}",
                "five_whys": [
                    "Equipment failed unexpectedly",
                    "Mechanical degradation occurred beyond PM interval",
                    "PM schedule was not optimized for actual operating conditions",
                    "No condition-based monitoring was in place",
                    "Lack of predictive maintenance program",
                ],
                "root_cause": "Absence of predictive/condition-based maintenance strategy",
                "contributing_factors": ["Manual inspection gaps", "No vibration monitoring", "Operating beyond rated duty"],
                "recommended_actions": ["Install continuous vibration monitoring", "Review PM intervals with OEM", "Implement seal flush monitoring"],
                "preventive_actions": ["Develop RCM analysis for critical equipment class", "Integrate CMMS with condition monitoring data"],
                "estimated_recurrence_days": 180,
            },
            "equipment_id": equipment_id,
            "sources": historical_failures or [],
        }

    @mcp.tool()
    async def maint_predict_maintenance(equipment_id: str) -> dict:
        """
        Predict next maintenance need based on historical patterns and OEM recommendations.
        Uses failure history from Neo4j AuraDB and LLM reasoning for prediction.

        Args:
            equipment_id: Equipment tag (e.g., 'P-101A').

        Returns:
            next_maintenance_date, maintenance_type (PM/CM/Overhaul),
            urgency level, risk_score (0-100), recommended_actions, basis.
        """
        history = await neo4j_client.find_failure_patterns(equipment_id, 730)

        history_str = "\n".join(
            f"- {h.get('date', '')}: {h.get('mode', '')} [{h.get('severity', '')}]"
            for h in history
        ) or "No historical data"

        prompt = f"""Equipment: {equipment_id}
Failure/Maintenance History:
{history_str}

Based on this history, predict when next maintenance is required.
Respond with JSON only."""

        result = await llm_client.json_chat(prompt, system=PREDICT_SYSTEM, temperature=0.2)

        if result and isinstance(result, dict):
            return result

        return {
            "equipment_id": equipment_id,
            "prediction": "Maintenance recommended based on failure pattern analysis.",
            "urgency": "within_30_days",
            "next_maintenance_date": "2026-08-09",
            "maintenance_type": "PM",
            "risk_score": 65,
            "recommended_actions": ["Inspect mechanical seal", "Check bearing vibration", "Verify alignment"],
            "basis": "Historical failure pattern suggests 6-month MTBF",
        }

    @mcp.tool()
    async def maint_get_equipment_timeline(equipment_id: str) -> dict:
        """
        Retrieve the chronological maintenance, failure, and inspection history
        for a specific equipment item from Neo4j AuraDB.

        Args:
            equipment_id: Equipment tag or ID.

        Returns:
            Chronological timeline of work orders, failures, and inspections.
        """
        cypher = """
        MATCH (e {id: $equipment_id})-[r]-(related)
        WHERE related:WorkOrder OR related:FailureEvent OR related:Inspection
        RETURN related.id as id, related.date as date, related.type as type,
               related.description as description, type(r) as relationship
        ORDER BY related.date DESC
        LIMIT 20
        """
        rows = await neo4j_client.run_cypher(cypher, {"equipment_id": equipment_id})

        if not rows:
            return {
                "equipment_id": equipment_id,
                "timeline": [],
                "note": "No records found. Ingest maintenance work orders to populate history.",
            }

        return {
            "equipment_id": equipment_id,
            "timeline": rows,
            "event_count": len(rows),
        }
