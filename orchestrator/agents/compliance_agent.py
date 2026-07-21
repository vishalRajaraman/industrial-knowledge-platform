"""Compliance Agent — regulatory gap detection and audit preparation."""
import logging
from typing import Any

from mcp_client import MCPClientManager

logger = logging.getLogger("compliance-agent")


class ComplianceAgent:
    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager

    async def run(self, query: str, regulation: str | None) -> dict[str, Any]:
        """Execute compliance gap detection workflow."""
        logger.info(f"Compliance agent processing query for regulation: {regulation}")
        
        # If no explicit regulation was extracted, try to guess from query or ask for clarification
        if not regulation:
            # Fallback to Copilot for general compliance queries if specific reg isn't identified
            copilot_res = await self.mcp.call_tool("copilot", "expand_query", {"query": query, "user_role": "auditor"})
            expanded = copilot_res.get("expanded_query", query)
            
            search_res = await self.mcp.call_tool("copilot", "hybrid_search", {
                "query": expanded, "entities": ["compliance", "regulation"], "top_k": 5
            })
            
            answer_res = await self.mcp.call_tool("copilot", "generate_answer", {
                "query": query, "context_chunks": search_res.get("results", []), "user_role": "auditor"
            })
            
            return {
                "answer": answer_res.get("answer", "Could not find compliance information."),
                "sources": answer_res.get("sources", []),
                "confidence": 0.7,
                "metadata": {"type": "general_compliance"}
            }

        # Specific gap detection requested
        gap_res = await self.mcp.call_tool("compliance", "comply_detect_gaps", {
            "regulation": regulation,
            "scope_query": query
        })
        
        if "error" in gap_res:
            return {"answer": f"Error checking compliance: {gap_res['error']}", "sources": [], "confidence": 0}
            
        gaps = gap_res.get("gaps", [])
        
        if not gaps:
            return {
                "answer": f"No compliance gaps detected for {regulation} based on current documentation.",
                "sources": [],
                "confidence": 0.9,
                "metadata": {"type": "gap_analysis"}
            }
            
        answer = f"### Compliance Gap Analysis: {regulation}\n\n"
        answer += "The following potential compliance gaps were identified:\n\n"
        
        for gap in gaps:
            severity = gap.get("severity", "Medium")
            icon = "🔴" if severity.lower() == "high" else "🟡" if severity.lower() == "medium" else "🟢"
            answer += f"{icon} **{severity} Priority:** Clause {gap.get('clause', 'Unknown')}\n"
            answer += f"   - **Requirement:** {gap.get('requirement', '')}\n"
            answer += f"   - **Current State:** {gap.get('current_state', 'No documentation found')}\n"
            answer += f"   - **Recommendation:** {gap.get('recommendation', 'Address immediately')}\n\n"
            
        # Audit compilation
        audit_res = await self.mcp.call_tool("compliance", "comply_compile_audit", {
            "regulation": regulation
        })
        
        if audit_res.get("package_url"):
            answer += f"\n[📥 Download complete audit evidence package]({audit_res['package_url']})"
            
        return {
            "answer": answer,
            "sources": gap_res.get("sources", []),
            "confidence": 0.85,
            "metadata": {"type": "gap_analysis", "gap_count": len(gaps), "results": gap_res}
        }
