"""
InduStreakAI — Unified Single MCP Server
=========================================
All platform intelligence exposed as one FastMCP server with 30+ tools.
Replaces the previous 6-server architecture for simpler deployment and
shared database connections.

Tool Namespaces:
  ingest_*   — Document ingestion (PDF, Excel, OCR, P&ID, folder watch, S3)
  extract_*  — NLP/NER entity extraction & knowledge engineering
  kg_*       — Knowledge graph (Neo4j AuraDB) operations
  search_*   — Vector + graph + hybrid search
  rag_*      — RAG pipeline (Mistral via NVIDIA NIM)
  maint_*    — Maintenance intelligence & RCA
  comply_*   — Compliance audit tools
  lessons_*  — Lessons learned & safety patterns
  admin_*    — System health & metadata
"""

import logging
import os
from pathlib import Path

# ── Load .env FIRST — before any tool/core imports that read env vars ─────────
# Search for .env in the mcp-server dir, then the project root (one level up)
_env_candidates = [
    Path(__file__).parent / ".env",          # mcp-server/.env
    Path(__file__).parent.parent / ".env",   # project_root/.env  ← standard location
]
for _env_path in _env_candidates:
    if _env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)  # override=False: real env vars win
        break

from mcp.server.fastmcp import FastMCP

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("industreak-mcp")

# ── FastMCP application ──────────────────────────────────────────────────────
port = int(os.getenv("PORT", "8080"))
mcp = FastMCP("InduStreakAI", host="0.0.0.0", port=port)

# ── Register all tool modules ────────────────────────────────────────────────
from tools.ingestion.pdf_tool import register as reg_pdf
from tools.ingestion.excel_tool import register as reg_excel
from tools.ingestion.ocr_tool import register as reg_ocr
from tools.ingestion.pid_tool import register as reg_pid
from tools.ingestion.watcher import register as reg_watcher
from tools.ingestion.s3_watcher import register as reg_s3

from tools.knowledge.ner_tool import register as reg_ner
from tools.knowledge.chunker_tool import register as reg_chunker
from tools.knowledge.embedding_tool import register as reg_embed
from tools.knowledge.triplet_tool import register as reg_triplet
from tools.knowledge.regulatory_tool import register as reg_reg
from tools.knowledge.hierarchy_tool import register as reg_hier

from tools.storage.vector_tool import register as reg_vector
from tools.storage.graph_tool import register as reg_graph
from tools.storage.asset_tool import register as reg_asset

from tools.search.hybrid_search import register as reg_hybrid
from tools.search.graph_search import register as reg_gsearch

from tools.agents.copilot import register as reg_copilot
from tools.agents.maintenance import register as reg_maint
from tools.agents.compliance import register as reg_comply
from tools.agents.lessons_learned import register as reg_lessons

from tools.admin.system_tools import register as reg_admin

for register_fn in [
    reg_pdf, reg_excel, reg_ocr, reg_pid, reg_watcher, reg_s3,
    reg_ner, reg_chunker, reg_embed, reg_triplet, reg_reg, reg_hier,
    reg_vector, reg_graph, reg_asset,
    reg_hybrid, reg_gsearch,
    reg_copilot, reg_maint, reg_comply, reg_lessons,
    reg_admin,
]:
    register_fn(mcp)

logger.info("InduStreakAI MCP server initialised — %d tool namespaces loaded", 21)

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting InduStreakAI MCP server on port %d", port)
    mcp.run(transport="streamable-http")
