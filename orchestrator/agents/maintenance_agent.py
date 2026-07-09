"""Maintenance Agent — predictive maintenance, RCA, and equipment timelines."""
import logging
from typing import Any

from mcp_client import MCPClientManager

logger = logging.getLogger("maintenance-agent")


class MaintenanceAgent:
    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager

    async def run(self, query: str, equipment_ids: list[str] | str | None) -> dict[str, Any]:
        """Execute maintenance or RCA workflows."""
        if isinstance(equipment_ids, str):
            equipment_ids = [equipment_ids]
            
        logger.info(f"Maintenance agent processing query for equipment: {equipment_ids}")
        
        if not equipment_ids:
            return {
                "answer": "Please specify the equipment tag (e.g., P-2003A) for maintenance analysis.",
                "sources": [],
                "confidence": 0.0
            }
            
        eq_id = equipment_ids[0]  # Focus on primary equipment
        
        # Check if RCA request
        is_rca = any(term in query.lower() for term in ["rca", "root cause", "why did it fail"])
        
        if is_rca:
            # Generate RCA Report
            rca_res = await self.mcp.call_tool("maintenance", "generate_rca_report", {
                "equipment_id": eq_id,
                "incident_description": query
            })
            
            if "error" in rca_res:
                return {"answer": f"Error generating RCA: {rca_res['error']}", "sources": [], "confidence": 0}
                
            report = rca_res.get("report", {})
            sources = rca_res.get("sources", [])
            
            # Format report into readable markdown
            answer = f"### Root Cause Analysis Draft: {eq_id}\n\n"
            answer += f"**Incident:** {report.get('incident_summary', 'Unknown')}\n\n"
            answer += "#### 5-Why Analysis\n"
            for i, why in enumerate(report.get("five_whys", [])):
                answer += f"{i+1}. {why}\n"
                
            answer += f"\n**Likely Root Cause:** {report.get('root_cause', 'Requires further investigation')}\n\n"
            answer += "#### Recommended Actions\n"
            for action in report.get("recommended_actions", []):
                answer += f"- {action}\n"
                
            return {
                "answer": answer,
                "sources": sources,
                "confidence": 0.85,
                "metadata": {"type": "rca", "raw_report": report}
            }
            
        else:
            # Predictive / History Request
            timeline_res = await self.mcp.call_tool("maintenance", "get_equipment_timeline", {
                "equipment_id": eq_id
            })
            
            pred_res = await self.mcp.call_tool("maintenance", "predict_maintenance", {
                "equipment_id": eq_id
            })
            
            timeline = timeline_res.get("timeline", [])
            prediction = pred_res.get("prediction", "No prediction available.")
            
            answer = f"### Maintenance Intelligence for {eq_id}\n\n"
            answer += f"**Prediction:** {prediction}\n\n"
            answer += "#### Recent History\n"
            
            for event in timeline[:5]:
                answer += f"- **{event.get('date', 'Unknown')}**: {event.get('description', '')} ({event.get('type', '')})\n"
                
            return {
                "answer": answer,
                "sources": [{"doc_id": "graph-db", "type": "timeline"}],
                "confidence": 0.9,
                "metadata": {"type": "history_predict", "event_count": len(timeline)}
            }
