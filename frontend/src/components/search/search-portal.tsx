"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getRoleLandingPath } from "@/lib/auth";
import { GATEWAY_API_BASE, type SearchHit, type SearchResponse } from "@/lib/gateway";
import { useSession } from "@/components/auth/session-provider";
import { SearchResults } from "./search-results";

const EXAMPLE_QUERIES = [
  "Why is Pump P-2003A vibrating?",
  "Show SOPs for slurry pump maintenance",
  "What compliance evidence exists for fire water systems?",
  "Find documents about seal replacement after abrasion",
  "Show engineering manuals for FCCU-1 equipment",
];

function normalizeHits(payload: SearchResponse): SearchHit[] {
  return payload.results || payload.hits || payload.documents || [];
}

export function SearchPortal() {
  const router = useRouter();
  const { session, logout } = useSession();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(8);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);

  const hits = useMemo(() => (result ? normalizeHits(result) : []), [result]);

  const runSearch = async (searchQuery: string, mode: "vector" | "graph" = "vector") => {
    if (!session) {
      router.replace("/login");
      return;
    }

    if (!searchQuery.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const endpoint = mode === "vector" ? "/search/vector" : "/search/graph";
      const body = mode === "vector" 
        ? { query: searchQuery.trim(), top_k: topK, filters: null, session_id: session.username }
        : { query: searchQuery.trim(), depth: 2, params: {}, session_id: session.username };

      const response = await fetch(`${GATEWAY_API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (response.status === 401) {
        logout();
        router.replace("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(`Search failed with status ${response.status}`);
      }

      const data = (await response.json()) as SearchResponse;
      setResult(data);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : `Unable to execute ${mode} search`);
      setResult({
        status: "error",
        mode: mode,
        query: searchQuery,
        session_id: session.username,
        results: [],
        meta: { fallback: true },
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-in" style={{ display: "grid", gap: "1.5rem" }}>
      <section className="glass-panel" style={{ padding: "1.75rem", background: "linear-gradient(135deg, rgba(37,99,235,0.12), rgba(56,189,248,0.06))" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", marginBottom: "1.35rem" }}>
          <div>
            <h1 style={{ fontSize: "2rem", marginBottom: "0.4rem" }}>Cross-Functional Search Portal</h1>
            <p style={{ color: "var(--text-muted)", lineHeight: 1.7 }}>
              Unified semantic search for engineering and management workflows. Signed in as {session?.username} ({session?.role}).
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
            <button className="btn-secondary" onClick={() => router.push(getRoleLandingPath(session?.role || "field_tech"))}>
              Back to dashboard
            </button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "0.85rem", alignItems: "start" }}>
          <label style={{ display: "grid", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.84rem", color: "var(--text-muted)" }}>Ask a question</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search maintenance manuals, SOPs, work orders, or compliance records..."
              rows={3}
              style={{ width: "100%", resize: "vertical", minHeight: "92px", padding: "1rem 1.1rem", borderRadius: "16px", background: "rgba(15, 23, 42, 0.82)", border: "1px solid var(--border-color)", color: "white", outline: "none", lineHeight: 1.7 }}
            />
          </label>

          <div style={{ display: "grid", gap: "0.75rem", minWidth: "220px" }}>
            <label style={{ display: "grid", gap: "0.45rem" }}>
              <span style={{ fontSize: "0.84rem", color: "var(--text-muted)" }}>Top K (Vector only)</span>
              <input
                type="number"
                min={1}
                max={20}
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value || 8))}
                style={{ padding: "0.95rem 1rem", borderRadius: "12px", background: "rgba(15, 23, 42, 0.82)", border: "1px solid var(--border-color)", color: "white", outline: "none" }}
              />
            </label>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <button className="btn-primary" onClick={() => runSearch(query, "vector")} disabled={loading} style={{ justifyContent: "center", minHeight: "52px", padding: "0 0.5rem" }}>
                Vector Search
              </button>
              <button className="btn-secondary" onClick={() => runSearch(query, "graph")} disabled={loading} style={{ justifyContent: "center", minHeight: "52px", padding: "0 0.5rem" }}>
                Graph Search
              </button>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", marginTop: "1rem" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: "28px" }}>Try:</span>
          {EXAMPLE_QUERIES.map((example) => (
            <button
              key={example}
              onClick={() => {
                setQuery(example);
                runSearch(example, "vector");
              }}
              style={{
                padding: "0.45rem 0.8rem",
                borderRadius: "999px",
                background: "rgba(56, 189, 248, 0.08)",
                border: "1px solid rgba(56, 189, 248, 0.16)",
                color: "var(--accent)",
                fontSize: "0.84rem",
              }}
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="glass-panel" style={{ padding: "1rem 1.2rem", borderColor: "rgba(239,68,68,0.35)", background: "rgba(239,68,68,0.08)" }}>
          {error}
        </div>
      )}

      {loading && (
        <div className="glass-panel" style={{ padding: "1.5rem", color: "var(--text-muted)" }}>
          Querying the gateway vector endpoint and preparing ranked matches...
        </div>
      )}

      {result && !loading && (
        <div style={{ display: "grid", gap: "1.2rem" }}>
          <div className="glass-panel" style={{ padding: "1rem 1.2rem", display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.12em" }}>Search Metadata</div>
              <div style={{ marginTop: "0.35rem", fontWeight: 600 }}>{result.mode} search · {result.status}</div>
            </div>
            <div style={{ color: "var(--text-muted)" }}>
              {hits.length > 0 ? `${hits.length} documents returned` : "No documents returned yet"}
            </div>
          </div>

          <SearchResults hits={hits} />

          <div className="glass-panel" style={{ padding: "1rem 1.2rem", color: "var(--text-muted)", fontSize: "0.85rem" }}>
            Gateway session: {result.session_id || session?.username || "unknown"}
          </div>
        </div>
      )}
    </div>
  );
}
