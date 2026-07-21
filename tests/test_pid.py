import asyncio
import time
import sys
from dotenv import load_dotenv

load_dotenv('.env')
sys.path.append('mcp-server')

# Import starts the background pre-warm thread automatically
from tools.ingestion.pid_tool import register
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('test')
register(mcp)
tool = mcp._tool_manager.get_tool('parse_pid')

IMAGE_PATH = r'C:\Users\vishal rajaraman\Desktop\pid_test.png'

async def run():
    print("Waiting 20s for YOLO pre-warm to complete in background...")
    await asyncio.sleep(20)

    from tools.ingestion import pid_tool
    print("Model cached:", pid_tool._cached_yolo_model is not None)

    print("\n--- Run 1 ---")
    t = time.time()
    res = await tool.fn(IMAGE_PATH, 0.4, False)
    elapsed = time.time() - t
    print(f"Elapsed: {elapsed:.1f}s")
    mode = res.get("detection_mode")
    count = res.get("equipment_count")
    annotated = res.get("annotated_image_path")
    print(f"Mode: {mode}")
    print(f"Equipment count: {count}")
    print(f"Annotated image saved: {annotated}")
    for eq in res.get("equipment_detected", [])[:5]:
        lbl = eq['label']
        tag = eq['tag']
        conf = eq['confidence']
        print(f"  - {lbl} ({tag}) conf={conf}")

    print("\n--- Run 2 (model already cached) ---")
    t = time.time()
    res2 = await tool.fn(IMAGE_PATH, 0.4, False)
    elapsed2 = time.time() - t
    print(f"Elapsed: {elapsed2:.1f}s")

if __name__ == "__main__":
    asyncio.run(run())
