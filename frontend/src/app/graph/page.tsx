"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { ProtectedRoute } from "@/components/auth/protected-route";

// Dynamically import the visualizer to avoid SSR issues with Canvas/window
const GraphVisualizer = dynamic(
  () => import("@/components/search/graph-visualizer").then((mod) => mod.GraphVisualizer),
  { ssr: false, loading: () => <div className="glass-panel" style={{ height: "100%", display: "grid", placeItems: "center", color: "var(--text-muted)" }}>Loading Graph Engine...</div> }
);

// Dynamic colors are now generated per-type when the graph loads

interface GraphNode {
  id: string;
  label?: string;
  type?: string;
  [key: string]: unknown;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  label?: string;
  type?: string;
  from?: string;
  to?: string;
  [key: string]: unknown;
}

export default function GraphPage() {
  const [searchEntity, setSearchEntity] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [typeColors, setTypeColors] = useState<Record<string, string>>({});
  
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async (query: string) => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const endpoint = query.trim() ? `/graph/entity/${encodeURIComponent(query.trim())}?depth=2` : `/graph/all`;
      const response = await fetch(`${apiUrl}${endpoint}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" }
      });

      if (!response.ok) throw new Error(`API returned ${response.status}`);
      
      const data = await response.json();
      
      // Map Neo4j orchestrator response
      // Nodes from FastMCP neo4j client have {id, labels, props}. Map labels[0] to type.
      const nodes = Array.isArray(data?.nodes) ? data.nodes.map((n: any) => ({
        ...n,
        type: n.labels && n.labels.length > 0 ? n.labels[0] : "Entity"
      })) : [];
      const edges = Array.isArray(data?.relationships) ? data.relationships.map((r: { from: string; to: string; type: string }) => ({
        source: r.from,
        target: r.to,
        label: r.type
      })) : [];
      
      if (nodes.length > 0) {
        setGraphData({ nodes, edges });
        
        // Dynamically assign colors to unique types
        const uniqueTypes = Array.from(new Set(nodes.map((n: GraphNode) => n.type || "Entity")));
        const newColors: Record<string, string> = {};
        uniqueTypes.forEach((type, idx) => {
          // Golden angle approximation for evenly distributed vibrant colors
          newColors[type as string] = `hsl(${(idx * 137.508) % 360}, 75%, 60%)`;
        });
        setTypeColors(newColors);
      } else {
        setGraphData({ nodes: [], edges: [] });
        setError("No nodes found for this query.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchGraph(searchEntity);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ProtectedRoute allowedRoles={["plant admin"]}>
      <div className="animate-in" style={{ height: "calc(100vh - 140px)", display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
          <div>
            <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
              Knowledge <span className="text-accent">Graph Explorer</span>
            </h1>
            <p style={{ color: "var(--text-muted)" }}>
              Navigate relationships between assets, procedures, failures, and regulations.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <input
              type="text"
              value={searchEntity}
              onChange={(e) => setSearchEntity(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchGraph(searchEntity)}
              placeholder="Enter entity ID..."
              style={{ padding: "0.625rem 1rem", borderRadius: "8px", background: "rgba(15,23,42,0.8)", border: "1px solid var(--border-color)", color: "white", outline: "none" }}
            />
            <button className="btn-primary" onClick={() => fetchGraph(searchEntity)} disabled={loading}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              {loading ? "Exploring..." : "Explore"}
            </button>
          </div>
        </div>

        {error && (
          <div className="glass-panel" style={{ padding: "1rem 1.2rem", borderColor: "rgba(239,68,68,0.35)", background: "rgba(239,68,68,0.08)", marginBottom: "1rem" }}>
            Warning: {error}.
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "1.5rem", flex: 1, minHeight: 0 }}>
          {/* Graph Canvas */}
          <div className="glass-panel" style={{ position: "relative", overflow: "hidden", background: "#050816" }}>
            {/* Legend */}
            <div style={{ position: "absolute", top: "1rem", left: "1rem", display: "flex", flexDirection: "column", gap: "6px", zIndex: 10, background: "rgba(15,23,42,0.6)", padding: "1rem", borderRadius: "12px", backdropFilter: "blur(8px)", maxHeight: "calc(100% - 2rem)", overflowY: "auto" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: "bold", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "white" }}>Legend</div>
              {Object.entries(typeColors).map(([type, color]) => (
                <div key={type} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: color }} />
                  <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.85)" }}>{type}</span>
                </div>
              ))}
            </div>
            
            <GraphVisualizer 
              data={graphData} 
              selectedNodeId={selectedNode?.id || null}
              onNodeClick={setSelectedNode}
              typeColors={typeColors}
            />
          </div>

          {/* Node Detail Panel */}
          <div className="glass-panel" style={{ padding: "1.5rem", overflowY: "auto" }}>
            {selectedNode ? (
              <>
                <div style={{ marginBottom: "1.5rem" }}>
                  <div
                    style={{
                      width: "48px", height: "48px", borderRadius: "12px",
                      background: `${typeColors[selectedNode.type ?? "Entity"] || "#6b7280"}22`,
                      border: `1px solid ${typeColors[selectedNode.type ?? "Entity"] || "#6b7280"}`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      marginBottom: "12px",
                    }}
                  >
                    <span style={{ fontSize: "1.25rem" }}>
                      {selectedNode.type === "Pump" ? "⚙️" : selectedNode.type === "Document" ? "📄" : selectedNode.type === "Failure" ? "🚨" : selectedNode.type === "Regulation" ? "📋" : "🔵"}
                    </span>
                  </div>
                  <h3 style={{ fontSize: "1.25rem", marginBottom: "4px" }}>{selectedNode.id}</h3>
                  <span style={{ fontSize: "0.875rem", color: typeColors[selectedNode.type ?? "Entity"] || "var(--text-muted)" }}>
                    {selectedNode.type}
                  </span>
                </div>

                <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "1.25rem" }}>
                  <h4 style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Connections
                  </h4>
                  {graphData.edges.filter((e) => {
                    const srcId = typeof e.source === 'object' ? (e.source as GraphNode).id : e.source;
                    const tgtId = typeof e.target === 'object' ? (e.target as GraphNode).id : e.target;
                    return srcId === selectedNode.id || tgtId === selectedNode.id;
                  }).map((edge, i) => {
                    const sourceId = typeof edge.source === 'object' ? (edge.source as GraphNode).id : edge.source;
                    const targetId = typeof edge.target === 'object' ? (edge.target as GraphNode).id : edge.target;

                    const isSource = sourceId === selectedNode.id;
                    const otherId = isSource ? targetId : sourceId;
                    const direction = isSource ? "→" : "←";
                    
                    const otherNode = graphData.nodes.find(n => n.id === otherId);
                    
                    return (
                      <div
                        key={i}
                        onClick={() => otherNode && setSelectedNode(otherNode)}
                        style={{ display: "flex", alignItems: "center", gap: "8px", padding: "0.625rem", borderRadius: "8px", cursor: "pointer", marginBottom: "6px", transition: "background 0.2s" }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{direction}</span>
                        <div>
                          <div style={{ fontSize: "0.875rem", fontWeight: 500 }}>{otherId}</div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{edge.label}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>Click a node in the graph to inspect its details and connections.</p>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
