"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

// Demo graph data for a subgraph around P-2003A
const DEMO_NODES = [
  { id: "P-2003A", label: "P-2003A", type: "Pump", x: 400, y: 280 },
  { id: "COL-201", label: "COL-201", type: "Column", x: 180, y: 280 },
  { id: "FCCU-1", label: "FCCU-1", type: "Unit", x: 400, y: 120 },
  { id: "SOP-PUMP-003", label: "SOP-PUMP-003", type: "Document", x: 600, y: 160 },
  { id: "MAN-SLURRY-PUMP", label: "MAN-SLURRY-PUMP", type: "Document", x: 640, y: 340 },
  { id: "FAIL-2023-08", label: "Failure Aug 2023", type: "Failure", x: 200, y: 160 },
  { id: "FAIL-2024-03", label: "Failure Mar 2024", type: "Failure", x: 160, y: 400 },
  { id: "RC-MISALIGN", label: "Misalignment", type: "RootCause", x: 60, y: 120 },
  { id: "RC-ABRASION", label: "Seal Abrasion", type: "RootCause", x: 40, y: 440 },
  { id: "OISD-STD-144", label: "OISD-144", type: "Regulation", x: 600, y: 460 },
];

const DEMO_EDGES = [
  { from: "P-2003A", to: "COL-201", label: "CONNECTED_TO" },
  { from: "COL-201", to: "P-2003A", label: "CONNECTED_TO" },
  { from: "FCCU-1", to: "P-2003A", label: "CONTAINS" },
  { from: "SOP-PUMP-003", to: "P-2003A", label: "REFERENCES" },
  { from: "MAN-SLURRY-PUMP", to: "P-2003A", label: "REFERENCES" },
  { from: "FAIL-2023-08", to: "P-2003A", label: "OCCURRED_ON" },
  { from: "FAIL-2024-03", to: "P-2003A", label: "OCCURRED_ON" },
  { from: "FAIL-2023-08", to: "RC-MISALIGN", label: "HAS_ROOT_CAUSE" },
  { from: "FAIL-2024-03", to: "RC-ABRASION", label: "HAS_ROOT_CAUSE" },
  { from: "MAN-SLURRY-PUMP", to: "OISD-STD-144", label: "COMPLIES_WITH" },
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

function GraphSVG({
  nodes,
  edges,
  selectedNode,
  onNodeClick,
}: {
  nodes: typeof DEMO_NODES;
  edges: typeof DEMO_EDGES;
  selectedNode: string | null;
  onNodeClick: (id: string) => void;
}) {
  return (
    <svg width="100%" height="100%" viewBox="0 0 700 580" style={{ fontFamily: "Inter, sans-serif" }}>
      {/* Edges */}
      {edges.map((edge, i) => {
        const from = nodes.find((n) => n.id === edge.from);
        const to = nodes.find((n) => n.id === edge.to);
        if (!from || !to) return null;
        const mx = (from.x + to.x) / 2;
        const my = (from.y + to.y) / 2;
        return (
          <g key={i}>
            <line
              x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="rgba(148, 163, 184, 0.25)" strokeWidth="1.5"
              markerEnd="url(#arrowhead)"
            />
            <text x={mx} y={my - 5} fill="rgba(148, 163, 184, 0.6)" fontSize="9" textAnchor="middle">
              {edge.label}
            </text>
          </g>
        );
      })}

      {/* Arrow marker */}
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="rgba(148, 163, 184, 0.4)" />
        </marker>
      </defs>

      {/* Nodes */}
      {nodes.map((node) => {
        const color = TYPE_COLORS[node.type] || "#6b7280";
        const isSelected = selectedNode === node.id;
        return (
          <g key={node.id} onClick={() => onNodeClick(node.id)} style={{ cursor: "pointer" }}>
            <circle
              cx={node.x} cy={node.y} r={isSelected ? 36 : 30}
              fill={`${color}22`}
              stroke={isSelected ? color : `${color}88`}
              strokeWidth={isSelected ? 2.5 : 1.5}
              style={{ transition: "all 0.3s" }}
            />
            {isSelected && (
              <circle cx={node.x} cy={node.y} r={42} fill="none" stroke={color} strokeWidth="1" strokeDasharray="4 4" opacity="0.6" />
            )}
            <text x={node.x} y={node.y - 2} fill="white" fontSize="10" fontWeight="600" textAnchor="middle">{node.id.split("-").slice(0, 2).join("-")}</text>
            <text x={node.x} y={node.y + 14} fill={color} fontSize="9" textAnchor="middle">{node.type}</text>
          </g>
        );
      })}
    </svg>
  );
}

export default function GraphPage() {
  const [searchEntity, setSearchEntity] = useState("P-2003A");
  const [selectedNode, setSelectedNode] = useState<string | null>("P-2003A");

  const selectedNodeData = DEMO_NODES.find((n) => n.id === selectedNode);

  return (
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
            placeholder="Enter entity ID..."
            style={{ padding: "0.625rem 1rem", borderRadius: "8px", background: "rgba(15,23,42,0.8)", border: "1px solid var(--border-color)", color: "white", outline: "none" }}
          />
          <button className="btn-primary">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            Explore
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "1.5rem", flex: 1, minHeight: 0 }}>
        {/* Graph Canvas */}
        <div className="glass-panel" style={{ position: "relative", overflow: "hidden" }}>
          {/* Legend */}
          <div style={{ position: "absolute", top: "1rem", left: "1rem", display: "flex", flexDirection: "column", gap: "6px", zIndex: 10 }}>
            {Object.entries(TYPE_COLORS).slice(0, 6).map(([type, color]) => (
              <div key={type} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: color }} />
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{type}</span>
              </div>
            ))}
          </div>
          <GraphSVG
            nodes={DEMO_NODES}
            edges={DEMO_EDGES}
            selectedNode={selectedNode}
            onNodeClick={setSelectedNode}
          />
        </div>

        {/* Node Detail Panel */}
        <div className="glass-panel" style={{ padding: "1.5rem", overflowY: "auto" }}>
          {selectedNodeData ? (
            <>
              <div style={{ marginBottom: "1.5rem" }}>
                <div
                  style={{
                    width: "48px", height: "48px", borderRadius: "12px",
                    background: `${TYPE_COLORS[selectedNodeData.type] || "#6b7280"}22`,
                    border: `1px solid ${TYPE_COLORS[selectedNodeData.type] || "#6b7280"}`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    marginBottom: "12px",
                  }}
                >
                  <span style={{ fontSize: "1.25rem" }}>
                    {selectedNodeData.type === "Pump" ? "⚙️" : selectedNodeData.type === "Document" ? "📄" : selectedNodeData.type === "Failure" ? "🚨" : selectedNodeData.type === "Regulation" ? "📋" : "🔵"}
                  </span>
                </div>
                <h3 style={{ fontSize: "1.25rem", marginBottom: "4px" }}>{selectedNodeData.id}</h3>
                <span style={{ fontSize: "0.875rem", color: TYPE_COLORS[selectedNodeData.type] || "var(--text-muted)" }}>
                  {selectedNodeData.type}
                </span>
              </div>

              <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "1.25rem" }}>
                <h4 style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Connections
                </h4>
                {DEMO_EDGES.filter((e) => e.from === selectedNodeData.id || e.to === selectedNodeData.id).map((edge, i) => {
                  const other = edge.from === selectedNodeData.id ? edge.to : edge.from;
                  const direction = edge.from === selectedNodeData.id ? "→" : "←";
                  return (
                    <div
                      key={i}
                      onClick={() => setSelectedNode(other)}
                      style={{ display: "flex", alignItems: "center", gap: "8px", padding: "0.625rem", borderRadius: "8px", cursor: "pointer", marginBottom: "6px", transition: "background 0.2s" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{direction}</span>
                      <div>
                        <div style={{ fontSize: "0.875rem", fontWeight: 500 }}>{other}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{edge.label}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <p style={{ color: "var(--text-muted)" }}>Click a node to inspect.</p>
          )}
        </div>
      </div>
    </div>
  );
}
