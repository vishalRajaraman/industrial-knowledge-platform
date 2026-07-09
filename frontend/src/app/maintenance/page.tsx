"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

const EQUIPMENT_LIST = [
  { id: "P-2003A", name: "Slurry Recycle Pump", unit: "FCCU-1", type: "Centrifugal Pump", status: "alert" },
  { id: "P-101A", name: "Crude Charge Pump", unit: "CDU-1", type: "Centrifugal Pump", status: "ok" },
  { id: "C-201", name: "Wet Gas Compressor", unit: "FCCU-1", type: "Centrifugal Compressor", status: "ok" },
  { id: "HE-101", name: "Crude Pre-heat Exchanger", unit: "CDU-1", type: "Shell and Tube", status: "ok" },
  { id: "P-901A", name: "Fire Water Main Pump", unit: "Utilities", type: "Centrifugal Pump", status: "warning" },
];

const DEMO_HISTORY: Record<string, { date: string; type: string; description: string; wo?: string }[]> = {
  "P-2003A": [
    { date: "2024-03-12", type: "Corrective", description: "Mechanical seal replacement after abrasion failure", wo: "WO-2024-1234" },
    { date: "2023-08-15", type: "Corrective", description: "Mechanical seal replaced due to shaft misalignment vibration", wo: "WO-2023-4512" },
    { date: "2023-05-02", type: "Preventive", description: "Quarterly inspection - all parameters within spec" },
    { date: "2022-11-08", type: "Corrective", description: "Bearing replacement" },
  ],
  "P-101A": [
    { date: "2024-01-20", type: "Preventive", description: "Annual inspection — no issues" },
    { date: "2023-06-15", type: "Preventive", description: "Impeller wear check — passed" },
  ],
};

const STATUS_STYLES: Record<string, { color: string; label: string; dot: string }> = {
  ok: { color: "var(--success)", label: "Normal", dot: "#10b981" },
  warning: { color: "var(--warning)", label: "Monitor", dot: "#f59e0b" },
  alert: { color: "var(--danger)", label: "Action Required", dot: "#ef4444" },
};

