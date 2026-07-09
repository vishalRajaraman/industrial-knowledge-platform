"""
Graph-specific search tools — find_failure_patterns, check_compliance_coverage.
"""
from mcp.server.fastmcp import FastMCP
from core import neo4j_client


def register(mcp: FastMCP):

    @mcp.tool()
    async def find_failure_patterns(equipment_tag: str, days: int = 365) -> dict:
        """
        Query Neo4j AuraDB for historical failure patterns on a specific equipment.
        Returns all FailureEvent nodes within the time range, with modes and severities.

        Args:
            equipment_tag: Equipment identifier (e.g., 'P-101A').
            days: Look-back period in days (default: 365).

        Returns:
            failure_events list with dates, modes, severities, and root causes.
        """
        rows = await neo4j_client.find_failure_patterns(equipment_tag, days)
        return {
            "equipment_tag": equipment_tag,
            "time_range_days": days,
            "failure_count": len(rows),
            "failure_events": rows,
        }

    @mcp.tool()
    async def check_compliance_coverage(framework: str = "OISD_154") -> dict:
        """
        Check which regulatory clauses are covered in the knowledge graph
        (i.e., have equipment/documents linked to them).

        Args:
            framework: Regulatory framework identifier (e.g., 'OISD_154', 'Factory_Act_1948').

        Returns:
            Clause-level coverage with equipment/document counts per clause.
        """
        rows = await neo4j_client.check_compliance_coverage(framework)
        covered = [r for r in rows if r.get("coverage_count", 0) > 0]
        return {
            "framework": framework,
            "total_clauses": len(rows),
            "covered_clauses": len(covered),
            "coverage_pct": round(len(covered) / max(len(rows), 1) * 100, 1),
            "clauses": rows,
        }
