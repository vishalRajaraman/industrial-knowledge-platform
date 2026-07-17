"use client";

import type { SearchHit } from "@/lib/gateway";

type SearchResultsProps = {
  hits: SearchHit[];
};

function getDisplayText(hit: SearchHit): string {
  return hit.snippet || hit.text || "No snippet returned for this document yet.";
}

function getConfidence(hit: SearchHit): number | null {
  if (typeof hit.confidence === "number") return hit.confidence;
  if (typeof hit.score === "number") return hit.score;
  return null;
}

export function SearchResults({ hits }: SearchResultsProps) {
  if (hits.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
        No documents yet. Run a search to see vector matches here.
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {hits.map((hit, index) => {
        const confidence = getConfidence(hit);
        const title = hit.title || hit.doc_id || `Document ${index + 1}`;

        return (
          <article key={`${title}-${index}`} className="glass-card" style={{ padding: "1.25rem 1.35rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", marginBottom: "0.75rem" }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: "1rem" }}>{title}</div>
                {hit.section_title && <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.2rem" }}>{hit.section_title}</div>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
                {confidence !== null && (
                  <span style={{ background: "rgba(16, 185, 129, 0.12)", color: "var(--success)", padding: "0.35rem 0.65rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: 600 }}>
                    {Math.round(confidence * 100)}% confidence
                  </span>
                )}
                {hit.doc_type && (
                  <span style={{ background: "rgba(56, 189, 248, 0.12)", color: "var(--accent)", padding: "0.35rem 0.65rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: 600 }}>
                    {hit.doc_type}
                  </span>
                )}
              </div>
            </div>

            <p style={{ color: "var(--text-main)", lineHeight: 1.75, marginBottom: "0.85rem" }}>{getDisplayText(hit)}</p>

            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", color: "var(--text-muted)", fontSize: "0.82rem", flexWrap: "wrap" }}>
              <span>Document ID: {hit.doc_id || "N/A"}</span>
              {hit.metadata && Object.keys(hit.metadata).length > 0 && <span>{Object.keys(hit.metadata).length} metadata fields</span>}
            </div>
          </article>
        );
      })}
    </div>
  );
}
