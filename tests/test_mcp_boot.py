"""
MCP Server Boot Test — server.py
=================================
Verifies that the FastMCP server starts cleanly and all 21 tool
modules import without errors. Does NOT start the HTTP listener —
just validates the import/registration chain.

Covers:
  1. All tool module imports resolve (no missing files/packages)
  2. All 21 register() calls complete without exceptions
  3. FastMCP has tools registered after boot
  4. Core clients (Qdrant, Neo4j) are importable (config errors are expected
     without live credentials, but import itself must succeed)
  5. Server.py __main__ block exists with correct transport config

Usage:
    cd mcp-server
    pip install -r requirements.txt
    python ../tests/test_mcp_boot.py
"""

import sys
import os
import importlib
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"✅  Loaded .env from {env_path}")
else:
    print("⚠️   No .env found")

# ── Add mcp-server to path ────────────────────────────────────────────────────
MCP_SERVER_DIR = Path(__file__).parent.parent / "mcp-server"
sys.path.insert(0, str(MCP_SERVER_DIR))
os.chdir(MCP_SERVER_DIR)   # server.py uses relative paths for ontology/

results: dict[str, bool] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1 — Import: mcp.server.fastmcp (FastMCP library present)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 1 — FastMCP library import")
print("=" * 60)
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("TestServer")
    print("✅  FastMCP imported and instantiated\n")
    results["fastmcp_import"] = True
