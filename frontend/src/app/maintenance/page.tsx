"use client";

import { useState, useEffect, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Equipment {
  id: string;
  name: string;
  unit: string;
  type: string;
  status: "ok" | "warning" | "alert";
  lastInspection?: string;
}

interface HistoryEvent {
  date: string;
  type: string;
  description: string;
  wo?: string;
}

const STATUS_STYLES: Record<string, { color: string; label: string; dot: string }> = {
  ok: { color: "var(--success)", label: "Normal", dot: "#10b981" },
  warning: { color: "var(--warning)", label: "Monitor", dot: "#f59e0b" },
  alert: { color: "var(--danger)", label: "Action Required", dot: "#ef4444" },
};

function parseEquipmentFromAnswer(answer: string): Equipment[] {
  // Try to parse structured equipment data from the AI answer
  const lines = answer.split("\n").filter(l => l.trim());
  const equipment: Equipment[] = [];

  for (const line of lines) {
    // Match patterns like: P-2003A | Slurry Recycle Pump | FCCU-1 | alert
    const match = line.match(/([A-Z][-A-Z0-9]+[A-Z0-9])\s*[\|:]\s*([^|:]+)[\|:]\s*([^|:]+)[\|:]?\s*(ok|warning|alert)?/i);
    if (match) {
      equipment.push({
        id: match[1].trim(),
        name: match[2].trim(),
        unit: match[3].trim(),
        type: "Equipment",
        status: ((match[4] || "ok").toLowerCase() as Equipment["status"]) ?? "ok",
      });
    }
  }

  // Fallback: extract equipment IDs mentioned in the answer
  if (equipment.length === 0) {
    const idPattern = /\b([A-Z]{1,3}-\d{3,4}[A-Z]?)\b/g;
    const ids = [...new Set(answer.match(idPattern) || [])];
    ids.slice(0, 8).forEach(id => {
      equipment.push({
        id,
        name: id,
        unit: "Plant",
        type: "Equipment",
        status: answer.toLowerCase().includes(id.toLowerCase() + " alert") ||
                answer.toLowerCase().includes(id.toLowerCase() + " critical") ? "alert"
              : answer.toLowerCase().includes(id.toLowerCase() + " warning") ? "warning" : "ok",
      });
    });
  }

  return equipment;
}

function parseHistoryFromAnswer(answer: string): HistoryEvent[] {
  const events: HistoryEvent[] = [];
  const lines = answer.split("\n").filter(l => l.trim());

  for (const line of lines) {
    const dateMatch = line.match(/(\d{4}-\d{2}-\d{2})/);
    const woMatch = line.match(/(WO-[\d-]+)/);
    const typeMatch = line.toLowerCase().includes("corrective") ? "Corrective"
      : line.toLowerCase().includes("preventive") ? "Preventive"
      : line.toLowerCase().includes("inspection") ? "Preventive" : null;

    if (dateMatch && typeMatch) {
      events.push({
        date: dateMatch[1],
        type: typeMatch,
        description: line.replace(/\*+/g, "").replace(dateMatch[1], "").replace(woMatch?.[1] || "", "").trim().slice(0, 120),
        wo: woMatch?.[1],
      });
    }
  }

  return events.slice(0, 8);
}

export default function MaintenancePage() {
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [equipmentLoading, setEquipmentLoading] = useState(true);
  const [selectedEquipment, setSelectedEquipment] = useState<Equipment | null>(null);
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [rcaLoading, setRcaLoading] = useState(false);
  const [rcaResult, setRcaResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch equipment list from orchestrator
  const fetchEquipment = useCallback(async () => {
    setEquipmentLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: "List all tracked equipment in the plant with their IDs, names, unit areas, and current health status (ok/warning/alert). Format each as: ID | Name | Unit | Status",
          user_role: "engineer",
        }),
        signal: AbortSignal.timeout(15000),
      });

      if (res.ok) {
        const data = await res.json();
        const parsed = parseEquipmentFromAnswer(data.answer || "");
        if (parsed.length > 0) {
          setEquipment(parsed);
          setSelectedEquipment(parsed[0]);
        } else {
          setError("Orchestrator is running but no equipment data found in the knowledge graph. Try uploading maintenance records first.");
          setEquipment([]);
        }
      } else {
        throw new Error(`API returned ${res.status}`);
      }
    } catch (err) {
      setError(err instanceof Error && err.name !== "AbortError"
        ? `Could not connect to orchestrator: ${err.message}`
        : "Orchestrator connection timed out. Ensure the backend is running on port 8000.");
      setEquipment([]);
    }
    setEquipmentLoading(false);
  }, []);

  // Fetch maintenance history for selected equipment
  const fetchHistory = useCallback(async (equipmentId: string) => {
    setHistoryLoading(true);
    setHistory([]);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: `Show the complete maintenance history for equipment ${equipmentId}. List each event with: date (YYYY-MM-DD), type (Corrective/Preventive), description, and work order number if available.`,
          equipment_id: equipmentId,
          user_role: "engineer",
        }),
        signal: AbortSignal.timeout(15000),
      });
      if (res.ok) {
        const data = await res.json();
        const events = parseHistoryFromAnswer(data.answer || "");
        setHistory(events);
      }
    } catch {
      setHistory([]);
    }
    setHistoryLoading(false);
  }, []);

  useEffect(() => {
    void fetchEquipment();
  }, [fetchEquipment]);

  useEffect(() => {
    if (selectedEquipment) {
      setRcaResult(null);
      void fetchHistory(selectedEquipment.id);
    }
  }, [selectedEquipment, fetchHistory]);

  const handleGenerateRCA = async () => {
    if (!selectedEquipment) return;
    setRcaLoading(true);
    setRcaResult(null);
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: `Generate a full Root Cause Analysis (RCA) report for equipment ${selectedEquipment.id} (${selectedEquipment.name}). Include: 5-Why analysis, likely root causes, contributing factors, and recommended corrective actions. Use all available maintenance history and knowledge base information.`,
          equipment_id: selectedEquipment.id,
          user_role: "engineer",
        }),
        signal: AbortSignal.timeout(30000),
      });
      const data = await res.json();
      setRcaResult(data.answer);
    } catch (e) {
      setRcaResult(`**Error:** Could not generate RCA. ${e instanceof Error ? e.message : 'Ensure the orchestrator is running on port 8000.'}`);
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
        <p style={{ color: "var(--text-muted)" }}>Equipment health, failure history, and AI-generated root cause analysis — powered by the knowledge graph.</p>
      </div>

      {/* Backend connection error */}
      {error && (
        <div className="glass-panel animate-in" style={{ padding: "1rem 1.25rem", marginBottom: "1.5rem", borderColor: "rgba(245,158,11,0.35)", background: "rgba(245,158,11,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ color: "#fde68a", fontSize: "0.9rem" }}>⚠️ {error}</span>
          <button className="btn-secondary" onClick={fetchEquipment} style={{ fontSize: "0.8rem", padding: "0.4rem 0.8rem" }}>
            Retry
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "1.5rem" }}>
        {/* Equipment List */}
        <div className="glass-panel" style={{ padding: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", padding: "0 0.5rem" }}>
            <h3 style={{ fontSize: "0.875rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Equipment
            </h3>
            <button onClick={fetchEquipment} title="Refresh equipment list" style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
            </button>
          </div>

          {equipmentLoading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} style={{ padding: "1rem", borderRadius: "8px", background: "rgba(255,255,255,0.03)" }}>
                  <div style={{ height: "14px", width: "60%", background: "rgba(255,255,255,0.06)", borderRadius: "4px", marginBottom: "6px" }} />
                  <div style={{ height: "12px", width: "80%", background: "rgba(255,255,255,0.04)", borderRadius: "4px" }} />
                </div>
              ))}
            </div>
          ) : equipment.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", padding: "0.5rem" }}>
              No equipment found. Upload maintenance records to populate this list.
            </p>
          ) : (
            equipment.map((eq) => {
              const st = STATUS_STYLES[eq.status] || STATUS_STYLES.ok;
              return (
                <div
                  key={eq.id}
                  onClick={() => { setSelectedEquipment(eq); setRcaResult(null); }}
                  style={{
                    padding: "1rem",
                    borderRadius: "8px",
                    cursor: "pointer",
                    background: selectedEquipment?.id === eq.id ? "rgba(37, 99, 235, 0.1)" : "transparent",
                    borderLeft: selectedEquipment?.id === eq.id ? "3px solid var(--accent)" : "3px solid transparent",
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
            })
          )}
        </div>

        {/* Main Panel */}
        {selectedEquipment ? (
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
              <h3 style={{ marginBottom: "1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                Maintenance History
                {historyLoading && (
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Loading from knowledge graph...</span>
                )}
              </h3>
              {historyLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {[1, 2].map(i => (
                    <div key={i} style={{ padding: "1rem", background: "rgba(255,255,255,0.03)", borderRadius: "8px" }}>
                      <div style={{ height: "14px", width: "70%", background: "rgba(255,255,255,0.06)", borderRadius: "4px", marginBottom: "6px" }} />
                      <div style={{ height: "12px", width: "50%", background: "rgba(255,255,255,0.04)", borderRadius: "4px" }} />
                    </div>
                  ))}
                </div>
              ) : history.length > 0 ? (
                <div style={{ position: "relative", paddingLeft: "1.5rem" }}>
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
                <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                  No maintenance history found for {selectedEquipment.id}. Upload work orders or maintenance records for this equipment to populate this timeline.
                </p>
              )}
            </div>

            {/* RCA Result */}
            {rcaResult && (
              <div className="glass-panel animate-in" style={{ padding: "1.5rem" }}>
                <h3 style={{ marginBottom: "1.25rem", display: "flex", alignItems: "center", gap: "8px" }}>
                  <span>🔍 AI-Generated RCA Report</span>
                  <span style={{ fontSize: "0.75rem", background: "rgba(16,185,129,0.1)", color: "var(--success)", padding: "2px 8px", borderRadius: "10px" }}>Live</span>
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
        ) : !equipmentLoading && (
          <div className="glass-panel" style={{ padding: "2rem", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem", textAlign: "center" }}>
            <div style={{ fontSize: "3rem" }}>⚙️</div>
            <h3>No Equipment Selected</h3>
            <p style={{ color: "var(--text-muted)" }}>Select an equipment from the list to view its maintenance history and generate an AI RCA report.</p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
