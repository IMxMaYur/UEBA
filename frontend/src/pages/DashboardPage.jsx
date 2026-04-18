import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { Bar, Line, Doughnut } from 'react-chartjs-2'
import { Shield, AlertTriangle, Users, TrendingUp, ChevronRight, Cpu, Target, Activity } from 'lucide-react'
import api from '../api'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Tooltip, Legend, Filler)

const CHART_DEFAULTS = {
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 11 } } },
    y: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 11 } } },
  },
  responsive: true,
  maintainAspectRatio: false,
}

function StatCard({ icon: Icon, label, value, sub, color = '#3b82f6', pulse = false }) {
  return (
    <div className={`card ${pulse ? 'pulse-critical' : ''}`} style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
      <div style={{ padding: 10, borderRadius: 10, background: `${color}20`, flexShrink: 0 }}>
        <Icon size={20} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text-primary)' }}>{value}</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  )
}

function RiskBar({ score }) {
  const color = score >= 0.9 ? '#ef4444' : score >= 0.75 ? '#f59e0b' : score >= 0.65 ? '#3b82f6' : '#10b981'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="risk-bar" style={{ flex: 1 }}>
        <div className="risk-bar-fill" style={{ width: `${score * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color, minWidth: 36, textAlign: 'right' }}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  )
}

function getSeverityBadge(score) {
  if (score >= 0.90) return <span className="badge badge-critical">Critical</span>
  if (score >= 0.80) return <span className="badge badge-high">High</span>
  if (score >= 0.65) return <span className="badge badge-medium">Medium</span>
  return <span className="badge badge-low">Low</span>
}

export default function DashboardPage() {
  const [stats, setStats]       = useState(null)
  const [trends, setTrends]     = useState([])
  const [leaderboard, setLeaderboard] = useState([])
  const [alerts, setAlerts]     = useState([])
  const [metrics, setMetrics]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/stats/overview'),
      api.get('/stats/trends?days=30'),
      api.get('/stats/leaderboard?limit=10'),
      api.get('/alerts?status=OPEN&limit=5'),
      api.get('/stats/model-metrics'),
    ]).then(([s, t, lb, a, m]) => {
      setStats(s.data)
      setTrends(t.data)
      setLeaderboard(lb.data)
      setAlerts(a.data)
      setMetrics(m.data)
    }).catch(console.error).finally(() => setLoading(false))
  }, [])



  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--text-muted)' }}>
      <Activity size={24} style={{ marginRight: 10 }} />Loading threat intelligence...
    </div>
  )

  // Trend chart — last 30 days alert count
  const trendChartData = {
    labels: trends.map(t => t.date.slice(5)), // MM-DD
    datasets: [{
      label: 'Alerts',
      data: trends.map(t => t.alert_count),
      borderColor: '#ef4444',
      backgroundColor: 'rgba(239,68,68,0.12)',
      fill: true,
      tension: 0.4,
      pointRadius: 2,
    }],
  }

  // Alert type summary from open alerts
  const alertsByType = {}
  alerts.forEach(a => { alertsByType[a.alert_type] = (alertsByType[a.alert_type] || 0) + 1 })

  return (
    <div className="animate-in" style={{ maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <Shield size={20} color="#3b82f6" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Security Operations Center</h1>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>UEBA Insider Threat Detection Dashboard • CERT r4.2</p>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>
        <StatCard icon={Users}        label="Total Users Monitored" value={stats?.total_users ?? '—'}   color="#3b82f6" />
        <StatCard icon={AlertTriangle} label="High-Risk Users"       value={stats?.high_risk_users ?? '—'} color="#f59e0b" pulse={stats?.high_risk_users > 0} />
        <StatCard icon={Shield}       label="Open Alerts"           value={stats?.open_alerts ?? '—'}   color="#ef4444" />
        <StatCard icon={TrendingUp}   label="Avg Risk Score"        value={stats ? `${(stats.avg_risk_score * 100).toFixed(1)}%` : '—'} color="#8b5cf6" />
        <StatCard icon={Activity}     label="Alerts Today"          value={stats?.alerts_today ?? '—'}  color="#06b6d4" />
      </div>

      {/* Charts row — Trend + Alert type */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* 30-day alert trend line */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>ALERT TREND — LAST 30 DAYS</h3>
          <div style={{ height: 200 }}>
            <Line data={trendChartData} options={{
              ...CHART_DEFAULTS,
              plugins: { legend: { display: false } },
              scales: {
                ...CHART_DEFAULTS.scales,
                y: { ...CHART_DEFAULTS.scales.y, beginAtZero: true, ticks: { ...CHART_DEFAULTS.scales.y.ticks, stepSize: 1 } },
              },
            }} />
          </div>
        </div>

        {/* Alert types doughnut */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>OPEN ALERT TYPES</h3>
          <div style={{ height: 200 }}>
            {Object.keys(alertsByType).length > 0 ? (
              <Doughnut
                data={{
                  labels: Object.keys(alertsByType).map(k => k.replace(/_/g, ' ')),
                  datasets: [{ data: Object.values(alertsByType), backgroundColor: ['#ef4444','#f59e0b','#3b82f6','#8b5cf6','#10b981'], borderWidth: 0, hoverOffset: 6 }],
                }}
                options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10 } } } } }}
              />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>No open alerts</div>
            )}
          </div>
        </div>
      </div>

      {/* Department Risk Distribution + Model Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Department risk distribution */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-secondary)' }}>DEPARTMENT RISK DISTRIBUTION</h3>
          {leaderboard.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>Run the pipeline to load data.</div>
          ) : (() => {
            // Aggregate avg risk by department
            const deptMap = {}
            leaderboard.forEach(u => {
              const d = u.department || 'Unknown'
              if (!deptMap[d]) deptMap[d] = { total: 0, count: 0 }
              deptMap[d].total += u.risk_score
              deptMap[d].count++
            })
            const depts = Object.entries(deptMap)
              .map(([d, v]) => ({ dept: d, avg: v.total / v.count }))
              .sort((a, b) => b.avg - a.avg)
            return (
              <div style={{ height: 200 }}>
                <Bar
                  data={{
                    labels: depts.map(d => d.dept),
                    datasets: [{
                      data: depts.map(d => +(d.avg * 100).toFixed(1)),
                      backgroundColor: depts.map(d =>
                        d.avg >= 0.9 ? '#ef4444' : d.avg >= 0.75 ? '#f59e0b' : d.avg >= 0.65 ? '#3b82f6' : '#10b981'
                      ),
                      borderRadius: 6,
                    }],
                  }}
                  options={{
                    ...CHART_DEFAULTS,
                    indexAxis: 'y',
                    plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` Avg Risk: ${ctx.raw}%` } } },
                    scales: {
                      x: { ...CHART_DEFAULTS.scales.x, max: 100, ticks: { ...CHART_DEFAULTS.scales.x.ticks, callback: v => v + '%' } },
                      y: { ...CHART_DEFAULTS.scales.y },
                    },
                  }}
                />
              </div>
            )
          })()}
        </div>

        {/* Model metrics card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Cpu size={16} color="#8b5cf6" />
            <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>ML MODEL PERFORMANCE</h3>
          </div>
          {metrics && metrics.roc_auc > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {[
                { label: 'ROC-AUC',   value: metrics.roc_auc,           color: '#10b981' },
                { label: 'Precision', value: metrics.precision,          color: '#3b82f6' },
                { label: 'Recall',    value: metrics.recall,             color: '#f59e0b' },
                { label: 'F1-Score',  value: metrics.f1_score,           color: '#8b5cf6' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ padding: '10px 14px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color }}>{(value * 100).toFixed(1)}%</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              <Target size={32} style={{ opacity: 0.3, display: 'block', margin: '0 auto 8px' }} />
              Run the ML pipeline to load model metrics.<br />
              <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>python run_pipeline.py</span>
            </div>
          )}
          {metrics?.last_trained && (
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
              Last trained: {new Date(metrics.last_trained).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {/* Recent Alerts — its own row */}
      <div style={{ marginBottom: 24 }}>
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>RECENT OPEN ALERTS</h3>
            <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => navigate('/alerts')}>View all</button>
          </div>
          <div style={{ padding: '8px 0' }}>
            {alerts.length === 0 && (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32, fontSize: 13 }}>No open alerts</div>
            )}
            {alerts.map(alert => (
              <div key={alert.id}
                onClick={() => navigate('/alerts')}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer', padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: alert.severity === 'CRITICAL' ? '#ef4444' : alert.severity === 'HIGH' ? '#f59e0b' : '#3b82f6', flexShrink: 0, marginTop: 4 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{alert.alert_type.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{alert.user_id}</span> · {alert.date}
                  </div>
                </div>
                <span className={`badge badge-${alert.severity.toLowerCase()}`}>{alert.severity}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Risk Leaderboard */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>RISK LEADERBOARD — TOP USERS</h3>
          <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => navigate('/users')}>View all users</button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Department</th>
              <th>Risk Score</th>
              <th>Severity</th>
              <th>Open Alerts</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No users loaded. Run the pipeline first.</td></tr>
            )}
            {leaderboard.map(user => (
              <tr key={user.user_id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/users/${user.user_id}`)}>
                <td>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 600 }}>{user.user_id}</div>
                  {user.name && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{user.name}</div>}
                </td>
                <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{user.department || '—'}</td>
                <td style={{ minWidth: 140 }}><RiskBar score={user.risk_score} /></td>
                <td>{getSeverityBadge(user.risk_score)}</td>
                <td>
                  {user.open_alerts > 0
                    ? <span style={{ fontSize: 12, fontWeight: 700, color: '#ef4444' }}>{user.open_alerts} open</span>
                    : <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>—</span>
                  }
                </td>
                <td><ChevronRight size={14} color="var(--text-muted)" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  )
}
