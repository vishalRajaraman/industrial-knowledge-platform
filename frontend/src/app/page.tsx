"use client";
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const GATEWAY_API_BASE = process.env.NEXT_PUBLIC_GATEWAY_URL || 'http://localhost:8100/api/v1';

interface DashboardStats {
  totalDocuments: number | null;
  graphNodes: number | null;
  graphEdges: number | null;
  complianceGaps: number | null;
  predictiveAlerts: number | null;
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
    predictiveAlerts: null,
    mcpStatus: 'loading',
    orchestratorStatus: 'loading',
  });
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
        const nodes = graphData?.nodes?.result || graphData?.nodes || [];
        if (Array.isArray(nodes)) {
          nodeCount = nodes.reduce((sum: number, row: { cnt?: number }) => sum + (Number(row.cnt) || 0), 0);
        }
        const edges = graphData?.edges?.result || graphData?.edges;
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

    // 2. Fetch compliance gap count via query
    try {
      const compRes = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'How many compliance gaps are currently detected?', user_role: 'auditor' }),
        signal: AbortSignal.timeout(10000),
      });
      if (compRes.ok) {
        const compData = await compRes.json();
        const gapCount = compData?.metadata?.gap_count ?? null;
        setStats(prev => ({ ...prev, complianceGaps: gapCount !== null ? Number(gapCount) : 0 }));
      }
    } catch {
      setStats(prev => ({ ...prev, complianceGaps: 0 }));
    }

    // 3. Fetch predictive alerts count
    try {
      const alertRes = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'How many equipment are currently in alert or critical state?', user_role: 'operator' }),
        signal: AbortSignal.timeout(10000),
      });
      if (alertRes.ok) {
        const alertData = await alertRes.json();
        const alertCount = alertData?.metadata?.alert_count ?? null;
        setStats(prev => ({ ...prev, predictiveAlerts: alertCount !== null ? Number(alertCount) : 0 }));
      }
    } catch {
      setStats(prev => ({ ...prev, predictiveAlerts: 0 }));
    }
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
            sub="OISD-144 & ISO-55001"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>}
          />
        </div>
        <div className="stagger-3">
          <StatCard
            label="Predictive Alerts"
            value={stats.predictiveAlerts}
            color={stats.predictiveAlerts !== null && stats.predictiveAlerts > 0 ? 'var(--danger)' : 'var(--success)'}
            sub={stats.predictiveAlerts !== null && stats.predictiveAlerts > 0 ? 'Equipment requires attention' : 'All equipment nominal'}
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
        {/* Ask Copilot Section */}
        <div className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            </div>
            Ask IKP Copilot
          </h2>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '1.5rem', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>Suggested Queries:</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                {[
                  'Why is Pump P-101 vibrating?',
                  "Generate RCA for yesterday's shutdown",
                  'Show compliance gaps for Fire Systems',
                ].map(q => (
                  <span
                    key={q}
                    onClick={() => setQuery(q)}
                    style={{ background: 'rgba(56, 189, 248, 0.1)', color: 'var(--accent)', padding: '0.5rem 1rem', borderRadius: '20px', fontSize: '0.875rem', cursor: 'pointer', border: '1px solid rgba(56, 189, 248, 0.2)' }}
                  >
                    {q}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div style={{ position: 'relative' }}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Ask anything about assets, procedures, or compliance..."
              style={{ width: '100%', padding: '1.25rem', paddingRight: '4rem', borderRadius: '12px', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--border-color)', color: 'white', fontSize: '1rem', outline: 'none' }}
            />
            <button
              onClick={handleSearch}
              style={{ position: 'absolute', right: '12px', top: '12px', background: 'var(--primary)', color: 'white', width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
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
    </div>
  );
}
