import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(r"c:\Users\vishal rajaraman\Desktop\industrial-knowledge-platform\.env")
load_dotenv(env_path)
sys.path.append(r"c:\Users\vishal rajaraman\Desktop\industrial-knowledge-platform\mcp-server")

from core import llm_client, neo4j_client

# We'll just test the core clients which the tools wrap. 
# We already saw Neo4j fail earlier due to paused database. Let's check again.

async def main():
    print("--- Starting Backend Tests ---")
    
    print("\n1. Testing LLM (NVIDIA NIM)...")
    try:
        res = await llm_client.chat("Say 'LLM is working'")
        print(f"LLM Result: {res}")
    except Exception as e:
        print(f"LLM ERROR: {e}")

    print("\n2. Testing Neo4j (Knowledge Graph)...")
    try:
        nodes = await neo4j_client.run_cypher("MATCH (n) RETURN count(n) as count")
        print(f"Neo4j Result: {nodes}")
    except Exception as e:
        print(f"Neo4j ERROR: {e}")
        print("-> Action Required: Please log into Neo4j AuraDB and resume your database instance.")
        
    print("\n3. Testing RouterAgent (Orchestrator)...")
    try:
        sys.path.append(r"c:\Users\vishal rajaraman\Desktop\industrial-knowledge-platform\orchestrator")
        from agents.router import RouterAgent
        class DummyMCP: pass
        router = RouterAgent(DummyMCP())
        route = await router.classify("Am I compliant with OISD 144?")
        print(f"Router Result: {route}")
    except Exception as e:
        print(f"Router ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