export default function MaintenancePage() {
  const [selectedEquipment, setSelectedEquipment] = useState(EQUIPMENT_LIST[0]);
  const [rcaLoading, setRcaLoading] = useState(false);
  const [rcaResult, setRcaResult] = useState<string | null>(null);

  const history = DEMO_HISTORY[selectedEquipment.id] || [];

  const handleGenerateRCA = async () => {
    setRcaLoading(true);
    setRcaResult(null);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: `Generate a full RCA for equipment ${selectedEquipment.id} (${selectedEquipment.name}) repeated seal failures`,
          equipment_id: selectedEquipment.id,
          user_role: "engineer",
        }),
      });
      const data = await res.json();
      setRcaResult(data.answer);
    } catch {
      // Demo fallback
      setRcaResult(
        `### Root Cause Analysis Draft: ${selectedEquipment.id}\n\n**Incident:** Recurring mechanical seal failures (2 in 14 months)\n\n#### 5-Why Analysis\n1. The mechanical seal failed → causing leakage and unplanned shutdown\n2. The seal failed due to excessive axial thrust and abrasion\n3. Abrasion was caused by high catalyst fines in slurry (above design limit)\n4. Catalyst fines rose due to regenerator cyclone degradation\n5. Cyclone degradation was not detected in time due to gaps in inspection schedule\n\n**Likely Root Cause:** Insufficient inspection frequency on regenerator cyclones allowing catalyst fines to exceed slurry pump design limits.\n\n#### Recommended Actions\n- Increase cyclone inspection frequency to monthly\n- Install online particle size monitor on slurry line\n- Upgrade seal flush to API Plan 54 with clean oil to reduce abrasion\n- Implement laser alignment verification after every seal replacement`
      );
    } finally {
      setRcaLoading(false);
    }
  };

  return (
    <div className="animate-in">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
          Predictive <span className="text-accent">Maintenance & RCA</span>
        </h1>
        <p style={{ color: "var(--text-muted)" }}>Equipment health, failure history, and AI-generated root cause analysis.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.5rem" }}>
        {/* Equipment List */}
        <div className="glass-panel" style={{ padding: "1rem" }}>
          <h3 style={{ fontSize: "0.875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "1rem", padding: "0 0.5rem" }}>
            Equipment
          </h3>
          {EQUIPMENT_LIST.map((eq) => {
            const st = STATUS_STYLES[eq.status];
            return (
              <div
                key={eq.id}
                onClick={() => { setSelectedEquipment(eq); setRcaResult(null); }}
                style={{
                  padding: "1rem",
                  borderRadius: "8px",
                  cursor: "pointer",
                  background: selectedEquipment.id === eq.id ? "rgba(37, 99, 235, 0.1)" : "transparent",
                  borderLeft: selectedEquipment.id === eq.id ? "3px solid var(--accent)" : "3px solid transparent",
                  marginBottom: "4px",
                  transition: "all 0.2s",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <span style={{ fontWeight: 600 }}>{eq.id}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                    <div style={{ width: "7px", height: "7px", borderRadius: "50%", background: st.dot, boxShadow: `0 0 6px ${st.dot}` }} />
                    <span style={{ fontSize: "0.75rem", color: st.color }}>{st.label}</span>
                  </div>
                </div>
                <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{eq.name}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>{eq.unit}</div>
              </div>
            );
          })}
        </div>

        {/* Main Panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Equipment Header */}
          <div className="glass-panel" style={{ padding: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h2 style={{ fontSize: "1.5rem", marginBottom: "4px" }}>{selectedEquipment.id} — {selectedEquipment.name}</h2>
              <div style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{selectedEquipment.type} · {selectedEquipment.unit}</div>
            </div>
            <button
              id="generate-rca-btn"
              className="btn-primary"
              onClick={handleGenerateRCA}
              disabled={rcaLoading}
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              {rcaLoading ? (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "spin 1s linear infinite" }}><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
                  Generating RCA...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                  Generate AI RCA
                </>
              )}
            </button>
          </div>

          {/* Maintenance History */}
          <div className="glass-panel" style={{ padding: "1.5rem" }}>
            <h3 style={{ marginBottom: "1.25rem" }}>Maintenance History</h3>
            {history.length > 0 ? (
              <div style={{ position: "relative", paddingLeft: "1.5rem" }}>
                {/* Timeline line */}
                <div style={{ position: "absolute", left: "5px", top: 0, bottom: 0, width: "2px", background: "rgba(255,255,255,0.07)" }} />
                {history.map((event, i) => (
                  <div key={i} style={{ position: "relative", marginBottom: "1.5rem", paddingLeft: "1.5rem" }}>
                    <div style={{
                      position: "absolute", left: "-18px", top: "4px", width: "10px", height: "10px", borderRadius: "50%",
                      background: event.type === "Corrective" ? "var(--danger)" : "var(--success)",
                      border: "2px solid var(--bg-color)",
                    }} />
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                      <span style={{ fontWeight: 600, fontSize: "0.9375rem" }}>{event.description}</span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", whiteSpace: "nowrap", marginLeft: "1rem" }}>{event.date}</span>
                    </div>
                    <div style={{ display: "flex", gap: "0.75rem" }}>
                      <span style={{
                        fontSize: "0.75rem", padding: "2px 8px", borderRadius: "10px",
                        background: event.type === "Corrective" ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.1)",
                        color: event.type === "Corrective" ? "var(--danger)" : "var(--success)",
                      }}>
                        {event.type}
                      </span>
                      {event.wo && <span style={{ fontSize: "0.75rem", color: "var(--accent)" }}>{event.wo}</span>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)" }}>No maintenance history available for this equipment.</p>
            )}
          </div>

          {/* RCA Result */}
          {rcaResult && (
            <div className="glass-panel animate-in" style={{ padding: "1.5rem" }}>
              <h3 style={{ marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>🔍 AI-Generated RCA Report</span>
                <span style={{ fontSize: "0.75rem", background: "rgba(16,185,129,0.1)", color: "var(--success)", padding: "2px 8px", borderRadius: "10px" }}>Draft</span>
              </h3>
              <div
                style={{ lineHeight: "1.8", color: "var(--text-main)", whiteSpace: "pre-wrap" }}
                dangerouslySetInnerHTML={{
                  __html: rcaResult
                    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                    .replace(/^### (.+)$/gm, '<h3 style="margin: 1.25rem 0 0.75rem; font-size: 1.1rem; color: var(--accent);">$1</h3>')
                    .replace(/^#### (.+)$/gm, '<h4 style="margin: 1rem 0 0.5rem; font-size: 1rem;">$1</h4>')
                    .replace(/^(\d+)\. (.+)$/gm, '<div style="margin-left: 1rem; margin-bottom: 0.5rem;"><strong>$1.</strong> $2</div>')
                    .replace(/^- (.+)$/gm, '<li style="margin-left: 1.5rem; margin-bottom: 0.375rem;">$1</li>'),
                }}
              />
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
