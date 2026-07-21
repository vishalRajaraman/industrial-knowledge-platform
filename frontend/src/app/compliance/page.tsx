"use client";
import { useState } from 'react';

interface ComplianceGap {
  clause: string;
  requirement: string;
  severity: 'High' | 'Medium' | 'Low';
  current_state: string;
  recommendation: string;
}

interface ComplianceResult {
  framework: string;
  overall_coverage: number;
  summary: string;
  docs_checked: number;
  gaps: ComplianceGap[];
}

export default function ComplianceAuditor() {
  const [framework, setFramework] = useState('OISD_154');
  const [scope, setScope] = useState('All Plant');
  const [isAuditing, setIsAuditing] = useState(false);
  const [results, setResults] = useState<ComplianceResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runAudit = async () => {
    setIsAuditing(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const queryStr = `Check compliance gaps for framework ${framework} targeting ${scope}`;
      
      const res = await fetch(`${apiUrl}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryStr, user_role: 'auditor', regulation: framework })
      });
      
      if (!res.ok) throw new Error('API Error');
      const data = await res.json();

      // Compliance agent returns structured data in metadata.results (gap_res object)
      // or a breakdown in the metadata directly
      const meta = data.metadata || {};
      const resultsData = meta.results || meta || {};
      const gapCount = meta.gap_count ?? (resultsData.gaps?.length ?? 0);
      const rawCoverage = resultsData.overall_coverage ?? (gapCount === 0 ? 1.0 : Math.max(0, 1 - gapCount * 0.1));
      // Normalize coverage: backend may return 0.85 or 85
      const coverage = rawCoverage > 1 ? rawCoverage / 100 : rawCoverage;

      setResults({
        framework: framework,
        overall_coverage: coverage,
        summary: resultsData.summary || data.answer || "Compliance analysis complete.",
        docs_checked: resultsData.docs_checked ?? (data.sources?.length ?? 0),
        gaps: resultsData.gaps || [],
      });
    } catch (err) {
      console.error(err);
      setError("Failed to run audit. Ensure the InduStreakAI Orchestrator is running.");
      setResults(null);
    }
    setIsAuditing(false);
  };

  return (
    <div className="animate-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Quality & <span className="text-accent">Compliance</span> Auditor</h1>
          <p style={{ color: 'var(--text-muted)' }}>Auto-generate compliance evidence packages and detect gaps.</p>
        </div>
      </div>

      <div className="glass-card" style={{ padding: '2rem', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>Initiate Auto-Audit</h2>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>Regulatory Framework</label>
            <select 
              value={framework}
              onChange={(e) => setFramework(e.target.value)}
              style={{ width: '100%', padding: '0.875rem', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', color: 'white', outline: 'none' }}
            >
              <option value="OISD_154">OISD 154 — Safety Management System</option>
              <option value="OISD_STD_144">OISD STD 144 — Fire Prevention & Protection</option>
              <option value="Factory_Act_1948">Factory Act 1948</option>
              <option value="ISO_55001">ISO 55001 — Asset Management</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>Scope (Equipment/Area)</label>
            <input 
              type="text" 
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder="e.g., CDU-1, Fire Water Pumps, or All Plant" 
              style={{ width: '100%', padding: '0.875rem', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', color: 'white', outline: 'none' }}
            />
          </div>
          <button 
            onClick={runAudit}
            disabled={isAuditing}
            className="btn-primary" 
            style={{ height: '46px', minWidth: '160px' }}
          >
            {isAuditing ? (
              <><span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>↻</span> Auditing...</>
            ) : (
              <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg> Run Audit</>
            )}
          </button>
        </div>
      </div>
      
      {error && (
        <div className="glass-panel" style={{ padding: '1rem', borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.1)', marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      {results && (
        <div className="animate-in stagger-1">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
            <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}>
              <div style={{ fontSize: '3rem', fontWeight: 700, color: results.overall_coverage > 0.8 ? 'var(--success)' : 'var(--warning)', marginBottom: '0.5rem' }}>
                {results.overall_coverage * 100}%
              </div>
              <div style={{ color: 'var(--text-muted)' }}>Compliance Score</div>
              <div style={{ fontSize: '0.75rem', marginTop: '1rem', color: 'var(--text-muted)' }}>
                Based on {results.docs_checked} documents analyzed against {results.framework}.
              </div>
            </div>
            
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <h3 style={{ marginBottom: '0.5rem', color: 'var(--accent)' }}>Executive Summary</h3>
              <p style={{ lineHeight: 1.6 }}>{results.summary}</p>
              
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                <button className="btn-secondary" style={{ fontSize: '0.875rem' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '6px' }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                  Export Evidence Package (PDF)
                </button>
              </div>
            </div>
          </div>

          <h3 style={{ fontSize: '1.25rem', marginBottom: '1rem', marginTop: '2rem' }}>Identified Compliance Gaps</h3>
          {results.gaps.length === 0 ? (
            <div className="glass-panel" style={{ padding: '1.5rem', borderColor: 'rgba(16,185,129,0.3)', background: 'rgba(16,185,129,0.05)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--success)' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                <div>
                  <div style={{ fontWeight: 600 }}>No Structured Gaps Detected</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '4px' }}>The compliance agent found no specific gap records for {results.framework}. Review the executive summary above for a full analysis.</div>
                </div>
              </div>
            </div>
          ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {results.gaps.map((gap: ComplianceGap, idx: number) => (
              <div key={idx} className="glass-card" style={{ padding: '1.5rem', borderLeft: `4px solid ${gap.severity === 'High' ? 'var(--danger)' : gap.severity === 'Low' ? 'var(--success)' : 'var(--warning)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                  <div>
                    <span style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', marginRight: '8px' }}>Clause {gap.clause}</span>
                    <span style={{ fontWeight: 600, fontSize: '1.125rem' }}>{gap.requirement}</span>
                  </div>
                  <span style={{ 
                    background: gap.severity === 'High' ? 'rgba(239, 68, 68, 0.2)' : gap.severity === 'Low' ? 'rgba(16,185,129,0.2)' : 'rgba(245, 158, 11, 0.2)', 
                    color: gap.severity === 'High' ? 'var(--danger)' : gap.severity === 'Low' ? 'var(--success)' : 'var(--warning)', 
                    padding: '4px 12px', borderRadius: '20px', fontSize: '0.75rem', fontWeight: 600 
                  }}>
                    {gap.severity} Risk
                  </span>
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.875rem' }}>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px' }}>
                    <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Current State (Evidence)</div>
                    <div style={{ color: 'white' }}>{gap.current_state}</div>
                  </div>
                  <div style={{ background: 'rgba(56, 189, 248, 0.1)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
                    <div style={{ color: 'var(--accent)', marginBottom: '0.25rem' }}>Recommendation</div>
                    <div style={{ color: 'white' }}>{gap.recommendation}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          )}
        </div>
      )}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}} />
    </div>
  );
}
