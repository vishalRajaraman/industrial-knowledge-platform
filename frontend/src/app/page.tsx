"use client";
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const GATEWAY_API_BASE = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://localhost:8100/api/v1';

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
  sources: { id?: string; title?: string; doc_type?: string }[];
}

interface DashboardStats {
  totalDocuments: number | null;
  graphNodes: number | null;
  graphEdges: number | null;
  complianceGaps: number | null;
  mcpStatus: 'online' | 'offline' | 'loading';
  orchestratorStatus: 'online' | 'offline' | 'loading';
}

interface ActivityItem {
  title: string;
  description: string;
  time: string;
  status: 'success' | 'warning' | 'error';
}

function StatCard({
  label, value, icon, color, sub,
}: {
  label: string;
  value: number | null;
  icon: React.ReactNode;
  color?: string;
  sub?: string;
}) {
  return (
    <div className="glass-card" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', color: 'var(--text-muted)' }}>
        <span style={{ fontWeight: 500 }}>{label}</span>
        {icon}
      </div>
      {value === null ? (
        <div style={{ height: '2.5rem', width: '8rem', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', animation: 'shimmer 1.5s infinite' }} />
      ) : (
        <div style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '0.5rem', color: color || 'var(--text-main)' }}>
          {value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value}
        </div>
      )}
      {sub && <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [stats, setStats] = useState<DashboardStats>({
    totalDocuments: null,
    graphNodes: null,
    graphEdges: null,
    complianceGaps: null,
    mcpStatus: 'loading',
    orchestratorStatus: 'loading',
  });
  
  // Compliance Auditor State
  const [framework, setFramework] = useState('OISD_154');
  const [isAuditing, setIsAuditing] = useState(false);
  const [results, setResults] = useState<ComplianceResult | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  const runAudit = async () => {
    setIsAuditing(true);
    setAuditError(null);
    try {
      const queryStr = `Check compliance gaps for framework ${framework} targeting All Plant`;
      const res = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryStr, user_role: 'auditor', regulation: framework })
      });
      if (!res.ok) throw new Error('API Error');
      const data = await res.json();
      const meta = data.metadata || {};
      const resultsData = meta.results || meta || {};
      const gapCount = meta.gap_count ?? (resultsData.gaps?.length ?? 0);
      const rawCoverage = resultsData.overall_coverage ?? (gapCount === 0 ? 1.0 : Math.max(0, 1 - gapCount * 0.1));
      const coverage = rawCoverage > 1 ? rawCoverage / 100 : rawCoverage;
      setResults({
        framework: framework,
        overall_coverage: coverage,
        summary: resultsData.summary || data.answer || "Compliance analysis complete.",
        docs_checked: resultsData.docs_checked ?? (data.sources?.length ?? 0),
        gaps: resultsData.gaps || [],
        sources: data.sources || [],
      });
      setStats(prev => ({ ...prev, complianceGaps: gapCount }));
    } catch (err) {
      console.error(err);
      setAuditError("Failed to run audit. Ensure the InduStreakAI Orchestrator is running.");
      setResults(null);
    }
    setIsAuditing(false);
  };
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);

  const handleSearch = () => {
    if (query.trim()) {
      sessionStorage.setItem('initialQuery', query);
      router.push('/chat');
    }
  };

  const fetchStats = useCallback(async () => {
    // 1. Fetch orchestrator health + graph stats in parallel
    try {
      const [healthRes, graphRes] = await Promise.allSettled([
        fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(6000) }),
        fetch(`${API_URL}/graph/stats`, { signal: AbortSignal.timeout(8000) }),
      ]);

      let mcpOnline = false;
      let nodeCount: number | null = null;
      let edgeCount: number | null = null;
      let docCount: number | null = null;

      if (healthRes.status === 'fulfilled' && healthRes.value.ok) {
        const healthData = await healthRes.value.json();
        mcpOnline = healthData.status === 'ok';
        setStats(prev => ({ ...prev, orchestratorStatus: 'online', mcpStatus: mcpOnline ? 'online' : 'offline' }));
      } else {
        setStats(prev => ({ ...prev, orchestratorStatus: 'offline', mcpStatus: 'offline' }));
      }

      if (graphRes.status === 'fulfilled' && graphRes.value.ok) {
        const graphData = await graphRes.value.json();
        // Parse node counts from Cypher result
        const nodes = graphData?.nodes?.results || graphData?.nodes || [];
        if (Array.isArray(nodes)) {
          nodeCount = nodes.reduce((sum: number, row: { cnt?: number }) => sum + (Number(row.cnt) || 0), 0);
        }
        const edges = graphData?.edges?.results || graphData?.edges;
        if (edges && typeof edges === 'object') {
          edgeCount = Number(edges.total_edges ?? edges[0]?.total_edges ?? 0) || null;
        }
        // Doc count = Document nodes
        if (Array.isArray(nodes)) {
          const docRow = nodes.find((r: { lbls?: string[] }) => r.lbls?.includes('Document') || r.lbls?.includes('Chunk'));
          docCount = docRow ? Number(docRow.cnt) : null;
        }
      }

      setStats(prev => ({
        ...prev,
        graphNodes: nodeCount,
        graphEdges: edgeCount,
        totalDocuments: docCount,
      }));
    } catch {
      setStats(prev => ({ ...prev, orchestratorStatus: 'offline', mcpStatus: 'offline' }));
    }
    
    // 2. Prevent server blocking on mount by removing concurrent heavy LLM audits.
    // Compliance gaps will now be updated when the user manually runs the audit.
    setStats(prev => ({ ...prev, complianceGaps: 0 }));
  }, []);

  const fetchActivity = useCallback(async () => {
    setActivityLoading(true);
    try {
      // Query the MCP server knowledge list for recent documents
      const res = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'List the 3 most recently ingested documents with their processing status', user_role: 'operator' }),
        signal: AbortSignal.timeout(10000),
      });
      if (res.ok) {
        const data = await res.json();
        const sources = data?.sources || [];
        if (sources.length > 0) {
          const mapped: ActivityItem[] = sources.slice(0, 3).map((src: { title?: string; doc_id?: string; snippet?: string; metadata?: { ingested_at?: string } }) => ({
            title: src.title || src.doc_id || 'Document processed',
            description: src.snippet ? src.snippet.slice(0, 80) + '…' : 'Indexed into knowledge base.',
            time: src.metadata?.ingested_at ? new Date(src.metadata.ingested_at).toLocaleString() : 'Recently',
            status: 'success' as const,
          }));
          setActivity(mapped);
        } else {
          setActivity([]);
        }
      }
    } catch {
      setActivity([]);
    }
    setActivityLoading(false);
  }, []);

  useEffect(() => {
    void fetchStats();
    void fetchActivity();
  }, [fetchStats, fetchActivity]);

  const statusDot = (s: 'online' | 'offline' | 'loading') =>
    s === 'online' ? '#10b981' : s === 'offline' ? '#ef4444' : '#f59e0b';

  return (
    <div className="animate-in">
      <style>{`
        @keyframes shimmer {
          0% { opacity: 0.4; }
          50% { opacity: 0.8; }
          100% { opacity: 0.4; }
        }
      `}</style>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Platform <span className="text-accent">Intelligence</span></h1>
          <p style={{ color: 'var(--text-muted)' }}>Real-time overview of knowledge assets and equipment health.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {/* Backend Status Indicators */}
          <div className="glass-card" style={{ padding: '0.5rem 1rem', display: 'flex', gap: '1rem', fontSize: '0.8rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-muted)' }}>
              <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: statusDot(stats.orchestratorStatus) }} />
              Orchestrator
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-muted)' }}>
              <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: statusDot(stats.mcpStatus) }} />
              MCP Server
            </span>
          </div>
          <button className="btn-primary" onClick={() => router.push('/upload')}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            Ingest New Manual
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem', marginBottom: '2.5rem' }}>
        <div className="stagger-1">
          <StatCard
            label="Total Documents"
            value={stats.totalDocuments}
            color="var(--text-main)"
            sub={stats.totalDocuments !== null ? '📄 Indexed in knowledge base' : undefined}
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>}
          />
        </div>
        <div className="stagger-2">
          <StatCard
            label="Knowledge Graph Nodes"
            value={stats.graphNodes}
            color="var(--text-main)"
            sub={stats.graphEdges !== null ? `+${stats.graphEdges} relationships` : undefined}
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>}
          />
        </div>
        <div className="stagger-3">
          <StatCard
            label="Compliance Gaps"
            value={stats.complianceGaps}
            color={stats.complianceGaps !== null && stats.complianceGaps > 0 ? 'var(--warning)' : 'var(--success)'}
            sub="All Regulatory Frameworks"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
        {/* Quality & Compliance Auditor */}
        <div className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1.5rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Quality & Compliance Auditor
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
            <div>
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
            <button 
              onClick={runAudit}
              disabled={isAuditing}
              className="btn-primary" 
              style={{ height: '46px', marginTop: '0.5rem' }}
            >
              {isAuditing ? (
                <><span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>↻</span> Auditing...</>
              ) : (
                <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg> Run Auto-Audit</>
              )}
            </button>
            {auditError && <div style={{ marginTop: '0.5rem', padding: '0.75rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', fontSize: '0.875rem' }}>{auditError}</div>}
            
            {results && (
              <div className="animate-in" style={{ marginTop: '1rem', padding: '1.25rem', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <div style={{ fontWeight: 600 }}>Compliance Score</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 700, color: results.overall_coverage > 0.8 ? 'var(--success)' : 'var(--warning)' }}>
                    {Math.round(results.overall_coverage * 100)}%
                  </div>
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                  Analyzed {results.docs_checked} documents. Found {results.gaps.length} gaps.
                </div>
                <button 
                  className="btn-secondary" 
                  style={{ width: '100%', fontSize: '0.875rem' }} 
                  onClick={() => {
                    const el = document.getElementById('audit-summary-details');
                    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
                  }}
                >
                  Toggle Executive Summary
                </button>
                <div id="audit-summary-details" className="animate-in" style={{ display: 'none', marginTop: '1rem' }}>
                  <div style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', borderLeft: '3px solid var(--accent)', fontSize: '0.875rem', lineHeight: '1.6', color: 'var(--text-main)', whiteSpace: 'pre-wrap', marginBottom: '1rem' }}>
                    <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-muted)' }}>Audit Summary</div>
                    {results.summary.replace(/\*\*/g, '').replace(/### /g, '').replace(/#/g, '')}
                  </div>
                  
                  {results.gaps && results.gaps.length > 0 && (
                    <div style={{ marginBottom: '1rem' }}>
                      <div style={{ fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Detected Gaps</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {results.gaps.map((gap, i) => (
                          <div key={i} style={{ padding: '1rem', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '8px', border: '1px solid var(--border-color)', borderLeft: `3px solid ${gap.severity === 'High' ? 'var(--danger)' : gap.severity === 'Medium' ? 'var(--warning)' : 'var(--success)'}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                              <strong style={{ fontSize: '0.9rem' }}>Clause {gap.clause}</strong>
                              <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '12px', background: 'rgba(255,255,255,0.1)' }}>{gap.severity} Priority</span>
                            </div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--text-main)', marginBottom: '0.5rem' }}><strong>Requirement:</strong> {gap.requirement}</div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}><strong>Current State:</strong> {gap.current_state}</div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--accent)' }}><strong>Recommendation:</strong> {gap.recommendation}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {results.sources && results.sources.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: '0.75rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Knowledge Graph Sources</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {results.sources.map((src, i) => (
                          <div key={i} style={{ fontSize: '0.75rem', padding: '0.5rem 0.75rem', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                            {src.id || src.title}
                            {src.doc_type && <span style={{ opacity: 0.5 }}>({src.doc_type})</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
        {/* Recent Activity */}
        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1.5rem', paddingBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Recent Processing
            <button
              onClick={() => fetchActivity()}
              style={{ fontSize: '0.75rem', color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
              Refresh
            </button>
          </h2>

          {activityLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {[1, 2, 3].map(i => (
                <div key={i} style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', marginTop: '8px', flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ height: '14px', width: '70%', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '6px', animation: 'shimmer 1.5s infinite' }} />
                    <div style={{ height: '12px', width: '90%', background: 'rgba(255,255,255,0.03)', borderRadius: '4px', animation: 'shimmer 1.5s infinite' }} />
                  </div>
                </div>
              ))}
            </div>
          ) : activity.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {activity.map((item, i) => (
                <div key={i} style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: item.status === 'success' ? 'var(--success)' : item.status === 'warning' ? 'var(--warning)' : 'var(--danger)', marginTop: '8px', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontWeight: 500 }}>{item.title}</div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '2px' }}>{item.description}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>{item.time}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                {stats.orchestratorStatus === 'offline'
                  ? '⚠️ Orchestrator is offline. Start the backend to see live activity.'
                  : 'No recent documents found. Upload a document to get started.'}
              </p>
              <button className="btn-secondary" onClick={() => router.push('/upload')} style={{ fontSize: '0.875rem', width: 'fit-content' }}>
                + Ingest first document
              </button>
            </div>
          )}
        </div>
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}} />
    </div>
  );
}
