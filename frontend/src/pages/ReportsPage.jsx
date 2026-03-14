import { useState, useEffect } from 'react'
import { FileBarChart, Download } from 'lucide-react'
import { Bar } from 'react-chartjs-2'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js'
import ReportDownloader from '../components/ReportDownloader'
import api from '../api'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

const REPORT_TYPES = [
  { id: 'threat_summary', label: 'Insider Threat Summary', icon: '🛡️', color: '#ef4444', desc: 'Overview of all detected threats and their severity distribution.' },
  { id: 'risky_users',    label: 'Risky User Report',      icon: '👤', color: '#f59e0b', desc: 'Ranked list of highest-risk employees with behavioral profiles.' },
  { id: 'anomaly_report', label: 'Anomaly Detection Report', icon: '📊', color: '#8b5cf6', desc: 'ML model outputs, anomaly scores, and detection accuracy metrics.' },
]

export default function ReportsPage() {
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeReport, setActiveReport] = useState('threat_summary')

  useEffect(() => {
    Promise.all([
      api.get('/stats/overview').catch(() => ({ data: null })),
      api.get('/stats/leaderboard?limit=100').catch(() => ({ data: [] })),
      api.get('/alerts?limit=200').catch(() => ({ data: [] })),
    ]).then(([s, lb, a]) => {
      setStats(s.data)
      setUsers(lb.data || [])
      setAlerts(a.data || [])
    }).finally(() => setLoading(false))
  }, [])

  const getReportData = () => {
    if (activeReport === 'threat_summary') return alerts.map(a => ({
      alert_id: a.id, user_id: a.user_id, alert_type: a.alert_type,
      severity: a.severity, status: a.status, date: a.date, risk_score: a.risk_score,
    }))
    if (activeReport === 'risky_users') return users.map(u => ({
      user_id: u.user_id, name: u.name || '', department: u.department || '',
      risk_score: (u.risk_score * 100).toFixed(1) + '%', open_alerts: u.open_alerts,
    }))
    if (activeReport === 'anomaly_report') return users.map(u => ({
      user_id: u.user_id, risk_score: u.risk_score, open_alerts: u.open_alerts, department: u.department,
    }))
    return []
  }

  // Severity distribution chart
  const sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }
  alerts.forEach(a => { if (sevCounts[a.severity] !== undefined) sevCounts[a.severity]++ })

  const sevBar = {
    labels: Object.keys(sevCounts),
    datasets: [{ data: Object.values(sevCounts), backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981'], borderRadius: 8 }],
  }

  const reportName = REPORT_TYPES.find(r => r.id === activeReport)?.label.toLowerCase().replace(/ /g, '_') || 'report'

  return (
    <div className="animate-in" style={{ maxWidth: 1100 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <FileBarChart size={20} color="#10b981" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Security Reports</h1>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Export insider threat analytics in CSV, JSON, or PDF format</p>
      </div>

      {/* Summary cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 14, marginBottom: 24 }}>
          {[
            { label: 'Total Alerts', value: alerts.length, color: '#ef4444' },
            { label: 'High-Risk Users', value: stats.high_risk_users || 0, color: '#f59e0b' },
            { label: 'Resolved', value: alerts.filter(a => a.status === 'RESOLVED').length, color: '#10b981' },
            { label: 'Open', value: alerts.filter(a => a.status === 'OPEN').length, color: '#3b82f6' },
          ].map(m => (
            <div key={m.label} className="card" style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: m.color }}>{m.value}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{m.label}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 20 }}>
        {/* Report type selector */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12 }}>SELECT REPORT TYPE</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
            {REPORT_TYPES.map(r => (
              <div key={r.id}
                onClick={() => setActiveReport(r.id)}
                className="card"
                style={{ cursor: 'pointer', borderColor: activeReport === r.id ? r.color : undefined, padding: '14px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <span style={{ fontSize: 18 }}>{r.icon}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: activeReport === r.id ? r.color : 'var(--text-primary)' }}>{r.label}</span>
                </div>
                <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.desc}</p>
              </div>
            ))}
          </div>

          {/* Download buttons */}
          <div className="card">
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Download size={13} color="#10b981" /> EXPORT: {REPORT_TYPES.find(r => r.id === activeReport)?.label}
            </div>
            <ReportDownloader data={getReportData()} reportName={reportName} />
            {loading && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>Loading report data...</div>}
            {!loading && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>{getReportData().length} records ready to export</div>}
          </div>
        </div>

        {/* Preview + charts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Alert severity chart */}
          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 14 }}>ALERT SEVERITY DISTRIBUTION</h3>
            <div style={{ height: 180 }}>
              <Bar data={sevBar} options={{
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                  x: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 11 } } },
                  y: { grid: { color: 'rgba(30,45,69,0.6)' }, ticks: { color: '#475569', font: { size: 11 } }, beginAtZero: true },
                },
              }} />
            </div>
          </div>

          {/* Data preview table */}
          <div className="card" style={{ padding: 0 }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)' }}>
              DATA PREVIEW (first 5 rows)
            </div>
            <div style={{ overflowX: 'auto', maxHeight: 260 }}>
              {getReportData().length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr>{Object.keys(getReportData()[0]).map(k => <th key={k}>{k.replace(/_/g, ' ')}</th>)}</tr>
                  </thead>
                  <tbody>
                    {getReportData().slice(0, 5).map((row, i) => (
                      <tr key={i}>{Object.values(row).map((v, j) => <td key={j} style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{String(v)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>No data available yet. Run the pipeline first.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
