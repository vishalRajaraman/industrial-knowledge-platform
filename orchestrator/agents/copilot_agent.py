"""Copilot Agent — general knowledge querying with RAG over graph + vector."""
import logging
from typing import Any

from mcp_client import MCPClientManager

logger = logging.getLogger("copilot-agent")


class CopilotAgent:
    def __init__(self, mcp_manager: MCPClientManager):
        self.mcp = mcp_manager

    async def run(self, query: str, entities: list[str], user_role: str) -> dict[str, Any]:
        """Execute knowledge retrieval and answer generation."""
        logger.info(f"Copilot processing query: {query} (Entities: {entities})")
        
        # 1. Expand Query (Server 4)


        expand_res = await self.mcp.call_tool("copilot", "expand_query", {"user_query": query, "user_role": user_role})
        expanded_query = expand_res.get("expanded_query", query)
        
        # 2. Hybrid Search (Server 4)
        search_res = await self.mcp.call_tool("copilot", "hybrid_search", {
            "query": expanded_query,
            "equipment_tags": entities,
            "top_k": 5
        })
        
        context_chunks = search_res.get("combined_sources", [])
        
        if not context_chunks:
            return {
                "answer": "I couldn't find any relevant information in the knowledge base to answer your question.",
                "sources": [],
                "confidence": 0.0,
                "metadata": {"expanded_query": expanded_query}
            }
            
        # 3. Generate Answer (Server 4)
        answer_res = await self.mcp.call_tool("copilot", "rag_answer", {
            "query": query,
            "context_chunks": context_chunks,
            "user_role": user_role
        })
        
        # 4. Score Confidence (Server 4)
        conf_res = await self.mcp.call_tool("copilot", "score_confidence", {
            "answer": answer_res.get("answer", ""),
            "sources": answer_res.get("sources", [])
        })
        
        return {
            "answer": answer_res.get("answer", "Error generating answer."),
            "sources": answer_res.get("sources", []),
            "confidence": conf_res.get("score", 0.0),
            "metadata": {
                "expanded_query": expanded_query,
                "context_used": len(context_chunks),
                "confidence_details": conf_res.get("details", {})
            }
        }
