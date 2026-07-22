import sys
import asyncio
from pathlib import Path
import os
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

sys.path.append(str(project_root / "orchestrator"))
from agents.router import RouterAgent
from mcp_client import MCPClientManager

async def main():
    print("Testing RouterAgent...")
    mcp_manager = MCPClientManager()
    router = RouterAgent(mcp_manager)
    
    query = "Check compliance gaps for framework OISD_STD_144 targeting All Plant"
    print(f"Query: {query}")
    print(f"Using Model: {os.getenv('LLM_MODEL')}")
    
    result = await router.classify(query)
    print(f"Classification Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
