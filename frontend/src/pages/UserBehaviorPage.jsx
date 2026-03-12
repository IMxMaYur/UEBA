import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Chart as ChartJS, CategoryScale, LinearScale, LineElement, PointElement, BarElement, Tooltip, Filler, Legend } from 'chart.js'
import { Line, Bar } from 'react-chartjs-2'
import { ArrowLeft, User, AlertTriangle, TrendingUp, Activity } from 'lucide-react'
import api from '../api'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, BarElement, Tooltip, Filler, Legend)

const LINE_OPTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { mode: 'index' } },
  scales: {
    x: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 10 }, maxTicksLimit: 10 } },
    y: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 10 } } },
  },
}

function MetricRow({ label, value, baseline, unit = '' }) {
  const deviation = baseline?.mean ? ((value - baseline.mean) / Math.max(baseline.std || 1, 0.01)) : null
  const isAnomaly = Math.abs(deviation) > 2
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid rgba(30,45,69,0.5)' }}>
      <div style={{ flex: 1, fontSize: 13, color: 'var(--text-secondary)' }}>{label}</div>
      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, fontWeight: 600, color: isAnomaly ? '#ef4444' : 'var(--text-primary)' }}>
        {typeof value === 'number' ? value.toFixed(1) : value}{unit}
      </div>
      {deviation !== null && (
        <div style={{ marginLeft: 12, fontSize: 11, color: isAnomaly ? '#ef4444' : 'var(--text-muted)', minWidth: 60, textAlign: 'right' }}>
          {isAnomaly ? '⚠ ' : ''}{deviation > 0 ? '+' : ''}{deviation.toFixed(1)}σ
        </div>
      )}
    </div>
  )
}

