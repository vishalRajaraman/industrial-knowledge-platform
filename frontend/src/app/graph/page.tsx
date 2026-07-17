"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import { GATEWAY_API_BASE, SearchResponse } from "@/lib/gateway";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { useSession } from "@/components/auth/session-provider";

// Dynamically import the visualizer to avoid SSR issues with Canvas/window
const GraphVisualizer = dynamic(
  () => import("@/components/search/graph-visualizer").then((mod) => mod.GraphVisualizer),
  { ssr: false, loading: () => <div className="glass-panel" style={{ height: "100%", display: "grid", placeItems: "center", color: "var(--text-muted)" }}>Loading Graph Engine...</div> }
);

const DEMO_NODES = [
  { id: "P-2003A", label: "P-2003A", type: "Pump" },
  { id: "COL-201", label: "COL-201", type: "Column" },
  { id: "FCCU-1", label: "FCCU-1", type: "Unit" },
  { id: "SOP-PUMP-003", label: "SOP-PUMP-003", type: "Document" },
  { id: "MAN-SLURRY-PUMP", label: "MAN-SLURRY-PUMP", type: "Document" },
  { id: "FAIL-2023-08", label: "Failure Aug 2023", type: "Failure" },
  { id: "FAIL-2024-03", label: "Failure Mar 2024", type: "Failure" },
  { id: "RC-MISALIGN", label: "Misalignment", type: "RootCause" },
  { id: "RC-ABRASION", label: "Seal Abrasion", type: "RootCause" },
  { id: "OISD-STD-144", label: "OISD-144", type: "Regulation" },
];

const DEMO_EDGES = [
  { source: "P-2003A", target: "COL-201", label: "CONNECTED_TO" },
  { source: "COL-201", target: "P-2003A", label: "CONNECTED_TO" },
  { source: "FCCU-1", target: "P-2003A", label: "CONTAINS" },
  { source: "SOP-PUMP-003", target: "P-2003A", label: "REFERENCES" },
  { source: "MAN-SLURRY-PUMP", target: "P-2003A", label: "REFERENCES" },
  { source: "FAIL-2023-08", target: "P-2003A", label: "OCCURRED_ON" },
  { source: "FAIL-2024-03", target: "P-2003A", label: "OCCURRED_ON" },
  { source: "FAIL-2023-08", target: "RC-MISALIGN", label: "HAS_ROOT_CAUSE" },
  { source: "FAIL-2024-03", target: "RC-ABRASION", label: "HAS_ROOT_CAUSE" },
  { source: "MAN-SLURRY-PUMP", target: "OISD-STD-144", label: "COMPLIES_WITH" },
];

const TYPE_COLORS: Record<string, string> = {
  Pump: "#2563eb",
  Column: "#7c3aed",
  Unit: "#0891b2",
  Document: "#16a34a",
  Failure: "#ef4444",
  RootCause: "#f59e0b",
  Regulation: "#0d9488",
  Entity: "#6b7280",
};

export default function GraphPage() {
  const { session } = useSession();
  const [searchEntity, setSearchEntity] = useState("P-2003A");
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  
  const [graphData, setGraphData] = useState({ nodes: DEMO_NODES, edges: DEMO_EDGES });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSelectedNode(null);

    try {
      const response = await fetch(`${GATEWAY_API_BASE}/search/graph`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ query: query.trim(), depth: 2, session_id: session?.username }),
      });

      if (!response.ok) throw new Error(`API returned ${response.status}`);
      
      const data = await response.json() as SearchResponse;
      
      // If the backend stub returns empty results, we fallback to our demo data so the visualizer works.
      const hasNodes = data.meta?.nodes && Array.isArray(data.meta.nodes) && data.meta.nodes.length > 0;
      
      if (hasNodes) {
        setGraphData({
          nodes: (data.meta?.nodes as any[]) || [],
          edges: (data.meta?.edges as any[]) || [],
        });
      } else {
        // Fallback for stub
        setGraphData({ nodes: DEMO_NODES, edges: DEMO_EDGES });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
      // Fallback on error to demo data
      setGraphData({ nodes: DEMO_NODES, edges: DEMO_EDGES });
    } finally {
      setLoading(false);
    }
  }, [session]);

  // Initial load
  useEffect(() => {
    fetchGraph(searchEntity);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ProtectedRoute allowedRoles={["manager", "engineer"]}>
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
            Warning: {error}. Falling back to sample data.
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "1.5rem", flex: 1, minHeight: 0 }}>
          {/* Graph Canvas */}
          <div className="glass-panel" style={{ position: "relative", overflow: "hidden", background: "#050816" }}>
            {/* Legend */}
            <div style={{ position: "absolute", top: "1rem", left: "1rem", display: "flex", flexDirection: "column", gap: "6px", zIndex: 10, background: "rgba(15,23,42,0.6)", padding: "1rem", borderRadius: "12px", backdropFilter: "blur(8px)" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: "bold", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "white" }}>Legend</div>
              {Object.entries(TYPE_COLORS).slice(0, 7).map(([type, color]) => (
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
                      background: `${TYPE_COLORS[selectedNode.type] || "#6b7280"}22`,
                      border: `1px solid ${TYPE_COLORS[selectedNode.type] || "#6b7280"}`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      marginBottom: "12px",
                    }}
                  >
                    <span style={{ fontSize: "1.25rem" }}>
                      {selectedNode.type === "Pump" ? "⚙️" : selectedNode.type === "Document" ? "📄" : selectedNode.type === "Failure" ? "🚨" : selectedNode.type === "Regulation" ? "📋" : "🔵"}
                    </span>
                  </div>
                  <h3 style={{ fontSize: "1.25rem", marginBottom: "4px" }}>{selectedNode.id}</h3>
                  <span style={{ fontSize: "0.875rem", color: TYPE_COLORS[selectedNode.type] || "var(--text-muted)" }}>
                    {selectedNode.type}
                  </span>
                </div>

                <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "1.25rem" }}>
                  <h4 style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Connections
                  </h4>
                  {graphData.edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id || (e.source as any).id === selectedNode.id || (e.target as any).id === selectedNode.id).map((edge, i) => {
                    const sourceId = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
                    const targetId = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
                    
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
