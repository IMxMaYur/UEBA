import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Search, ChevronRight, Activity, Brain, Shield, Eye, Heart } from 'lucide-react'
import api from '../api'

// ─── OCEAN Helpers ────────────────────────────────────────────────────────────

// Returns a human-readable label + description based on trait score (10–50)
function oceanLabel(score) {
  if (score === null || score === undefined) return { level: '—', desc: 'No data' }
  if (score >= 42) return { level: 'Very High', desc: '↑↑' }
  if (score >= 34) return { level: 'High',      desc: '↑' }
  if (score >= 26) return { level: 'Average',   desc: '→' }
  if (score >= 18) return { level: 'Low',        desc: '↓' }
  return                  { level: 'Very Low',  desc: '↓↓' }
}

// Readable security-relevant tip for each OCEAN trait
const OCEAN_META = {
  O: { name: 'Openness',          color: '#8b5cf6', icon: '🔭', tip: (lv) => lv === 'Very High' || lv === 'High' ? 'Curious, may explore policy boundaries' : lv === 'Very Low' || lv === 'Low' ? 'Conventional, unlikely to deviate' : 'Balanced approach to new experiences' },
  C: { name: 'Conscientiousness', color: '#10b981', icon: '📋', tip: (lv) => lv === 'Very High' || lv === 'High' ? 'Rule-follower, low insider risk' : lv === 'Very Low' || lv === 'Low' ? 'Disorganised, may overlook security policies' : 'Moderate adherence to procedures' },
  E: { name: 'Extraversion',      color: '#f59e0b', icon: '💬', tip: (lv) => lv === 'Very High' || lv === 'High' ? 'Outgoing, may share information freely' : lv === 'Very Low' || lv === 'Low' ? 'Introverted, acts independently' : 'Moderately social in work context' },
  A: { name: 'Agreeableness',     color: '#06b6d4', icon: '🤝', tip: (lv) => lv === 'Very High' || lv === 'High' ? 'Cooperative, easily influenced' : lv === 'Very Low' || lv === 'Low' ? 'Competitive, may bypass norms' : 'Balanced trust and caution' },
  N: { name: 'Neuroticism',       color: '#ef4444', icon: '⚡', tip: (lv) => lv === 'Very High' || lv === 'High' ? 'Stress-prone — elevated vulnerability indicator' : lv === 'Very Low' || lv === 'Low' ? 'Emotionally stable, resilient' : 'Moderate emotional reactivity' },
}

function OCEANBar({ label, score, meta }) {
  const { level, desc } = oceanLabel(score)
  // Normalize 10–50 to 0–100%
  const pct = score !== null && score !== undefined ? Math.round(((score - 10) / 40) * 100) : 0
  const col = meta.color
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: col }}>{meta.icon} {meta.name}</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{score ?? '?'} · {level}</span>
      </div>
      <div style={{ height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: col, borderRadius: 2, transition: 'width 0.4s' }} />
      </div>
    </div>
  )
}

function OCEANSummaryBadge({ O, C, E, A, N }) {
  // Risk-relevant signal: High N + Low C = elevated insider risk
  const highN = N >= 34, lowC = C <= 26, highE = E >= 34
  if (highN && lowC) return <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 999, background: 'rgba(239,68,68,0.12)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)', fontWeight: 700 }}>⚠ High-Risk Profile</span>
  if (highN)        return <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 999, background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', fontWeight: 700 }}>Stress-Prone</span>
  if (lowC)         return <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 999, background: 'rgba(251,191,36,0.12)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.3)', fontWeight: 700 }}>Low Compliance</span>
  return                   <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 999, background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.3)', fontWeight: 700 }}>Normal Profile</span>
}