export default function UserBehaviorPage() {
  const { userId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/users/${userId}?days=60`)
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) return <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}><Activity size={24} style={{ marginRight: 10 }} />Loading behavior profile...</div>
  if (!data) return <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>User not found.</div>

  const { user, features_timeline, risk_timeline, alerts, baseline } = data
  const reversedFeatures = [...features_timeline].reverse()
  const reversedRisk = [...risk_timeline].reverse()
  const labels = reversedRisk.map(r => r.date)

  const riskChartData = {
    labels,
    datasets: [{
      label: 'Risk Score',
      data: reversedRisk.map(r => r.risk_score * 100),
      borderColor: '#ef4444',
      backgroundColor: 'rgba(239,68,68,0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 3,
    }],
  }

  const featureChartData = reversedFeatures.length > 0 ? {
    labels: reversedFeatures.map(f => f.date),
    datasets: [
      { label: 'Login Count', data: reversedFeatures.map(f => f.login_count), borderColor: '#3b82f6', tension: 0.3, pointRadius: 2 },
      { label: 'File Copies', data: reversedFeatures.map(f => f.file_copy_count), borderColor: '#f59e0b', tension: 0.3, pointRadius: 2 },
      { label: 'USB Events', data: reversedFeatures.map(f => f.usb_connect_count), borderColor: '#ef4444', tension: 0.3, pointRadius: 2 },
    ],
  } : null

  const latestFeat = reversedFeatures[reversedFeatures.length - 1] || {}
  const currentRisk = user.latest_risk_score
  const riskColor = currentRisk >= 0.9 ? '#ef4444' : currentRisk >= 0.75 ? '#f59e0b' : currentRisk >= 0.65 ? '#3b82f6' : '#10b981'

  return (
    <div className="animate-in" style={{ maxWidth: 1100 }}>
      {/* Header nav */}
      <button className="btn btn-ghost" style={{ marginBottom: 20 }} onClick={() => navigate('/dashboard')}>
        <ArrowLeft size={14} /> Back to Dashboard
      </button>

      {/* User hero */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 20, padding: '20px 24px' }}>
        <div style={{ width: 52, height: 52, borderRadius: 14, background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <User size={24} color="#3b82f6" />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'JetBrains Mono, monospace', marginBottom: 2 }}>{user.id}</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            {user.department || 'Unknown Dept'} · {user.role || 'Unknown Role'} · {user.is_active ? 'Active' : 'Inactive'}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 36, fontWeight: 900, color: riskColor }}>{(currentRisk * 100).toFixed(0)}%</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Current risk score</div>
        </div>
      </div>

      {/* Charts row — Risk + Activity + Login Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 20 }}>
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Risk Score — Last 60 Days</h3>
          <div style={{ height: 180 }}>
            <Line data={riskChartData} options={{ ...LINE_OPTS, scales: { ...LINE_OPTS.scales, y: { ...LINE_OPTS.scales.y, min: 0, max: 100 } } }} />
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Activity Metrics Timeline</h3>
          <div style={{ height: 180 }}>
            {featureChartData
              ? <Line data={featureChartData} options={{ ...LINE_OPTS, plugins: { legend: { display: true, labels: { color: '#94a3b8', font: { size: 10 } } } } }} />
              : <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>No feature data</div>
            }
          </div>
        </div>

        {/* Login Activity Distribution — regular vs after-hours */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Login Activity Distribution</h3>
          <div style={{ height: 180 }}>
            {reversedFeatures.length > 0 ? (
              <Bar
                data={{
                  labels: reversedFeatures.slice(-14).map(f => f.date?.slice(5) ?? ''),
                  datasets: [
                    {
                      label: 'Regular Logins',
                      data: reversedFeatures.slice(-14).map(f =>
                        Math.max(0, (f.login_count ?? 0) - (f.after_hours_login_count ?? 0))
                      ),
                      backgroundColor: '#3b82f6cc',
                      borderRadius: 4,
                      stack: 'logins',
                    },
                    {
                      label: 'After-Hours',
                      data: reversedFeatures.slice(-14).map(f => f.after_hours_login_count ?? 0),
                      backgroundColor: '#ef4444cc',
                      borderRadius: 4,
                      stack: 'logins',
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { display: true, position: 'bottom', labels: { color: '#94a3b8', font: { size: 9 }, boxWidth: 10 } },
                  },
                  scales: {
                    x: { stacked: true, grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 9 } } },
                    y: { stacked: true, beginAtZero: true, grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 9 } } },
                  },
                }}
              />
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>No feature data</div>
            )}
          </div>
        </div>
      </div>

      {/* Metrics + Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Latest day metrics */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>Latest Activity Snapshot</h3>
          {Object.keys(latestFeat).length > 0 ? (
            <>
              <MetricRow label="Login Count" value={latestFeat.login_count ?? 0} baseline={baseline?.login_count} />
              <MetricRow label="After-Hours Logins" value={latestFeat.after_hours_login_count ?? 0} baseline={baseline?.after_hours_login_count} />
              <MetricRow label="USB Connections" value={latestFeat.usb_connect_count ?? 0} baseline={baseline?.usb_connect_count} />
              <MetricRow label="File Copies (Removable)" value={latestFeat.file_copy_count ?? 0} baseline={baseline?.file_copy_count} />
              <MetricRow label="Emails Sent" value={latestFeat.email_sent_count ?? 0} baseline={baseline?.email_sent_count} />
              <MetricRow label="External Email Ratio" value={latestFeat.external_email_ratio ?? 0} baseline={baseline?.external_email_ratio} unit="%" />
              <MetricRow label="HTTP Requests" value={latestFeat.http_request_count ?? 0} baseline={baseline?.http_request_count} />
              <MetricRow label="File Sharing Visits" value={latestFeat.file_sharing_visit_count ?? 0} baseline={baseline?.file_sharing_visit_count} />
              <MetricRow label="Exfiltration Indicator" value={latestFeat.exfil_indicator ?? 0} baseline={baseline?.exfil_indicator} />
              <MetricRow label="Behavior Spike Score" value={latestFeat.behavior_spike_score ?? 0} />
            </>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No feature data available yet.</div>
          )}
        </div>

        {/* Alerts on this user */}
        <div className="card">
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>User Alerts ({alerts.length})</h3>
          {alerts.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No alerts for this user.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {alerts.map(alert => (
                <div key={alert.id} style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: alert.severity === 'CRITICAL' ? '#ef4444' : alert.severity === 'HIGH' ? '#f59e0b' : '#3b82f6' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{alert.alert_type.replace(/_/g, ' ')}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{alert.date}</div>
                  </div>
                  <span className={`badge badge-${alert.severity.toLowerCase()}`}>{alert.severity}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
