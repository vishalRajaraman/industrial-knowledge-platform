import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(r"c:\Users\vishal rajaraman\Desktop\industrial-knowledge-platform\.env")
load_dotenv(env_path)

import sys
sys.path.append(r"c:\Users\vishal rajaraman\Desktop\industrial-knowledge-platform\mcp-server")

from core import llm_client, neo4j_client

async def main():
    print("Testing LLM...")
    try:
        response = await llm_client.chat("Say 'Hello, I am working!'")
        print("LLM Response:", response)
    except Exception as e:
        print("LLM Error:", e)

    print("\nTesting Neo4j...")
    try:
        nodes = await neo4j_client.run_cypher("MATCH (n) RETURN count(n) as count")
        print("Neo4j Nodes:", nodes)
        
        # Test the compliance queries
        print("\nTesting comply_map_regulations Cypher...")
        cypher = "MATCH (e:Equipment {id: 'P-101'})-[:GOVERNED_BY]->(r:Regulation) RETURN r.framework as framework"
        res = await neo4j_client.run_cypher(cypher)
        print("Compliance Result:", res)
    except Exception as e:
        print("Neo4j Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
