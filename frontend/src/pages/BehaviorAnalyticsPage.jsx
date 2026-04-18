import { useState, useEffect } from 'react'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Tooltip, Legend, Filler
} from 'chart.js'
import { Scatter, Bar, Doughnut } from 'react-chartjs-2'
import { Activity, TrendingUp, Target, RefreshCw } from 'lucide-react'
import api from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Tooltip, Legend, Filler)

const CHART_DEFAULTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 11 } } },
    y: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 11 } } },
  },
}

function RiskBucket(users) {
  const buckets = [
    { label: 'Normal (0-30)',   count: 0, color: '#10b981' },
    { label: 'Low (30-60)',     count: 0, color: '#3b82f6' },
    { label: 'Medium (60-75)', count: 0, color: '#f59e0b' },
    { label: 'High (75-90)',   count: 0, color: '#f97316' },
    { label: 'Critical (90+)', count: 0, color: '#ef4444' },
  ]
  users.forEach(u => {
    const s = u.risk_score ?? 0
    if (s < 0.30) buckets[0].count++
    else if (s < 0.60) buckets[1].count++
    else if (s < 0.75) buckets[2].count++
    else if (s < 0.90) buckets[3].count++
    else buckets[4].count++
  })
  return buckets
}

export default function BehaviorAnalyticsPage() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchData = (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    api.get('/stats/leaderboard?limit=200')
      .then(r => setUsers(r.data || []))
      .catch(console.error)
      .finally(() => { setLoading(false); setRefreshing(false) })
  }

  useEffect(() => {
    fetchData()
    // Auto-poll every 30s so data updates after simulation
    const interval = setInterval(() => fetchData(true), 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--text-muted)' }}>
      <Activity size={24} style={{ marginRight: 10 }} /> Loading analytics...
    </div>
  )

  if (users.length === 0) return (
    <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>
      <Target size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>No behavioral data available</div>
      <div style={{ fontSize: 13 }}>Run the ML pipeline first to generate user risk scores.</div>
    </div>
  )

  const buckets = RiskBucket(users)

  // Scatter: IF score vs AE score as proxy for behavior clusters
  const scatterData = {
    datasets: [{
      label: 'Users',
      data: users.map((u, i) => ({
        x: +(u.risk_score * 100).toFixed(1),
        y: +((u.open_alerts || 0) + (u.risk_score * 10)).toFixed(1),
        user_id: u.user_id,
      })),
      backgroundColor: users.map(u => {
        const s = u.risk_score
        if (s >= 0.9) return 'rgba(239,68,68,0.8)'
        if (s >= 0.75) return 'rgba(249,115,22,0.8)'
        if (s >= 0.6) return 'rgba(245,158,11,0.8)'
        if (s >= 0.3) return 'rgba(59,130,246,0.8)'
        return 'rgba(16,185,129,0.7)'
      }),
      pointRadius: 6, pointHoverRadius: 9,
    }],
  }

  // Bar: anomaly score distribution
  const barData = {
    labels: buckets.map(b => b.label),
    datasets: [{
      data: buckets.map(b => b.count),
      backgroundColor: buckets.map(b => b.color),
      borderRadius: 8,
    }],
  }

  // Doughnut: severity breakdown
  const riskDoughnut = {
    labels: buckets.map(b => b.label),
    datasets: [{
      data: buckets.map(b => b.count),
      backgroundColor: buckets.map(b => b.color.replace(')', ', 0.8)').replace('rgb', 'rgba')),
      borderWidth: 0,
      hoverOffset: 8,
    }],
  }

  const topAnomalous = [...users].sort((a, b) => b.risk_score - a.risk_score).slice(0, 10)

  return (
    <div className="animate-in" style={{ maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <TrendingUp size={20} color="#8b5cf6" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Behavioral Anomaly Analytics</h1>
          <button
            onClick={() => fetchData(true)}
            disabled={refreshing}
            style={{ marginLeft: 8, background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.3)', borderRadius: 8, padding: '4px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, color: '#8b5cf6', fontSize: 11, fontWeight: 600 }}
          >
            <RefreshCw size={11} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>ML-powered outlier detection visualization • {users.length} users analyzed</p>
      </div>

      {/* Summary stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 28 }}>
        {buckets.map(b => (
          <div key={b.label} className="card" style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: b.color }}>{b.count}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{b.label}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Scatter: behavior clusters */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>BEHAVIOR CLUSTER SCATTER</h3>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>Risk Score vs Alert Activity — outliers indicate suspicious behavior</p>
          <div style={{ height: 280 }}>
            <Scatter data={scatterData} options={{
              ...CHART_DEFAULTS,
              plugins: {
                legend: { display: false },
                tooltip: {
                  callbacks: {
                    label: ctx => `User: ${ctx.raw.user_id}  |  Risk: ${ctx.raw.x}%  |  Activity: ${ctx.raw.y.toFixed(1)}`
                  }
                }
              },
              scales: {
                ...CHART_DEFAULTS.scales,
                x: { ...CHART_DEFAULTS.scales.x, title: { display: true, text: 'Risk Score (%)', color: '#475569', font: { size: 11 } } },
                y: { ...CHART_DEFAULTS.scales.y, title: { display: true, text: 'Alert Activity Index', color: '#475569', font: { size: 11 } } },
              }
            }} />
          </div>
        </div>

        {/* Doughnut: severity breakdown */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>RISK SEVERITY BREAKDOWN</h3>
          <div style={{ height: 280 }}>
            <Doughnut data={riskDoughnut} options={{
              responsive: true, maintainAspectRatio: false,
              plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 }, padding: 12 } }
              },
              cutout: '60%',
            }} />
          </div>
        </div>
      </div>

      {/* Bar: distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>ANOMALY SCORE DISTRIBUTION</h3>
          <div style={{ height: 200 }}>
            <Bar data={barData} options={{
              ...CHART_DEFAULTS,
              scales: {
                ...CHART_DEFAULTS.scales,
                y: { ...CHART_DEFAULTS.scales.y, beginAtZero: true, ticks: { ...CHART_DEFAULTS.scales.y.ticks, stepSize: 1 } }
              },
              plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${ctx.raw} users` } } }
            }} />
          </div>
        </div>

        {/* Outlier list */}
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>TOP OUTLIERS DETECTED</h3>
          </div>
          <div style={{ padding: '8px 0', maxHeight: 248, overflowY: 'auto' }}>
            {topAnomalous.map((u, i) => {
              const color = u.risk_score >= 0.9 ? '#ef4444' : u.risk_score >= 0.75 ? '#f97316' : u.risk_score >= 0.6 ? '#f59e0b' : '#3b82f6'
              return (
                <div key={u.user_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px', borderBottom: '1px solid rgba(30,45,69,0.5)' }}>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 18, fontFamily: 'JetBrains Mono, monospace' }}>#{i + 1}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, fontFamily: 'JetBrains Mono, monospace' }}>{u.user_id}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{u.department || '—'}</div>
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 800, color }}>{(u.risk_score * 100).toFixed(0)}%</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
