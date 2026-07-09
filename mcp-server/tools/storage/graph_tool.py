"""
Storage tools — Neo4j AuraDB (cloud-hosted Knowledge Graph) MCP tools.
kg_upsert_node, kg_upsert_edge, kg_query, kg_traversal, kg_stats.
"""
from mcp.server.fastmcp import FastMCP
from core import neo4j_client


def register(mcp: FastMCP):

    @mcp.tool()
    async def kg_upsert_node(
        node_id: str,
        labels: list[str],
        properties: dict | None = None,
    ) -> dict:
        """
        Create or update an entity node in Neo4j AuraDB (cloud Knowledge Graph).
        Uses MERGE on node_id — safe to call multiple times.

        Node types used in this platform:
        :Equipment, :Document, :Person, :WorkOrder, :FailureEvent,
        :Inspection, :Procedure, :Regulation, :ProcessParameter, :Incident

        Args:
            node_id: Unique identifier (e.g., equipment tag 'P-101A', doc UUID).
            labels: List of Neo4j labels (e.g., ['Equipment', 'Pump']).
            properties: Node properties dict.

        Returns:
            Upsert confirmation with node_id.
        """
        return await neo4j_client.upsert_node(node_id, labels, properties or {})

    @mcp.tool()
    async def kg_upsert_edge(
        from_id: str,
        to_id: str,
        relationship: str,
        properties: dict | None = None,
    ) -> dict:
        """
        Create or update a relationship between two nodes in Neo4j AuraDB.

        Relationship types used:
        CONNECTED_TO, MENTIONED_IN, HAS_FAILURE, MAINTAINED_BY,
        INSPECTED_IN, GOVERNED_BY, OPERATES_WITH, AUTHORED, PERFORMED,
        ADDRESSES, APPLIES_TO, INVOLVED, LED_TO, COMPLIES_WITH, DEPICTED_IN

        Args:
            from_id: Source node ID.
            to_id: Target node ID.
            relationship: Relationship type (UPPER_CASE_WITH_UNDERSCORES).
            properties: Optional relationship properties.

        Returns:
            Creation confirmation.
        """
        return await neo4j_client.upsert_edge(from_id, to_id, relationship, properties)

    @mcp.tool()
    async def kg_query(cypher: str, params: dict | None = None) -> dict:
        """
        Execute a raw Cypher query against Neo4j AuraDB.
        Use for complex traversals, aggregations, or custom lookups.

        Args:
            cypher: Cypher query string.
            params: Query parameters dict (use $param_name in query).

        Returns:
            List of result rows as dicts.

        Example:
            cypher: "MATCH (e:Equipment)-[:HAS_FAILURE]->(f:FailureEvent) RETURN e.tag, f.mode LIMIT 10"
        """
        rows = await neo4j_client.run_cypher(cypher, params)
        return {"results": rows, "count": len(rows)}

    @mcp.tool()
    async def kg_traversal(
        node_id: str,
        depth: int = 2,
        relationship_types: list[str] | None = None,
    ) -> dict:
        """
        Get the contextual subgraph around an entity (neighbourhood exploration).
        Returns all nodes and relationships within N hops.

        Args:
            node_id: Starting entity ID (e.g., 'P-101A', document UUID).
            depth: Number of hops to traverse (default: 2, max recommended: 3).
            relationship_types: Filter by specific relationship types (optional).

        Returns:
            Nodes list and relationships list for graph visualization.
        """
        return await neo4j_client.get_subgraph(node_id, depth, relationship_types)

    @mcp.tool()
    async def kg_stats() -> dict:
        """
        Get Neo4j AuraDB statistics: node counts by label,
        relationship counts by type, and total graph size.
        Also runs a keepalive ping to prevent AuraDB auto-pause.
        """
        counts = await neo4j_client.run_cypher(
            "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC LIMIT 20"
        )
        rel_counts = await neo4j_client.run_cypher(
            "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC LIMIT 20"
        )
        await neo4j_client.keepalive_ping()
        return {
            "node_counts": counts,
            "relationship_counts": rel_counts,
            "keepalive": "pinged",
        }
