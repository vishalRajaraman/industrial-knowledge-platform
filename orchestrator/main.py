"""
FastAPI + LangGraph Orchestrator
The main backend — handles API requests, connects to all MCP servers,
routes queries to specialized agents.
"""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.router import RouterAgent
from agents.copilot_agent import CopilotAgent
from agents.compliance_agent import ComplianceAgent
from mcp_client import MCPClientManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

# ─── Global MCP Client Manager ─────────────────────────────────────────────────
mcp_manager = MCPClientManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP connections on startup."""
    logger.info("Connecting to MCP servers...")
    await mcp_manager.connect_all()
    logger.info("All MCP servers connected.")
    yield
    await mcp_manager.disconnect_all()


# ─── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Industrial Knowledge Intelligence Platform",
    description="AI-powered unified asset and operations brain",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str
    user_role: str = "operator"  # operator | engineer | manager | auditor
    equipment_id: str | None = None
    regulation: str | None = None
    session_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    agent_used: str
    sources: list[dict]
    confidence: float
    session_id: str
    metadata: dict


class GraphQueryRequest(BaseModel):
    cypher: str
    params: dict = {}


# ─── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    server_status = await mcp_manager.health_check_all()
    return {"status": "ok", "mcp_servers": server_status}


# ─── Document Upload ─────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = "general",
    plant_id: str = "default",
):
    """Upload and process a document through the full ingestion pipeline."""
    import tempfile, shutil, pathlib

    doc_id = str(uuid.uuid4())
    suffix = pathlib.Path(file.filename or "document").suffix

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Determine the correct ingestion tool based on doc_type or extension
        tool_name = "ingest_pdf" # Default
        if suffix.lower() in ['.xlsx', '.xls', '.csv']:
            tool_name = "ingest_excel"
        elif doc_type == "pid":
            tool_name = "ingest_pid"
        elif doc_type == "drawing":
            tool_name = "ingest_drawing"
            
        result = await mcp_manager.call_tool(
            server="ingestion",
            tool_name=tool_name,
            arguments={
                "file_path": tmp_path,
                "doc_type": doc_type,
                "metadata": {"plant_id": plant_id, "filename": file.filename, "doc_id": doc_id}
            }
        )
        return {
            "doc_id": doc_id,
            "filename": file.filename,
            "status": "processed",
            "result": result,
        }
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ─── Query ───────────────────────────────────────────────────────────────────────
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Route a user query to the appropriate agent."""
    session_id = request.session_id or str(uuid.uuid4())

    # Route query
    router = RouterAgent(mcp_manager)
    route = await router.classify(request.query)
    category = route["category"]
    entities = route.get("entities_detected", [])

    # Dispatch to agent or tool based on intent
    if category == "KNOWLEDGE_QUERY":
        agent = CopilotAgent(mcp_manager)
        result = await agent.run(request.query, entities, request.user_role)
    elif category == "COMPLIANCE_QUERY":
        agent = ComplianceAgent(mcp_manager)
        result = await agent.run(request.query, request.regulation)
    elif category == "DIRECT_SEARCH":
        # Bypass agents and call the hybrid_search tool directly
        search_result = await mcp_manager.call_tool("knowledge", "hybrid_search", {
            "query": request.query,
            "top_k": 10,
            "equipment_tags": entities
        })
        result = {
            "answer": "Here are the files and documents matching your search.",
            "sources": search_result.get("combined_sources", []),
            "confidence": 1.0,
            "metadata": {"graph_context": search_result.get("graph_context", {})}
        }
    else:
        # Default to copilot
        agent = CopilotAgent(mcp_manager)
        result = await agent.run(request.query, entities, request.user_role)

    return QueryResponse(
        answer=result["answer"],
        agent_used=category,
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
        session_id=session_id,
        metadata={"route": route, **result.get("metadata", {})},
    )


# ─── Streaming Query ──────────────────────────────────────────────────────────────
@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """Streaming version of query for real-time response."""
    session_id = request.session_id or str(uuid.uuid4())

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"

        router = RouterAgent(mcp_manager)
        route = await router.classify(request.query)
        yield f"data: {json.dumps({'type': 'routing', 'category': route['category']})}\n\n"

        # Stream answer token by token (simplified — real streaming from LLM)
        agent = CopilotAgent(mcp_manager)
        result = await agent.run(request.query, route.get("entities_detected", []), request.user_role)

        # Stream answer in chunks
        answer = result["answer"]
        chunk_size = 20
        for i in range(0, len(answer), chunk_size):
            chunk = answer[i: i + chunk_size]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            await asyncio.sleep(0.02)

        yield f"data: {json.dumps({'type': 'done', 'sources': result.get('sources', []), 'confidence': result.get('confidence', 0.0)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ─── Knowledge Graph Endpoints ────────────────────────────────────────────────────
@app.post("/graph/query")
async def graph_query(request: GraphQueryRequest):
    """Execute a Cypher query against the knowledge graph."""
    result = await mcp_manager.call_tool("storage", "graph_query", {
        "cypher": request.cypher,
        "params": request.params,
    })
    return result


@app.get("/graph/entity/{entity_id}")
async def graph_entity(entity_id: str, depth: int = 2):
    """Get subgraph around an entity."""
    result = await mcp_manager.call_tool("storage", "graph_traversal", {
        "node_id": entity_id,
        "depth": depth,
    })
    return result


@app.get("/graph/stats")
async def graph_stats():
    """Get knowledge graph statistics."""
    result = await mcp_manager.call_tool("storage", "graph_query", {
        "cypher": """
        MATCH (n) 
        WITH labels(n) as lbls, count(n) as cnt
        RETURN lbls, cnt
        ORDER BY cnt DESC
        """
    })
    edge_count = await mcp_manager.call_tool("storage", "graph_query", {
        "cypher": "MATCH ()-[r]->() RETURN count(r) as total_edges"
    })
    return {"nodes": result, "edges": edge_count}


# ─── WebSocket for real-time updates ─────────────────────────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "query":
                router = RouterAgent(mcp_manager)
                route = await router.classify(data["query"])
                await websocket.send_json({"type": "routing", "category": route["category"]})

                agent = CopilotAgent(mcp_manager)
                result = await agent.run(data["query"], [], "operator")
                await websocket.send_json({
                    "type": "answer",
                    "answer": result["answer"],
                    "sources": result.get("sources", []),
                    "confidence": result.get("confidence", 0),
                })
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
