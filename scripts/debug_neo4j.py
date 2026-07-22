import sys
import asyncio
from pathlib import Path
import os
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

sys.path.append(str(project_root))
import importlib.util
mcp_server_path = project_root / "mcp-server"

def import_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

neo4j_client = import_module_from_path("neo4j_client", mcp_server_path / "core" / "neo4j_client.py")

async def main():
    print("Checking neo4j...")
    docs = await neo4j_client.run_cypher("MATCH (doc:Document) RETURN doc.id as id, doc.title as title LIMIT 5")
    print(f"Total documents returned by generic query: {len(docs)}")
    print(docs)
    
    linked_docs = await neo4j_client.run_cypher("MATCH (doc:Document)-[:COMPLIES_WITH]->(reg:Regulation {framework: 'OISD_STD_144'}) RETURN doc.id as id")
    print(f"Linked to OISD_STD_144: {len(linked_docs)}")
    print(linked_docs)
    
if __name__ == "__main__":
    asyncio.run(main())
