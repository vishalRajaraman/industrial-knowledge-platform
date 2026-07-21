"""Lessons Learned Agent — safety patterns and near-miss analysis."""
import logging
from typing import Any

from mcp_client import MCPClientManager

logger = logging.getLogger("lessons-agent")


class LessonsAgent:
    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager

    async def run(self, query: str) -> dict[str, Any]:
        """Execute lessons learned and pattern analysis workflow."""
        logger.info("Lessons agent processing query.")
        
        # Analyze near misses / incident patterns
        analysis_res = await self.mcp.call_tool("compliance", "lessons_analyze_near_misses", {
            "query": query
        })
        
        if "error" in analysis_res:
            return {"answer": f"Error analyzing patterns: {analysis_res['error']}", "sources": [], "confidence": 0}
            
        patterns = analysis_res.get("patterns", [])
        
        if not patterns:
            return {
                "answer": "No clear historical patterns or near-misses found related to this query.",
                "sources": [],
                "confidence": 0.8,
                "metadata": {"type": "lessons"}
            }
            
        answer = "### Historical Safety & Incident Patterns\n\n"
        answer += "Based on analysis of incident reports and near-miss logs:\n\n"
        
        for pattern in patterns:
            answer += f"#### ⚠️ {pattern.get('title', 'Identified Pattern')}\n"
            answer += f"**Observation:** {pattern.get('description', '')}\n"
            answer += f"**Frequency:** {pattern.get('frequency', 'Unknown')}\n"
            answer += f"**Key Warning Signs:**\n"
            for sign in pattern.get("warning_signs", []):
                answer += f"- {sign}\n"
            answer += f"**Proactive Mitigation:** {pattern.get('mitigation', '')}\n\n"
            
        # Check if we should generate an alert
        if any(p.get("severity", "").lower() == "high" for p in patterns):
            alert_res = await self.mcp.call_tool("compliance", "lessons_generate_safety_alert", {
                "patterns": patterns
            })
            if alert_res.get("alert_generated"):
                answer += f"\n> 🚨 **SYSTEM ACTION:** High severity pattern detected. A proactive safety alert has been queued for the operations team."
                
        return {
            "answer": answer,
            "sources": analysis_res.get("sources", []),
            "confidence": 0.88,
            "metadata": {"type": "lessons", "pattern_count": len(patterns)}
        }
