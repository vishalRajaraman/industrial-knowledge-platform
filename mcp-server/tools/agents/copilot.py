"""
RAG Copilot agent tools — rag_answer, cite_sources, score_confidence.
The primary user-facing conversational AI powered by Groq/Ollama.
"""
import logging

from mcp.server.fastmcp import FastMCP
from core import llm_client

logger = logging.getLogger("ikp.agents.copilot")

ANSWER_SYSTEM = """You are InduStreakAI — the Industrial Knowledge Copilot for petroleum refineries
and process plants. Answer questions ONLY from the provided context. Do not hallucinate facts.

Rules:
1. Be precise and use technical terminology appropriate for the industrial domain.
2. Always reference source document IDs where possible: [DOC-ID].
3. Format answers with headings and bullet points for clarity.
4. For safety-critical topics, add a ⚠️ safety note.
5. If context is insufficient, say: "Insufficient documentation found — please ingest the relevant manual."
6. Include confidence indicators: HIGH / MEDIUM / LOW based on source quality."""


def register(mcp: FastMCP):

    @mcp.tool()
    async def rag_answer(
        query: str,
        context_chunks: list[dict],
        graph_context: dict | None = None,
        user_role: str = "operator",
    ) -> dict:
        """
        Generate a grounded, cited answer using retrieved context.
        Uses the LLM (Groq → Google AI Studio → Ollama fallback) to synthesize
        information from multiple source documents.

        Always call hybrid_search first to get context_chunks before calling this tool.

        Args:
            query: The user's original question.
            context_chunks: Retrieved text chunks from hybrid_search.
            graph_context: Optional knowledge graph context from kg_traversal.
            user_role: User role for answer depth calibration (operator/engineer/manager).

        Returns:
            answer: Generated response with source citations.
            sources: List of source documents with doc_id and scores.
            confidence: Float 0-1 indicating answer reliability.
        """
        if not context_chunks:
            return {
                "answer": "No relevant documentation found. Please ensure relevant manuals or reports have been ingested into the knowledge base.",
                "sources": [],
                "confidence": 0.0,
            }

        context_str = "\n\n---\n\n".join(
            f"[{c.get('filename', c.get('doc_id', '?'))} | {c.get('section_title', '')} | score={c.get('score', 0):.2f}]\n{c.get('text', '')}"
            for c in context_chunks[:8]
        )

        graph_str = ""
        if graph_context:
            graph_str = f"\n\nKnowledge Graph Context:\n{str(graph_context)[:2000]}"

        prompt = (
            f"You are answering a question for a {user_role} at an industrial refinery.\n\n"
            f"Retrieved context from knowledge base:\n{context_str}{graph_str}\n\n"
            f"Question: {query}\n\n"
            f"Provide a precise technical answer citing document IDs in [brackets]."
        )

        answer_text = await llm_client.chat(prompt=prompt, system=ANSWER_SYSTEM, temperature=0.3)

        sources = []
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        
        for c in context_chunks:
            fname = c.get("filename") or c.get("doc_id", "")
            if uuid_pattern.match(fname):
                fname = "Unknown Document"
                
            sources.append({
                "doc_id": fname,
                "section_title": c.get("section_title", ""),
                "doc_type": c.get("doc_type", ""),
                "score": round(float(c.get("score", 0)), 4),
            })

        # Confidence based on source scores
        if sources:
            avg_score = sum(s["score"] for s in sources) / len(sources)
            confidence = round(min(avg_score + len(sources) * 0.03, 1.0), 3)
        else:
            confidence = 0.1

        return {
            "answer": answer_text,
            "sources": sources,
            "confidence": confidence,
            "source_count": len(sources),
        }

    @mcp.tool()
    async def cite_sources(answer: str, source_chunks: list[dict]) -> dict:
        """
        Attach inline source citations to each claim in the answer.
        Maps statements to their originating documents with [n] reference markers.

        Args:
            answer: The generated answer text.
            source_chunks: List of source chunk dicts from hybrid_search.

        Returns:
            cited_answer: Answer with [1], [2]... inline citations.
            bibliography: Numbered list of source documents.
        """
        bibliography = []
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        
        for i, chunk in enumerate(source_chunks, 1):
            did = chunk.get("doc_id", "")
            if uuid_pattern.match(did):
                did = "Unknown Document"
                
            bibliography.append({
                "ref": i,
                "doc_id": did,
                "section": chunk.get("section_title", ""),
                "doc_type": chunk.get("doc_type", ""),
                "score": round(float(chunk.get("score", 0)), 3),
            })

        # Simple citation: append bibliography to answer
        bib_text = "\n\n**References:**\n" + "\n".join(
            f"[{b['ref']}] {b['doc_id']} — {b['section']} ({b['doc_type']})"
            for b in bibliography
        )
        cited_answer = answer + bib_text

        return {
            "cited_answer": cited_answer,
            "bibliography": bibliography,
            "citation_count": len(bibliography),
        }

    @mcp.tool()
    async def score_confidence(answer: str, sources: list[dict]) -> dict:
        """
        Score answer reliability based on source count and similarity scores.
        Returns a 0-1 confidence score with breakdown.

        Args:
            answer: The generated answer text.
            sources: List of source dicts with 'score' fields.

        Returns:
            confidence: Float 0-1.
            level: 'HIGH' (>0.8) / 'MEDIUM' (0.5-0.8) / 'LOW' (<0.5).
            details: Breakdown of scoring factors.
        """
        if not sources:
            return {"confidence": 0.2, "level": "LOW", "details": {"source_count": 0}}

        avg_score = sum(float(s.get("score", 0)) for s in sources) / len(sources)
        source_bonus = min(len(sources) * 0.04, 0.15)
        confidence = round(min(avg_score + source_bonus, 1.0), 3)
        level = "HIGH" if confidence >= 0.8 else ("MEDIUM" if confidence >= 0.5 else "LOW")

        return {
            "confidence": confidence,
            "level": level,
            "details": {
                "source_count": len(sources),
                "avg_retrieval_score": round(avg_score, 3),
                "source_bonus": source_bonus,
            },
        }

    @mcp.tool()
    async def enhance_user_query(query: str) -> dict:
        """
        Enhance a short user query into a fully-formed, professional question
        using the nvidia/nemotron-4-340b-instruct model.

        Args:
            query: The short or informal query.

        Returns:
            enhanced_query: The rewritten, detailed query string.
        """
        SYSTEM = (
            "You are an expert industrial assistant. Your task is to rewrite short or informal "
            "user queries into professional, clear, and comprehensive questions suitable for an "
            "industrial knowledge base search. Do NOT answer the question. Only output the enhanced query text directly."
        )
        enhanced = await llm_client.chat(
            prompt=f"Enhance this query: '{query}'",
            system=SYSTEM,
            temperature=0.3
        )
        return {"enhanced_query": enhanced.strip('\"\' ')}