function RiskBar({ score }) {
  const color = score >= 0.9 ? '#ef4444' : score >= 0.75 ? '#f59e0b' : score >= 0.5 ? '#3b82f6' : '#10b981'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 5, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score * 100}%`, background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, minWidth: 32, textAlign: 'right' }}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  )
}

function SeverityBadge({ score }) {
  if (score >= 0.90) return <span className="badge badge-critical">Critical</span>
  if (score >= 0.80) return <span className="badge badge-high">High</span>
  if (score >= 0.50) return <span className="badge badge-medium">Medium</span>
  if (score > 0)     return <span className="badge badge-low">Low</span>
  return <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Not monitored</span>
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function UsersPage() {
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [filterRisk, setFilterRisk] = useState('all') // 'all' | 'monitored' | 'high' | 'profile'
  const [sortBy, setSortBy]     = useState('name')
  const [expanded, setExpanded] = useState(null) // user_id of expanded OCEAN row
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    api.get('/users?limit=1500')
      .then(r => setUsers(r.data || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = users
    .filter(u => {
      const q = search.toLowerCase()
      const matchSearch = !q ||
        u.id.toLowerCase().includes(q) ||
        (u.name || '').toLowerCase().includes(q)

      let matchFilter = true
      if (filterRisk === 'monitored') matchFilter = u.latest_risk_score > 0
      else if (filterRisk === 'high')  matchFilter = u.latest_risk_score >= 0.65
      else if (filterRisk === 'profile') {
        // High-Risk OCEAN profile: High N + Low C
        matchFilter = (u.ocean_N ?? 0) >= 34 && (u.ocean_C ?? 50) <= 26
      }
      return matchSearch && matchFilter
    })
    .sort((a, b) => {
      if (sortBy === 'risk')  return b.latest_risk_score - a.latest_risk_score
      if (sortBy === 'id')    return a.id.localeCompare(b.id)
      if (sortBy === 'neuroticism') return (b.ocean_N ?? 0) - (a.ocean_N ?? 0)
      // default: name
      return (a.name || a.id).localeCompare(b.name || b.id)
    })

  const monitoredCount = users.filter(u => u.latest_risk_score > 0).length
  const highRiskCount  = users.filter(u => u.latest_risk_score >= 0.65).length
  const profileRiskCount = users.filter(u => (u.ocean_N ?? 0) >= 34 && (u.ocean_C ?? 50) <= 26).length

  return (
    <div className="animate-in" style={{ maxWidth: 1300 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Users size={20} color="#3b82f6" />
            <h1 style={{ fontSize: 22, fontWeight: 800 }}>User Registry</h1>
            {!loading && <span className="badge badge-medium">{filtered.length} / {users.length} users</span>}
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            CERT r4.2 employees with Big Five (OCEAN) personality profiling. Click any row to see details.
          </p>
        </div>
      </div>

      {/* Summary stats */}
      {!loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Total Employees', value: users.length, color: '#3b82f6', icon: <Users size={15} /> },
            { label: 'Being Monitored', value: monitoredCount, color: '#10b981', icon: <Activity size={15} /> },
            { label: 'High-Risk Score', value: highRiskCount, color: '#f59e0b', icon: <Shield size={15} /> },
            { label: 'High-Risk OCEAN Profile', value: profileRiskCount, color: '#ef4444', icon: <Brain size={15} /> },
          ].map(s => (
            <div key={s.label} className="card" style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: `${s.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: s.color, flexShrink: 0 }}>
                {s.icon}
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        {/* Search */}
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search name or user ID…"
            style={{ paddingLeft: 32, paddingRight: 12, height: 34, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', width: 220 }} />
        </div>

        {/* Risk filter */}
        <select value={filterRisk} onChange={e => setFilterRisk(e.target.value)}
          style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
          <option value="all">All Employees</option>
          <option value="monitored">Being Monitored</option>
          <option value="high">High Risk Score (≥65%)</option>
          <option value="profile">High-Risk OCEAN Profile</option>
        </select>

        {/* Sort */}
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}
          style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
          <option value="name">Sort: Name</option>
          <option value="risk">Sort: Risk Score ↓</option>
          <option value="id">Sort: User ID</option>
          <option value="neuroticism">Sort: Neuroticism ↓</option>
        </select>
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 80, color: 'var(--text-muted)' }}>
          <Activity size={20} style={{ marginRight: 8 }} />Loading employees…
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
                <th style={{ width: 100 }}>User ID</th>
                <th>Employee Name</th>
                <th style={{ width: 140 }}>OCEAN Profile</th>
                <th style={{ width: 60, textAlign: 'center' }}>O</th>
                <th style={{ width: 60, textAlign: 'center' }}>C</th>
                <th style={{ width: 60, textAlign: 'center' }}>E</th>
                <th style={{ width: 60, textAlign: 'center' }}>A</th>
                <th style={{ width: 60, textAlign: 'center' }}>N</th>
                <th style={{ width: 140 }}>Risk Score</th>
                <th style={{ width: 110 }}>Status</th>
                <th style={{ width: 30 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(user => {
                const isExpanded = expanded === user.id
                const hasOcean = user.ocean_O !== null && user.ocean_O !== undefined
                return (
                  <>
                    <tr key={user.id}
                      style={{ cursor: 'pointer', background: isExpanded ? 'rgba(59,130,246,0.05)' : undefined }}
                      onClick={() => setExpanded(isExpanded ? null : user.id)}>

                      <td><span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 700, color: '#3b82f6' }}>{user.id}</span></td>

                      <td>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{user.name || user.id}</div>
                      </td>

                      <td>
                        {hasOcean
                          ? <OCEANSummaryBadge O={user.ocean_O} C={user.ocean_C} E={user.ocean_E} A={user.ocean_A} N={user.ocean_N} />
                          : <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>}
                      </td>

                      {/* Individual OCEAN scores */}
                      {['ocean_O','ocean_C','ocean_E','ocean_A','ocean_N'].map(key => {
                        const val = user[key]
                        const trait = key.split('_')[1]
                        const meta = OCEAN_META[trait]
                        const pct = val !== null && val !== undefined ? Math.round(((val - 10) / 40) * 100) : 0
                        return (
                          <td key={key} style={{ textAlign: 'center' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                              <div style={{ fontSize: 12, fontWeight: 800, color: meta.color }}>{val ?? '—'}</div>
                              <div style={{ width: 28, height: 3, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${pct}%`, background: meta.color }} />
                              </div>
                            </div>
                          </td>
                        )
                      })}

                      <td><RiskBar score={user.latest_risk_score} /></td>
                      <td><SeverityBadge score={user.latest_risk_score} /></td>
                      <td>
                        <ChevronRight size={14} color="var(--text-muted)"
                          style={{ transform: isExpanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
                      </td>
                    </tr>

                    {/* Expanded OCEAN detail row */}
                    {isExpanded && (
                      <tr key={`${user.id}-detail`}>
                        <td colSpan={11} style={{ padding: 0, background: 'var(--bg-secondary)' }}>
                          <div style={{ padding: '16px 24px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
                            {/* OCEAN bars */}
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
                                🧠 Big Five Personality (OCEAN)
                              </div>
                              {hasOcean ? (
                                <>
                                  {Object.entries(OCEAN_META).map(([trait, meta]) => (
                                    <OCEANBar key={trait} label={trait} score={user[`ocean_${trait}`]} meta={meta} />
                                  ))}
                                </>
                              ) : <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No psychometric data available.</div>}
                            </div>

                            {/* Security interpretation */}
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
                                🔒 Security Interpretation
                              </div>
                              {hasOcean ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                  {Object.entries(OCEAN_META).map(([trait, meta]) => {
                                    const val = user[`ocean_${trait}`]
                                    const { level } = oceanLabel(val)
                                    const tip = meta.tip(level)
                                    return (
                                      <div key={trait} style={{ display: 'flex', gap: 8, fontSize: 12 }}>
                                        <span style={{ color: meta.color, fontWeight: 700, minWidth: 20 }}>{meta.icon}</span>
                                        <span style={{ color: 'var(--text-secondary)' }}><strong>{meta.name}:</strong> {tip}</span>
                                      </div>
                                    )
                                  })}
                                </div>
                              ) : <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Profile unavailable.</div>}
                            </div>

                            {/* User actions */}
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
                                📋 Employee Overview
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                <div style={{ fontSize: 12 }}><span style={{ color: 'var(--text-muted)' }}>ID:</span> <span style={{ fontFamily: 'monospace', color: '#3b82f6', fontWeight: 700 }}>{user.id}</span></div>
                                <div style={{ fontSize: 12 }}><span style={{ color: 'var(--text-muted)' }}>Name:</span> <span style={{ color: 'var(--text-secondary)' }}>{user.name || '—'}</span></div>
                                <div style={{ fontSize: 12 }}><span style={{ color: 'var(--text-muted)' }}>Status:</span> <span style={{ color: user.latest_risk_score > 0 ? '#10b981' : 'var(--text-muted)' }}>{user.latest_risk_score > 0 ? '● Active monitoring' : '○ Not yet monitored'}</span></div>
                                <div style={{ fontSize: 12 }}><span style={{ color: 'var(--text-muted)' }}>Risk Score:</span> <span style={{ fontWeight: 700, color: user.latest_risk_score >= 0.65 ? '#ef4444' : '#10b981' }}>{(user.latest_risk_score * 100).toFixed(1)}%</span></div>
                              </div>
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/users/${user.id}`) }}
                                className="btn btn-primary"
                                style={{ marginTop: 16, fontSize: 11, padding: '6px 14px' }}>
                                View Behavior Timeline →
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