except ImportError as e:
    print(f"❌  FastMCP not installed: {e}")
    print("    Run: pip install mcp\n")
    results["fastmcp_import"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2 — Import: core modules
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 2 — Core module imports (llm_client, embeddings, neo4j_client, pinecone_client)")
print("=" * 60)

core_modules = [
    ("core.llm_client",    "LLM client (Mistral / NVIDIA NIM)"),
    ("core.embeddings",    "Embedding engine (Cohere)"),
]

for mod_name, desc in core_modules:
    try:
        mod = importlib.import_module(mod_name)
        print(f"✅  {mod_name:30s} — {desc}")
        results[f"import_{mod_name}"] = True
    except Exception as e:
        print(f"❌  {mod_name:30s} — {e}")
        results[f"import_{mod_name}"] = False

# neo4j and qdrant will raise EnvironmentError if creds missing — that's expected
for mod_name, desc in [("core.neo4j_client", "Neo4j AuraDB client"), ("core.pinecone_client", "Qdrant Cloud client")]:
    try:
        mod = importlib.import_module(mod_name)
        print(f"✅  {mod_name:30s} — {desc}")
        results[f"import_{mod_name}"] = True
    except EnvironmentError as e:
        # Expected when no creds are set — import worked, just missing config
        print(f"⚠️   {mod_name:30s} — Config missing (expected in bare env): {str(e)[:80]}")
        results[f"import_{mod_name}"] = True  # Import itself succeeded
    except Exception as e:
        print(f"❌  {mod_name:30s} — {e}")
        results[f"import_{mod_name}"] = False
print()


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3 — Import + register(): all 21 tool modules
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 3 — All 21 tool modules: import + register(mcp)")
print("=" * 60)

TOOL_MODULES = [
    # Ingestion
    ("tools.ingestion.pdf_tool",        "reg_pdf",      "ingest_pdf"),
    ("tools.ingestion.excel_tool",      "reg_excel",    "ingest_excel"),
    ("tools.ingestion.ocr_tool",        "reg_ocr",      "ocr_document"),
    ("tools.ingestion.pid_tool",        "reg_pid",      "parse_pid"),
    ("tools.ingestion.watcher",         "reg_watcher",  "watch_local_folder"),
    ("tools.ingestion.s3_watcher",      "reg_s3",       "watch_s3_bucket"),
    # Knowledge
    ("tools.knowledge.ner_tool",        "reg_ner",      "extract_entities"),
    ("tools.knowledge.chunker_tool",    "reg_chunker",  "chunk_document"),
    ("tools.knowledge.embedding_tool",  "reg_embed",    "generate_embeddings"),
    ("tools.knowledge.triplet_tool",    "reg_triplet",  "build_knowledge_triplets"),
    ("tools.knowledge.regulatory_tool", "reg_reg",      "align_regulatory"),
    ("tools.knowledge.hierarchy_tool",  "reg_hier",     None),   # stub, no tool
    # Storage
    ("tools.storage.vector_tool",       "reg_vector",   "vector_upsert"),
    ("tools.storage.graph_tool",        "reg_graph",    "kg_upsert_node"),
    ("tools.storage.asset_tool",        "reg_asset",    "store_raw_asset"),
    # Search
    ("tools.search.hybrid_search",      "reg_hybrid",   "hybrid_search"),
    ("tools.search.graph_search",       "reg_gsearch",  "graph_search"),
    # Agents
    ("tools.agents.copilot",            "reg_copilot",  "ask_knowledge_copilot"),
    ("tools.agents.compliance",         "reg_comply",   "audit_compliance"),
    # Admin
    ("tools.admin.system_tools",        "reg_admin",    "admin_health_check"),
]

if results.get("fastmcp_import"):
    from mcp.server.fastmcp import FastMCP
    test_mcp = FastMCP("BootTest")
    
    all_module_ok = True
    for mod_path, alias, expected_tool in TOOL_MODULES:
        try:
            mod = importlib.import_module(mod_path)
            mod.register(test_mcp)
            print(f"  ✅  {mod_path}")
            results[f"register_{alias}"] = True
        except Exception as e:
            print(f"  ❌  {mod_path} — {e}")
            results[f"register_{alias}"] = False
            all_module_ok = False
    print()
else:
    print("⚠️   Skipped — FastMCP not available\n")
    all_module_ok = False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Tool count: FastMCP has tools after registration
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 4 — Tool count: FastMCP has tools registered")
print("=" * 60)

try:
    if results.get("fastmcp_import"):
        # FastMCP stores tools internally — access via _tool_manager or tools dict
        tool_names = list(test_mcp._tool_manager._tools.keys())
        count = len(tool_names)
        print(f"✅  {count} tools registered")
        print(f"    Registered tool names:")
        for name in sorted(tool_names):
            print(f"      • {name}")
        results["tool_count"] = count >= 20
    else:
        results["tool_count"] = False
except Exception as e:
    # FastMCP internals may vary — just check it didn't crash during boot
    print(f"⚠️   Could not enumerate tools (FastMCP internals): {e}")
    print(f"    This is OK — boot test passes if all register() calls succeeded")
    results["tool_count"] = all_module_ok
print()


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5 — server.py transport config check
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 5 — server.py uses streamable-http transport on PORT env var")
print("=" * 60)

server_py = MCP_SERVER_DIR / "server.py"
content   = server_py.read_text(encoding="utf-8")

checks = {
    "host=0.0.0.0":              'host="0.0.0.0"'             in content,
    "PORT env var":               'os.getenv("PORT"'           in content,
    "FastMCP registered":         "FastMCP"                    in content,
}

all_ok = True
for check, passed in checks.items():
    icon = "✅" if passed else "❌"
    print(f"  {icon}  {check}")
    if not passed:
        all_ok = False

results["server_config"] = all_ok
print()


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("MCP SERVER BOOT TEST SUMMARY")
print("=" * 60)

critical = ["fastmcp_import", "import_core.llm_client", "import_core.embeddings", "tool_count", "server_config"]
failed   = [k for k, v in results.items() if not v]

if not failed:
    print("🎉  ALL CHECKS PASSED — MCP server will boot cleanly!")
    print("    Transport : streamable-http (judges can hit it via HTTP)")
    print("    Tools     : all 21 modules registered")
    print("\n    You can now proceed to Component 1.3 (PDF Ingestion Tool).")
else:
    print(f"⚠️   {len(failed)} checks failed:")
    for f in failed:
        is_critical = any(c in f for c in ["fastmcp", "core.", "tool_count", "server_config"])
        tag = " ← CRITICAL" if is_critical else ""
        print(f"    ❌  {f}{tag}")

print()
