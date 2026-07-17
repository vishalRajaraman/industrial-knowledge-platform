"""
Core client — Neo4j AuraDB (cloud-hosted Knowledge Graph).
Fully cloud-managed. Free tier: 200K nodes / 400K relationships.
Sign up: https://neo4j.com/cloud/platform/aura-graph-database/
"""
import asyncio
import logging
import os
from typing import Any

import neo4j
from neo4j import AsyncGraphDatabase

logger = logging.getLogger("ikp.neo4j")

NEO4J_URI = os.getenv("NEO4J_URI")          # neo4j+s://xxxx.databases.neo4j.io
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# NOTE: Credentials are validated lazily in get_driver(), not at import time.
# This allows server.py to load all modules before checking connectivity.

_driver: neo4j.AsyncDriver | None = None


def get_driver() -> neo4j.AsyncDriver:
    global _driver
    if _driver is None:
        # Lazy validation — only raises when first connection is attempted
        _uri  = os.getenv("NEO4J_URI")
        _user = os.getenv("NEO4J_USER", "neo4j")
        _pwd  = os.getenv("NEO4J_PASSWORD")
        if not _uri or not _pwd:
            raise EnvironmentError(
                "NEO4J_URI and NEO4J_PASSWORD must be set. "
                "Sign up free at https://neo4j.com/cloud/aura-free/"
            )
        # 30s timeout — enough for AuraDB cold-start/wake-up without hanging forever
        _driver = AsyncGraphDatabase.driver(_uri, auth=(_user, _pwd), connection_timeout=30.0)
    return _driver


async def run_cypher(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return rows as dicts."""
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(cypher, **(params or {}))
        records = await result.data()
        return records


async def upsert_node(node_id: str, labels: list[str], properties: dict) -> dict:
    """Create or update a node using MERGE on node_id."""
    label_str = ":".join(labels)
    props_set = ", ".join(f"n.{k} = ${k}" for k in properties)
    cypher = f"""
    MERGE (n:{label_str} {{id: $node_id}})
    ON CREATE SET n += $props, n.created_at = datetime()
    ON MATCH  SET {props_set if props_set else 'n.updated_at = datetime()'}
    RETURN n.id as id
    """
    params = {"node_id": node_id, "props": properties, **properties}
    rows = await run_cypher(cypher, params)
    return {"node_id": node_id, "labels": labels, "upserted": bool(rows)}


async def upsert_edge(
    from_id: str, to_id: str, relationship: str, properties: dict | None = None
) -> dict:
    """Create or update a relationship between two existing nodes."""
    props = properties or {}
    props_str = ", ".join(f"r.{k} = ${k}" for k in props)
    set_clause = f"ON CREATE SET {props_str}, r.created_at = datetime()" if props else "ON CREATE SET r.created_at = datetime()"
    cypher = f"""
    MATCH (a {{id: $from_id}}), (b {{id: $to_id}})
    MERGE (a)-[r:{relationship}]->(b)
    {set_clause}
    RETURN type(r) as rel_type
    """
    rows = await run_cypher(cypher, {"from_id": from_id, "to_id": to_id, **props})
    return {"from_id": from_id, "to_id": to_id, "relationship": relationship, "created": bool(rows)}


async def get_subgraph(node_id: str, depth: int = 2, rel_types: list[str] | None = None) -> dict:
    """Get neighbourhood subgraph within N hops."""
    rel_filter = f":{' | '.join(rel_types)}" if rel_types else ""
    cypher = f"""
    MATCH path = (n {{id: $node_id}})-[r{rel_filter}*1..{depth}]-(related)
    RETURN 
        [node in nodes(path) | {{id: node.id, labels: labels(node), props: properties(node)}}] as nodes,
        [rel  in relationships(path) | {{type: type(rel), from: startNode(rel).id, to: endNode(rel).id}}] as rels
    LIMIT 200
    """
    rows = await run_cypher(cypher, {"node_id": node_id})
    nodes_seen, rels_seen = {}, set()
    for row in rows:
        for n in row.get("nodes", []):
            nodes_seen[n["id"]] = n
        for r in row.get("rels", []):
            key = (r["from"], r["type"], r["to"])
            if key not in rels_seen:
                rels_seen.add(key)
    return {"node_id": node_id, "nodes": list(nodes_seen.values()), "relationships": list(rels_seen)}


async def find_failure_patterns(equipment_tag: str, days: int = 365) -> list[dict]:
    cypher = """
    MATCH (e:Equipment {id: $tag})-[:HAS_FAILURE]->(f:FailureEvent)
    WHERE f.date >= datetime() - duration({days: $days})
    RETURN f.id as id, f.date as date, f.mode as mode,
           f.severity as severity, f.root_cause as root_cause
    ORDER BY f.date DESC
    """
    return await run_cypher(cypher, {"tag": equipment_tag, "days": days})


async def check_compliance_coverage(framework: str) -> list[dict]:
    cypher = """
    MATCH (r:Regulation {framework: $framework})
    OPTIONAL MATCH (e:Equipment)-[:GOVERNED_BY]->(r)
    RETURN r.clause as clause, r.description as description, count(e) as coverage_count
    ORDER BY clause
    """
    return await run_cypher(cypher, {"framework": framework})


async def keepalive_ping() -> bool:
    """Write a heartbeat node to prevent AuraDB auto-pause (every 3 days)."""
    try:
        await run_cypher(
            "MERGE (h:Heartbeat {id: 'keepalive'}) SET h.last_ping = datetime() RETURN h"
        )
        return True
    except Exception as e:
        logger.warning("Neo4j keepalive failed: %s", e)
        return False
