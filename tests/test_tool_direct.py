"""
Direct tool test — bypasses MCP Inspector entirely.
Proves parse_pid works end-to-end: YOLO detection → annotated image → AuraDB.

Run:  python test_tool_direct.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(".env")

sys.path.append("mcp-server")

IMAGE_PATH = r"C:\Users\vishal rajaraman\Desktop\pid_test.png"

print("=" * 60)
print("  InduStreakAI — parse_pid Direct Tool Test")
print("=" * 60)

# ── Import triggers synchronous YOLO model load (~14s) ─────────────────
print("\n[1/4] Loading server modules (YOLO model loads here)...")
t0 = time.time()
from tools.ingestion.pid_tool import register, _cached_yolo_model
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test")
register(mcp)
tool = mcp._tool_manager.get_tool("parse_pid")
print(f"      Done in {time.time()-t0:.1f}s — model cached: {_cached_yolo_model is not None}")

# ── Run the tool ────────────────────────────────────────────────────────
async def run_test():
    from tools.ingestion import pid_tool

    print(f"\n[2/4] Running parse_pid on: {IMAGE_PATH}")
    t1 = time.time()
    result = await tool.fn(IMAGE_PATH, 0.4, False)
    elapsed = time.time() - t1
    print(f"      Returned in {elapsed:.1f}s")

    # ── Print results ───────────────────────────────────────────────────
    print(f"\n[3/4] Detection Results")
    print(f"      Mode:            {result.get('detection_mode')}")
    print(f"      Equipment found: {result.get('equipment_count')}")
    print(f"      Pipeline lines:  {result.get('pipeline_lines_detected')}")
    print(f"      Annotated image: {result.get('annotated_image_path')}")
    print(f"      KG status:       {result.get('kg_status')}")
    print(f"      Doc ID:          {result.get('doc_id')}")

    print(f"\n      Equipment list:")
    for eq in result.get("equipment_detected", []):
        print(f"        [{eq['confidence']:.2f}] {eq['label']} -> {eq['tag']}")

    # ── Verify annotated image exists ───────────────────────────────────
    annotated = result.get("annotated_image_path", "")
    if Path(annotated).exists():
        size_kb = Path(annotated).stat().st_size // 1024
        print(f"\n      ✅ Annotated image saved ({size_kb} KB): {annotated}")
    else:
        print(f"\n      ❌ Annotated image NOT found at: {annotated}")

    # ── Wait for AuraDB background write ───────────────────────────────
    print(f"\n[4/4] Waiting 15s for background AuraDB write to complete...")
    await asyncio.sleep(15)

    from core import neo4j_client
    try:
        t2 = time.time()
        rows = await neo4j_client.run_cypher(
            "MATCH (n) RETURN labels(n)[0] as type, n.id as id LIMIT 30"
        )
        print(f"      AuraDB connected in {time.time()-t2:.1f}s")
        print(f"      Total nodes visible: {len(rows)}")
        for row in rows[:10]:
            print(f"        [{row['type']}] {row['id']}")

        # Check for doc written in this run
        doc_id = result.get("doc_id")
        check = await neo4j_client.run_cypher(
            "MATCH (d:Drawing {id: $id}) RETURN d.filename as fn, d.equipment_count as eq",
            {"id": doc_id}
        )
        if check:
            print(f"\n      ✅ AuraDB: Drawing node found — {check[0]}")
        else:
            print(f"\n      ⚠️  AuraDB: Drawing node not yet visible (may need more time)")
    except Exception as e:
        print(f"      ❌ AuraDB error: {e}")

    print("\n" + "=" * 60)
    print("  Test complete.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_test())
