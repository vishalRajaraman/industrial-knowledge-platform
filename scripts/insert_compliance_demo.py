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
    print("Inserting demo compliance data...")
    # Add Regulation
    await neo4j_client.upsert_node("REG-OISD-154", ["Regulation", "RegulationFramework"], {
        "framework": "OISD_154",
        "description": "Safety Management System for Petroleum Industry"
    })
    await neo4j_client.upsert_node("REG-OISD-144", ["Regulation", "RegulationFramework"], {
        "framework": "OISD_STD_144",
        "description": "Fire Prevention & Protection"
    })
    
    # Add Document 1
    doc1_id = "DOC-DEMO-001"
    await neo4j_client.upsert_node(doc1_id, ["Document"], {
        "title": "Fire Water Pump Maintenance Log - 2026",
        "doc_type": "inspection",
        "content": "Quarterly inspection missing for Q1."
    })
    
    # Add Document 2
    doc2_id = "DOC-DEMO-002"
    await neo4j_client.upsert_node(doc2_id, ["Document"], {
        "title": "Plant Safety Procedures V2",
        "doc_type": "procedure",
        "content": "Safety management procedures."
    })
    
    # Add Relationships
    await neo4j_client.upsert_edge(doc1_id, "REG-OISD-144", "COMPLIES_WITH")
    await neo4j_client.upsert_edge(doc2_id, "REG-OISD-154", "COMPLIES_WITH")
    await neo4j_client.upsert_edge(doc1_id, "REG-OISD-154", "COMPLIES_WITH")

    print("Data insertion complete.")

if __name__ == "__main__":
    asyncio.run(main())
