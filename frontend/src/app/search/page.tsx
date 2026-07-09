"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

interface Source {
  doc_id: string;
  text?: string;
  section_title?: string;
  doc_type?: string;
  score?: number;
}

interface SearchResult {
  answer: string;
  agent_used: string;
  sources: Source[];
  confidence: number;
  session_id: string;
  metadata: Record<string, unknown>;
}

const EXAMPLE_QUERIES = [
  "What is the startup procedure for Pump P-2003A?",
  "Why has pump P-2003A had repeated seal failures?",
  "Generate an RCA for the slurry pump failure",
  "Are we compliant with OISD-STD-144 for fire water systems?",
  "Show historical maintenance patterns for CDU-1 equipment",
  "What safety incidents are similar to last month's seal failure?",
];

const ROLE_TAGS: Record<string, string> = {
  KNOWLEDGE_QUERY: "📚 Knowledge",
  MAINTENANCE_QUERY: "🔧 Maintenance",
  COMPLIANCE_QUERY: "📋 Compliance",
  LESSONS_QUERY: "⚠️ Lessons",
  INGESTION: "📥 Ingestion",
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("operator");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (q?: string) => {
    const finalQuery = q || query;
    if (!finalQuery.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: finalQuery, user_role: role }),
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      // For demo, show a mock response
      setResult({
        answer: `**Demo Response** (API not connected)\n\nBased on the maintenance records in the knowledge graph, Pump P-2003A (Slurry Recycle Pump in FCCU-1) has experienced 2 mechanical seal failures in the past 14 months:\n\n1. **August 2023** (WO-2023-4512): Seal failed due to shaft misalignment causing excessive vibration. Root Cause: Incorrect installation procedure after previous overhaul.\n\n2. **March 2024** (WO-2024-1234): Seal abrasion due to high catalyst fines content in slurry exceeding design limits.\n\n**Recommended Actions:**\n- Verify alignment after every major overhaul using laser alignment tools\n- Monitor slurry fines content and maintain flush flow ≥5 m³/hr per OEM manual\n- Consider upgrading to API Plan 54 seal flush to reduce abrasion`,
        agent_used: "MAINTENANCE_QUERY",
        sources: [
          { doc_id: "WO-2023-4512", section_title: "Work Order History", doc_type: "WorkOrder", score: 0.96 },
          { doc_id: "MAN-SLURRY-PUMP", section_title: "Seal Flush Requirements", doc_type: "OEM Manual", score: 0.88 },
        ],
        confidence: 0.92,
        session_id: "demo-session",
        metadata: { route: { category: "MAINTENANCE_QUERY" } },
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  return (
    <div className="animate-in">
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>
          Universal <span className="text-accent">Search & Query</span>
        </h1>
        <p style={{ color: "var(--text-muted)" }}>
          Ask anything — equipment procedures, maintenance history, compliance, or safety patterns.
        </p>
      </div>

      {/* Search Bar */}
      <div className="glass-panel" style={{ padding: "1.5rem", marginBottom: "2rem" }}>
        <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
          <div style={{ flex: 1, position: "relative" }}>
            <input
              id="query-input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about equipment, SOPs, compliance, incidents..."
              style={{
                width: "100%",
                padding: "1rem 1.25rem",
                borderRadius: "10px",
                background: "rgba(15, 23, 42, 0.8)",
                border: "1px solid var(--border-color)",
                color: "white",
                fontSize: "1rem",
                outline: "none",
              }}
            />
          </div>
          <select
            id="role-select"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{
              padding: "1rem",
              borderRadius: "10px",
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid var(--border-color)",
              color: "var(--text-muted)",
              outline: "none",
              minWidth: "140px",
            }}
          >
            <option value="operator">Operator</option>
            <option value="engineer">Engineer</option>
            <option value="manager">Manager</option>
            <option value="auditor">Auditor</option>
          </select>
          <button
            id="search-btn"
            className="btn-primary"
            onClick={() => handleSearch()}
            disabled={loading}
            style={{ minWidth: "120px" }}
          >
            {loading ? (
              <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "spin 1s linear infinite" }}><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
                Thinking...
              </span>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                Ask IKP
              </>
            )}
          </button>
        </div>

        {/* Example Queries */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginRight: "0.5rem", lineHeight: "28px" }}>Try:</span>
          {EXAMPLE_QUERIES.map((q, i) => (
            <button
              key={i}
              onClick={() => {
                setQuery(q);
                handleSearch(q);
              }}
              style={{
                background: "rgba(56, 189, 248, 0.08)",
                border: "1px solid rgba(56, 189, 248, 0.15)",
                color: "var(--accent)",
                padding: "4px 12px",
                borderRadius: "20px",
                fontSize: "0.8125rem",
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {loading && (
        <div className="glass-panel" style={{ padding: "2.5rem", textAlign: "center" }}>
          <div style={{ fontSize: "1rem", color: "var(--text-muted)" }}>
            🔍 Searching across 14,208 documents and 89k knowledge graph nodes...
          </div>
        </div>
      )}

      {result && !loading && (
        <div className="animate-in">
          {/* Agent Tag + Confidence */}
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
            <span style={{ background: "rgba(37, 99, 235, 0.15)", color: "var(--accent)", padding: "4px 14px", borderRadius: "20px", fontSize: "0.875rem", border: "1px solid rgba(37, 99, 235, 0.3)" }}>
              {ROLE_TAGS[result.agent_used] || result.agent_used}
            </span>
            <span style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>
              Confidence: <span style={{ color: result.confidence > 0.8 ? "var(--success)" : "var(--warning)" }}>{Math.round(result.confidence * 100)}%</span>
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1.5rem" }}>
            {/* Answer */}
            <div className="glass-panel" style={{ padding: "2rem" }}>
              <h3 style={{ marginBottom: "1.25rem", fontSize: "1.125rem" }}>Answer</h3>
              <div
                style={{ lineHeight: "1.8", color: "var(--text-main)", whiteSpace: "pre-wrap" }}
                dangerouslySetInnerHTML={{
                  __html: result.answer
                    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                    .replace(/^### (.+)$/gm, '<h3 style="margin: 1.25rem 0 0.75rem; font-size: 1.1rem;">$1</h3>')
                    .replace(/^#### (.+)$/gm, '<h4 style="margin: 1rem 0 0.5rem; font-size: 1rem; color: var(--accent);">$1</h4>')
                    .replace(/^- (.+)$/gm, '<li style="margin-left: 1.25rem; margin-bottom: 0.5rem;">$1</li>'),
                }}
              />
            </div>

            {/* Sources */}
            <div className="glass-panel" style={{ padding: "1.5rem" }}>
              <h3 style={{ marginBottom: "1.25rem", fontSize: "1.125rem" }}>
                Sources <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: "0.875rem" }}>({result.sources.length})</span>
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {result.sources.map((src, i) => (
                  <div
                    key={i}
                    className="glass-card"
                    style={{ padding: "1rem" }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{src.doc_id}</span>
                      {src.score && (
                        <span style={{ fontSize: "0.75rem", color: "var(--success)" }}>{Math.round(src.score * 100)}% match</span>
                      )}
                    </div>
                    {src.section_title && (
                      <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginBottom: "4px" }}>{src.section_title}</div>
                    )}
                    {src.doc_type && (
                      <div style={{ fontSize: "0.75rem", color: "var(--accent)", background: "rgba(56, 189, 248, 0.08)", padding: "2px 8px", borderRadius: "10px", display: "inline-block" }}>
                        {src.doc_type}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
