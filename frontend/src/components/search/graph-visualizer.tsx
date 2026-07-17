"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";

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

interface NodeData {
  id: string;
  label?: string;
  type?: string;
  group?: string;
  val?: number;
  [key: string]: any;
}

interface EdgeData {
  source: string;
  target: string;
  label?: string;
  [key: string]: any;
}

interface GraphData {
  nodes: NodeData[];
  edges: EdgeData[];
}

export function GraphVisualizer({
  data,
  onNodeClick,
  selectedNodeId,
}: {
  data: GraphData;
  onNodeClick: (node: NodeData | null) => void;
  selectedNodeId: string | null;
}) {
  const fgRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const handleNodeClick = useCallback((node: any) => {
    onNodeClick(node);
  }, [onNodeClick]);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      {dimensions.width > 0 && dimensions.height > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={{
            nodes: data.nodes.map(n => ({ ...n })),
            links: data.edges.map(e => ({ ...e, source: e.source, target: e.target })),
          }}
          nodeRelSize={6}
          nodeColor={(node: any) => TYPE_COLORS[node.type || "Entity"] || "#6b7280"}
          nodeVal={(node: any) => (node.id === selectedNodeId ? 12 : node.val || 6)}
          linkColor={() => "rgba(148, 163, 184, 0.25)"}
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.25}
          onNodeClick={handleNodeClick}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const label = node.label || node.id;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Inter, sans-serif`;
            
            const color = TYPE_COLORS[node.type || "Entity"] || "#6b7280";
            const isSelected = node.id === selectedNodeId;

            ctx.beginPath();
            ctx.arc(node.x, node.y, isSelected ? 8 : 5, 0, 2 * Math.PI, false);
            ctx.fillStyle = color;
            ctx.fill();
            
            if (isSelected) {
              ctx.lineWidth = 1.5;
              ctx.strokeStyle = 'white';
              ctx.stroke();
            }

            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = isSelected ? 'white' : 'rgba(255, 255, 255, 0.8)';
            ctx.fillText(label, node.x, node.y + (isSelected ? 14 : 10));
          }}
        />
      )}
    </div>
  );
}
