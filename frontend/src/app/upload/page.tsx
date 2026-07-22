"use client";

import { useState, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { GATEWAY_API_BASE } from "@/lib/gateway";

const GraphVisualizer = dynamic(
  () => import("@/components/search/graph-visualizer").then((mod) => mod.GraphVisualizer),
  { ssr: false, loading: () => <div style={{ height: "100%", display: "grid", placeItems: "center" }}>Loading Graph...</div> }
);

const DOC_TYPES = [
  { value: "industrial_doc", label: "Industrial Documents (PDF or Excel)", icon: "📄" },
  { value: "pid_yolo", label: "P&ID using YOLO model", icon: "📐" },
  { value: "layout_drawing", label: "Industrial layout drawing", icon: "🗺️" },
];

interface UploadResult {
  doc_id: string;
  status: string;
  result: any; // We'll receive the real output from the orchestrator here
}

export default function UploadPage() {
  const [docType, setDocType] = useState("industrial_doc");
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Generate local graph data from the result so it displays instantly
  const graphData = useMemo(() => {
    if (!result?.result) return { nodes: [], edges: [] };
    const res = result.result;
    const docId = result.doc_id;

    const nodes: any[] = [{ id: docId, type: "Document", label: "Document" }];
    const edges: any[] = [];

    // Drawing regions (layout_drawing)
    if (res.extracted_data?.length > 0) {
      res.extracted_data.forEach((region: any, i: number) => {
        const regionId = `region_${i}_${region.label}`;
        nodes.push({ id: regionId, type: "DrawingRegion", label: region.label });
        edges.push({ source: regionId, target: docId, label: "DEPICTED_IN" });
        // Connect adjacent regions
        if (i < res.extracted_data.length - 1) {
          const nextId = `region_${i+1}_${res.extracted_data[i+1].label}`;
          edges.push({ source: regionId, target: nextId, label: "ADJACENT_TO" });
        }
      });
    }

    // P&ID equipment
    if (res.equipment_detected?.length > 0) {
      res.equipment_detected.forEach((eq: any, i: number) => {
        nodes.push({ id: eq.tag, type: eq.label || "Equipment", label: eq.tag });
        edges.push({ source: eq.tag, target: docId, label: "DEPICTED_IN" });
        if (i < res.equipment_detected.length - 1) {
          edges.push({ source: eq.tag, target: res.equipment_detected[i+1].tag, label: "CONNECTED_TO" });
        }
      });
    }

    // PDF entities
    if (res.entities_extracted?.length > 0) {
      res.entities_extracted.forEach((ent: any) => {
         const text = typeof ent === 'string' ? ent : ent.text;
         const type = typeof ent === 'string' ? 'Entity' : (ent.label || 'Entity');
         nodes.push({ id: text, type: type, label: text });
         edges.push({ source: text, target: docId, label: "MENTIONED_IN" });
      });
    }

    return { nodes, edges };
  }, [result]);

  const typeColors = useMemo(() => {
    return {
      "Document": "hsl(0, 75%, 60%)",
      "DrawingRegion": "hsl(210, 80%, 65%)",
      "Pump": "hsl(137, 75%, 60%)",
      "Valve": "hsl(274, 75%, 60%)",
      "Entity": "hsl(50, 75%, 60%)",
      "Equipment": "hsl(200, 75%, 60%)",
    };
  }, []);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      // Route directly to the Orchestrator which implements the real AI pipelines (YOLO, etc)
      // rather than the API gateway stub
      const res = await fetch(`http://localhost:8000/upload?doc_type=${docType}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();
      
      if (data.result && data.result.error) {
        throw new Error(data.result.error);
      }

      // The orchestrator returns the full result synchronously
      setResult({
        doc_id: data.doc_id,
        status: data.status,
        result: data.result || {}, // Contains equipment_detected, etc.
      });
    } catch (err: any) {
      console.warn("Upload error:", err);
      setError(err.message || "Pipeline processing failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  return (
    <div className="animate-in">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
          Ingest <span className="text-accent">New Documents</span>
        </h1>
        <p style={{ color: "var(--text-muted)" }}>
          Upload PDFs, Excel files, P&IDs, maintenance records, and more. The AI pipeline will parse, extract, and index everything automatically.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
        {/* Upload Config */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1.25rem" }}>Document Settings</h3>
            <div style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>Document Type</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                {DOC_TYPES.map((dt) => (
                  <button
                    key={dt.value}
                    onClick={() => setDocType(dt.value)}
                    style={{
                      padding: "0.75rem",
                      borderRadius: "8px",
                      border: `1px solid ${docType === dt.value ? "rgba(56, 189, 248, 0.5)" : "rgba(255,255,255,0.07)"}`,
                      background: docType === dt.value ? "rgba(56, 189, 248, 0.08)" : "rgba(15, 23, 42, 0.5)",
                      color: docType === dt.value ? "var(--accent)" : "var(--text-muted)",
                      textAlign: "left",
                      cursor: "pointer",
                      transition: "all 0.2s",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      fontSize: "0.8125rem",
                    }}
                  >
                    <span>{dt.icon}</span>
                    {dt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Plant/Site removed as requested */}
          </div>

          {/* Pipeline Info */}
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1.25rem", fontSize: "1rem" }}>Processing Pipeline</h3>
            {[
              { icon: "📄", title: "Parse", desc: "OCR / PDF / Excel extraction" },
              { icon: "🧠", title: "Extract", desc: "NER entities + triplets" },
              { icon: "🔗", title: "Chunk & Embed", desc: "1024-dim semantic embeddings" },
              { icon: "💾", title: "Store", desc: "Vector DB + Knowledge Graph" },
            ].map((step, i) => (
              <div key={i} style={{ display: "flex", gap: "12px", marginBottom: i < 3 ? "1rem" : 0 }}>
                <div style={{ width: "36px", height: "36px", borderRadius: "8px", background: "rgba(37, 99, 235, 0.1)", border: "1px solid rgba(37, 99, 235, 0.2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  {step.icon}
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.875rem" }}>{step.title}</div>
                  <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Drop Zone + Results */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div
            className="glass-panel"
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              padding: "3rem 2rem",
              textAlign: "center",
              cursor: "pointer",
              border: `2px dashed ${dragOver ? "var(--accent)" : "rgba(255,255,255,0.1)"}`,
              background: dragOver ? "rgba(56, 189, 248, 0.05)" : "rgba(30, 41, 59, 0.4)",
              transition: "all 0.3s",
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: "none" }}
              accept=".pdf,.xlsx,.csv,.docx,.png,.jpg,.tiff,.eml,.msg"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleUpload(file);
              }}
            />
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>{uploading ? "⚙️" : "📁"}</div>
            <h3 style={{ marginBottom: "0.5rem" }}>
              {uploading ? "Processing..." : "Drop file here or click to browse"}
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
              Supports: PDF, Excel, PNG/TIFF (drawings), Email (.eml), Word
            </p>
            {uploading && (
              <div style={{ marginTop: "1.5rem" }}>
                <div style={{ height: "4px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: "60%", background: "linear-gradient(90deg, var(--primary), var(--accent))", borderRadius: "2px", animation: "progress 1.5s ease-in-out infinite" }} />
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginTop: "0.75rem" }}>Running ingestion pipeline...</div>
              </div>
            )}
          </div>

          {/* Error Banner */}
          {error && !uploading && (
            <div className="glass-panel animate-in" style={{ padding: "1rem 1.25rem", borderColor: "rgba(239,68,68,0.35)", background: "rgba(239,68,68,0.08)", display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "1.1rem" }}>⚠️</span>
              <span style={{ color: "#fecaca", fontSize: "0.9rem" }}>{error}</span>
            </div>
          )}

          {/* Pipeline Result */}
          {result && !uploading && (
            <div className="glass-panel animate-in" style={{ padding: "1.5rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "1.25rem" }}>
                <span style={{ fontSize: "1.25rem" }}>✅</span>
                <h3>Ingestion Complete</h3>
              </div>
              <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
                Doc ID: <code style={{ color: "var(--accent)" }}>{result.doc_id}</code>
              </div>

              {/* Rich Visualizations based on Doc Type */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div>
                  <h4 style={{ marginBottom: '0.75rem', color: 'var(--accent)' }}>Detected Entities (Real Data)</h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {result.result?.extracted_data?.length > 0 ? (
                      result.result.extracted_data.map((region: any, idx: number) => (
                        <span key={idx} style={{ padding: '4px 10px', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '16px', fontSize: '0.75rem', color: 'white' }}>
                          🗺️ {region.label} <span style={{opacity: 0.6, fontSize: '0.65rem', marginLeft: '4px'}}>(Region)</span>
                        </span>
                      ))
                    ) : result.result?.equipment_detected?.length > 0 ? (
                      result.result.equipment_detected.map((eq: any, idx: number) => (
                        <span key={idx} style={{ padding: '4px 10px', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '16px', fontSize: '0.75rem', color: 'white' }}>
                          {eq.label} ({eq.tag})
                        </span>
                      ))
                    ) : (result.result?.entities_extracted || []).length > 0 ? (
                      result.result.entities_extracted.map((ent: any, idx: number) => {
                        const text = typeof ent === 'string' ? ent : ent.text;
                        const label = typeof ent === 'string' ? 'Entity' : ent.label;
                        return (
                          <span key={idx} style={{ padding: '4px 10px', background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: '16px', fontSize: '0.75rem', color: 'white' }}>
                            {text} <span style={{opacity: 0.6, fontSize: '0.65rem', marginLeft: '4px'}}>({label})</span>
                          </span>
                        );
                      })
                    ) : (
                       <span style={{ padding: '4px 10px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '16px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>No entities found.</span>
                    )}
                  </div>
                </div>

                {/* Instant Knowledge Graph View */}
                <div>
                  <h4 style={{ marginBottom: '0.75rem', color: 'var(--accent)' }}>Live Knowledge Graph Preview</h4>
                  <div style={{ height: '300px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', position: 'relative', overflow: 'hidden' }}>
                    <GraphVisualizer 
                      data={graphData} 
                      selectedNodeId={null}
                      onNodeClick={() => {}}
                      typeColors={typeColors}
                    />
                    <div style={{ position: 'absolute', bottom: '10px', right: '10px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Nodes: {graphData.nodes.length} | Edges: {graphData.edges.length}
                    </div>
                  </div>
                </div>

                {docType === 'pid_yolo' && result.result?.pipeline_lines_detected !== undefined && (
                  <div>
                    <h4 style={{ marginBottom: '0.75rem', color: 'var(--accent)' }}>P&ID Pipeline Connections</h4>
                    <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                       <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Lines Detected</div>
                       <div style={{ fontWeight: 600, color: 'white' }}>{result.result.pipeline_lines_detected} connection segments found</div>
                       
                       <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Status</div>
                       <div style={{ fontWeight: 600, color: 'var(--success)' }}>{result.result.kg_status || 'Writing to Neo4j'}</div>
                    </div>
                  </div>
                )}

                {result.result?.annotated_image_path && (
                  <div>
                    <h4 style={{ marginBottom: '0.75rem', color: 'var(--accent)' }}>Annotated Image</h4>
                    <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <img 
                        src={`http://localhost:8000/image?path=${encodeURIComponent(result.result.annotated_image_path)}`}
                        alt="Annotated diagram"
                        style={{ width: '100%', height: 'auto', display: 'block' }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes progress {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(250%); }
        }
      `}</style>
    </div>
  );
}
