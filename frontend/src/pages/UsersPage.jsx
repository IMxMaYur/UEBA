import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Search, ChevronRight, Activity, Map } from 'lucide-react'
import HeatmapPanel from '../components/HeatmapPanel'
import api from '../api'

function RiskBar({ score }) {
  const color = score >= 0.9 ? '#ef4444' : score >= 0.75 ? '#f59e0b' : score >= 0.65 ? '#3b82f6' : '#10b981'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score * 100}%`, background: color, borderRadius: 3 }} />
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

export default function UsersPage() {
  const [users, setUsers]     = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState('')
  const [minRisk, setMinRisk] = useState(0)
  const [sortBy, setSortBy]   = useState('risk')
  const [tab, setTab]         = useState('list') // 'list' | 'heatmap'
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    api.get(`/stats/leaderboard?limit=200`)
      .then(r => setUsers(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = users
    .filter(u =>
      u.risk_score >= minRisk &&
      (!search ||
        u.user_id.toLowerCase().includes(search.toLowerCase()) ||
        (u.name || '').toLowerCase().includes(search.toLowerCase()) ||
        (u.department || '').toLowerCase().includes(search.toLowerCase()))
    )
    .sort((a, b) => {
      if (sortBy === 'id')   return a.user_id.localeCompare(b.user_id)
      if (sortBy === 'dept') return (a.department || '').localeCompare(b.department || '')
      return b.risk_score - a.risk_score
    })

  const tabBtn = (id, label, Icon) => (
    <button
      onClick={() => setTab(id)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
        background: tab === id ? 'rgba(59,130,246,0.15)' : 'transparent',
        border: `1px solid ${tab === id ? 'rgba(59,130,246,0.35)' : 'var(--border)'}`,
        color: tab === id ? '#3b82f6' : 'var(--text-secondary)',
        transition: 'all 0.15s',
      }}>
      <Icon size={13} />{label}
    </button>
  )

  return (
    <div className="animate-in" style={{ maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Users size={20} color="#3b82f6" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>User Registry</h1>
          {!loading && <span className="badge badge-medium">{filtered.length} users</span>}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {tabBtn('list',    'List View',     Users)}
          {tabBtn('heatmap', 'Dept Heatmap',  Map)}
        </div>
      </div>

      {/* Filters (only on list tab) */}
      {tab === 'list' && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search ID, name, department..."
              style={{ paddingLeft: 32, paddingRight: 12, height: 34, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', width: 240 }}
            />
          </div>
          <select value={minRisk} onChange={e => setMinRisk(Number(e.target.value))}
            style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
            <option value={0}>All Risk Levels</option>
            <option value={0.65}>High-Risk Only (≥65%)</option>
            <option value={0.80}>Critical Only (≥80%)</option>
          </select>
          <select value={sortBy} onChange={e => setSortBy(e.target.value)}
            style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
            <option value="risk">Sort: Risk Score</option>
            <option value="id">Sort: User ID</option>
            <option value="dept">Sort: Department</option>
          </select>
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 80, color: 'var(--text-muted)' }}>
          <Activity size={20} style={{ marginRight: 8 }} />Loading users...
        </div>
      ) : tab === 'heatmap' ? (
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 20 }}>DEPARTMENT RISK HEATMAP</h3>
          <HeatmapPanel users={users} />
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>
          <Users size={40} style={{ opacity: 0.25, display: 'block', margin: '0 auto 12px' }} />
          No users match your filters.
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>User ID</th>
                <th>Name</th>
                <th>Department</th>
                <th>Risk Score</th>
                <th>Severity</th>
                <th>Open Alerts</th>
                <th>Total Alerts</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(user => (
                <tr key={user.user_id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/users/${user.user_id}`)}>
                  <td><span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 600 }}>{user.user_id}</span></td>
                  <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{user.name || '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{user.department || '—'}</td>
                  <td style={{ minWidth: 150 }}><RiskBar score={user.risk_score} /></td>
                  <td>{getSeverityBadge(user.risk_score)}</td>
                  <td>{user.open_alerts > 0 ? <span style={{ fontSize: 13, fontWeight: 700, color: '#ef4444' }}>{user.open_alerts}</span> : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>—</span>}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{user.total_alerts}</td>
                  <td><ChevronRight size={14} color="var(--text-muted)" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
