import { useState, useEffect } from 'react'
import { Shield, ChevronRight, Clock, AlertTriangle, Search } from 'lucide-react'
import TimelineViewer from '../components/TimelineViewer'
import api from '../api'

const SEV_BADGE = {
  CRITICAL: 'badge-critical', HIGH: 'badge-high', MEDIUM: 'badge-medium', LOW: 'badge-low',
}

const PATTERNS = [
  { name: 'Data Exfiltration',      icon: '💾', color: '#ef4444', events: ['LOGIN', 'FILE_ACCESS', 'USB_COPY', 'WEB_VISIT'] },
  { name: 'Credential Misuse',      icon: '🔑', color: '#f97316', events: ['LOGIN', 'LOGIN', 'FILE_ACCESS'] },
  { name: 'Disgruntled Employee',   icon: '😠', color: '#f59e0b', events: ['FILE_ACCESS', 'WEB_VISIT', 'EMAIL_SEND'] },
  { name: 'Privilege Abuse',        icon: '⚡', color: '#8b5cf6', events: ['FILE_ACCESS', 'USB_COPY', 'EMAIL_SEND'] },
  { name: 'Insider Sabotage',       icon: '💣', color: '#ef4444', events: ['LOGIN', 'FILE_ACCESS', 'FILE_ACCESS'] },
]

function PatternBadge({ name }) {
  const p = PATTERNS.find(x => name && name.toLowerCase().includes(x.name.split(' ')[0].toLowerCase()))
  if (!p) return <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{name || 'Unknown'}</span>
  return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 10px', borderRadius: 999, background: `${p.color}15`, color: p.color, border: `1px solid ${p.color}40` }}>
      {p.icon} {p.name}
    </span>
  )
}

export default function IncidentsPage() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [timelineLoading, setTimelineLoading] = useState(false)

  useEffect(() => {
    api.get('/alerts?status=INVESTIGATING&limit=100')
      .then(r => setAlerts(r.data))
      .catch(() => api.get('/alerts?limit=50').then(r => setAlerts(r.data.filter(a => a.status !== 'RESOLVED'))))
      .finally(() => setLoading(false))
  }, [])

  const openInvestigation = async (alert) => {
    setSelected(alert)
    setTimelineLoading(true)
    try {
      const r = await api.get(`/investigation/users/${alert.user_id}/timeline`)
      setTimeline(r.data || [])
    } catch {
      setTimeline([])
    } finally { setTimelineLoading(false) }
  }

  const filtered = alerts.filter(a => {
    if (!search) return true
    const q = search.toLowerCase()
    return a.user_id?.toLowerCase().includes(q) || a.alert_type?.toLowerCase().includes(q)
  })

  return (
    <div className="animate-in" style={{ maxWidth: 1300 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Shield size={20} color="#8b5cf6" />
            <h1 style={{ fontSize: 22, fontWeight: 800 }}>Incident Investigation</h1>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Correlated multi-event threat patterns & forensic investigation</p>
        </div>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search user or alert type..."
            style={{ paddingLeft: 32, paddingRight: 12, height: 36, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', width: 260 }} />
        </div>
      </div>

      {/* Attack Pattern legend */}
      <div className="card" style={{ marginBottom: 20, padding: '14px 20px' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>ATTACK PATTERN LIBRARY</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {PATTERNS.map(p => (
            <div key={p.name} style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '10px 14px', borderRadius: 10, background: `${p.color}08`, border: `1px solid ${p.color}25`, minWidth: 160 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: p.color }}>{p.icon} {p.name}</div>
              <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                {p.events.map((ev, i) => (
                  <span key={i} style={{ fontSize: 9, fontWeight: 600, padding: '1px 6px', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-muted)' }}>{ev}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1.2fr' : '1fr', gap: 20 }}>
        {/* Incident list */}
        <div>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading incidents...</div>
          ) : filtered.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
              <AlertTriangle size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
              <div>No active incidents found.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {filtered.map(alert => (
                <div key={alert.id}
                  className="card"
                  onClick={() => openInvestigation(alert)}
                  style={{ cursor: 'pointer', borderColor: selected?.id === alert.id ? 'var(--accent-purple)' : undefined, padding: '14px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                      background: alert.severity === 'CRITICAL' ? '#ef4444' : alert.severity === 'HIGH' ? '#f59e0b' : '#3b82f6' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 700 }}>{alert.alert_type?.replace(/_/g, ' ')}</span>
                        <span className={`badge ${SEV_BADGE[alert.severity] || 'badge-low'}`}>{alert.severity}</span>
                        <PatternBadge name={alert.alert_type?.replace(/_/g, ' ')} />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: 'var(--text-muted)' }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>{alert.user_id}</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={11} /> {alert.date}</span>
                        <span>Risk: <strong style={{ color: '#f59e0b' }}>{(alert.risk_score * 100).toFixed(0)}%</strong></span>
                      </div>
                    </div>
                    <ChevronRight size={16} color="var(--text-muted)" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Investigation panel */}
        {selected && (
          <div className="card" style={{ position: 'sticky', top: 20, maxHeight: '80vh', overflowY: 'auto', padding: 0 }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>📋 Investigation: <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#8b5cf6' }}>{selected.user_id}</span></div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{selected.alert_type?.replace(/_/g, ' ')} · {selected.date}</div>
            </div>

            {/* Risk breakdown */}
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>THREAT SCORE</div>
              <div style={{ fontSize: 36, fontWeight: 800, color: selected.risk_score >= 0.9 ? '#ef4444' : selected.risk_score >= 0.75 ? '#f97316' : '#f59e0b' }}>
                {(selected.risk_score * 100).toFixed(0)}
                <span style={{ fontSize: 14, color: 'var(--text-muted)', fontWeight: 400 }}>/100</span>
              </div>
              <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, marginTop: 10, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${selected.risk_score * 100}%`, background: 'linear-gradient(90deg, #f59e0b, #ef4444)', borderRadius: 3, transition: 'width 0.5s ease' }} />
              </div>
            </div>

            {/* SHAP */}
            {selected.shap_json && selected.shap_json.length > 0 && (
              <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>TOP RISK FACTORS</div>
                {selected.shap_json.slice(0, 5).map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 11, flex: 1, color: 'var(--text-secondary)' }}>{f.friendly_name}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: f.direction === 'increases_risk' ? '#ef4444' : '#10b981' }}>
                      {f.direction === 'increases_risk' ? '▲' : '▼'} {Math.abs(f.shap_value).toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Timeline */}
            <div style={{ padding: '14px 20px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>ACTIVITY TIMELINE</div>
              {timelineLoading ? (
                <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)', fontSize: 12 }}>Loading timeline...</div>
              ) : (
                <TimelineViewer events={timeline} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
