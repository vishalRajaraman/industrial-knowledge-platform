import asyncio
import json
import sys
import uuid
import logging
from pathlib import Path

# Add the mcp-server directory to sys.path so we can import core modules
project_root = Path(__file__).resolve().parent.parent
mcp_server_path = project_root / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

from core import embeddings
from core import neo4j_client
from core import pinecone_client as vc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_ontology")

async def ingest_ontologies():
    ontology_dir = mcp_server_path / "ontology"
    if not ontology_dir.exists():
        logger.error(f"Ontology directory not found: {ontology_dir}")
        return

    json_files = list(ontology_dir.glob("*.json"))
    
    logger.info(f"Found {len(json_files)} ontology files to ingest.")
    
    for file_path in json_files:
        if file_path.name == "asset_types.json":
            continue
            
        logger.info(f"--- Processing {file_path.name} ---")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {file_path.name}: {e}")
            continue
            
        framework_id = data.get("id")
        framework_name = data.get("name")
        clauses = data.get("clauses", [])
        
        if not framework_id or not clauses:
            logger.warning(f"Skipping {file_path.name} — missing 'id' or 'clauses'.")
            continue
            
        # 1. Create the Framework Node in Neo4j
        await neo4j_client.upsert_node(
            node_id=framework_id,
            labels=["RegulationFramework"],
            properties={
                "name": framework_name,
                "applicable_to": data.get("applicable_to", [])
            }
        )
        
        chunks = []
        # 2. Process each clause
        for clause_text in clauses:
            # We construct a unique ID for the clause
            clause_id = f"{framework_id}_{uuid.uuid4().hex[:8]}"
            
            # Neo4j: Create Clause node and PART_OF relationship
            await neo4j_client.upsert_node(
                node_id=clause_id,
                labels=["RegulationClause"],
                properties={
                    "framework": framework_id,
                    "text": clause_text
                }
            )
            await neo4j_client.upsert_edge(
                from_id=clause_id,
                to_id=framework_id,
                relationship="PART_OF"
            )
            
            # Prepare for Vector DB
            chunks.append({
                "id": clause_id,
                "text": f"Framework: {framework_name} ({framework_id}) | Clause: {clause_text}",
                "doc_id": framework_id,
                "doc_type": "regulation"
            })
            
        # 3. Embed and upsert to Vector DB (Pinecone)
        if chunks:
            logger.info(f"Embedding {len(chunks)} clauses for {framework_id}...")
            texts_to_embed = [c["text"] for c in chunks]
            
            # Optional: handle Cohere rate limits if we have many clauses
            # For these small standards, we shouldn't hit the 96 batch limit, but just in case
            try:
                vectors = embeddings.embed_documents(texts_to_embed)
                
                enriched_chunks = []
                for c, v in zip(chunks, vectors):
                    c["embedding"] = v
                    enriched_chunks.append(c)
                    
                await vc.upsert_chunks(enriched_chunks)
                logger.info(f"Successfully ingested {framework_id} to Neo4j and Vector DB.")
            except Exception as e:
                logger.error(f"Failed to embed/upsert {framework_id} to Vector DB: {e}")
                
        # Slight pause to respect API rate limits between files
        await asyncio.sleep(2)

    logger.info("=== Ontology Ingestion Complete ===")

if __name__ == "__main__":
    asyncio.run(ingest_ontologies())
