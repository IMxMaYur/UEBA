import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, Info, CheckCircle, Search, XCircle, MessageSquare, Send, Microscope, Trash2 } from 'lucide-react'
import api from '../api'
import { useAuth } from '../useAuth'


function ShapPanel({ shap }) {
  if (!shap || shap.length === 0) return null
  return (
    <div style={{ marginTop: 16, padding: 14, background: 'var(--bg-secondary)', borderRadius: 10, border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>
        🔍 SHAP Explanation — Top contributing features
      </div>
      {shap.map((f, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>{f.friendly_name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Value: {typeof f.value === 'number' ? f.value.toFixed(2) : f.value}</div>
          </div>
          <div style={{ textAlign: 'right', minWidth: 80 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: f.direction === 'increases_risk' ? '#ef4444' : '#10b981' }}>
              {f.direction === 'increases_risk' ? '▲' : '▼'} {Math.abs(f.shap_value).toFixed(3)}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>SHAP impact</div>
          </div>
          <div style={{ width: 80 }}>
            <div style={{ height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(100, Math.abs(f.shap_value) * 200)}%`, background: f.direction === 'increases_risk' ? '#ef4444' : '#10b981', borderRadius: 2 }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function NoteForm({ alertId, onSave }) {
  const { email } = useAuth()
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!note.trim()) return
    setSaving(true)
    try {
      await api.post(`/investigation/alerts/${alertId}/notes`, {
        note: note.trim(),
        analyst: email || 'analyst',
      })
      setNote('')
      onSave()
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  return (
    <div style={{ marginTop: 14, padding: 14, background: 'rgba(59,130,246,0.06)', borderRadius: 8, border: '1px solid rgba(59,130,246,0.15)' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
        <MessageSquare size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />Add Analyst Note
      </div>
      <textarea
        value={note}
        onChange={e => setNote(e.target.value)}
        placeholder="Describe your findings, next steps, or resolution..."
        rows={3}
        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: 12, resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box' }}
      />
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={submit}
          disabled={saving || !note.trim()}
          className="btn btn-primary"
          style={{ fontSize: 11, padding: '5px 14px', display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Send size={11} /> {saving ? 'Saving...' : 'Save Note'}
        </button>
      </div>
    </div>
  )
}

export default function AlertsPage() {
  const [alerts, setAlerts]           = useState([])
  const [loading, setLoading]         = useState(true)
  const [expanded, setExpanded]       = useState(null)
  const [statusFilter, setStatusFilter]   = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [search, setSearch]           = useState('')
  const [selected, setSelected]       = useState(new Set())
  const [bulkStatus, setBulkStatus]   = useState('RESOLVED')
  const [bulking, setBulking]         = useState(false)
  const navigate = useNavigate()

  const fetchAlerts = () => {
    setLoading(true)
    const params = new URLSearchParams({ limit: 100 })
    if (statusFilter)   params.append('status', statusFilter)
    if (severityFilter) params.append('severity', severityFilter)
    api.get(`/alerts?${params}`).then(r => setAlerts(r.data)).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => { fetchAlerts() }, [statusFilter, severityFilter])

  const updateStatus = async (id, status) => {
    await api.patch(`/alerts/${id}`, { status })
    fetchAlerts()
  }

  const bulkUpdate = async () => {
    if (selected.size === 0) return
    setBulking(true)
    try {
      await api.patch('/alerts/bulk', { alert_ids: [...selected], status: bulkStatus })
      setSelected(new Set())
      fetchAlerts()
    } catch (e) { console.error(e) }
    finally { setBulking(false) }
  }

  const dismissAlert = async (id) => {
    try {
      await api.delete(`/alerts/${id}`)
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch (e) { console.error(e) }
  }

  const toggleSelect = (id) => setSelected(s => {
    const n = new Set(s)
    n.has(id) ? n.delete(id) : n.add(id)
    return n
  })

  const filtered = alerts.filter(a =>
    !search || a.user_id.toLowerCase().includes(search.toLowerCase()) || a.alert_type.toLowerCase().includes(search.toLowerCase())
  )

  const allFiltered = filtered.length > 0 && filtered.every(a => selected.has(a.id))

  const toggleAll = () => {
    if (allFiltered) setSelected(new Set())
    else setSelected(new Set(filtered.map(a => a.id)))
  }

  return (
    <div className="animate-in" style={{ maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Bell size={20} color="#ef4444" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Alert Investigation</h1>
          {alerts.length > 0 && <span className="badge badge-medium">{filtered.length} alerts</span>}
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search user or type..."
              style={{ paddingLeft: 32, paddingRight: 12, height: 34, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13, outline: 'none', width: 200 }} />
          </div>
          <select value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}
            style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
            <option value="">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
            <option value="">All Statuses</option>
            <option value="OPEN">Open</option>
            <option value="INVESTIGATING">Investigating</option>
            <option value="RESOLVED">Resolved</option>
            <option value="FALSE_POSITIVE">False Positive</option>
          </select>
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, padding: '10px 16px', background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{selected.size} selected</span>
          <select value={bulkStatus} onChange={e => setBulkStatus(e.target.value)}
            style={{ padding: '5px 10px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-secondary)', fontSize: 12, outline: 'none' }}>
            <option value="RESOLVED">Mark Resolved</option>
            <option value="INVESTIGATING">Mark Investigating</option>
            <option value="FALSE_POSITIVE">Mark False Positive</option>
            <option value="OPEN">Mark Open</option>
          </select>
          <button onClick={bulkUpdate} disabled={bulking} className="btn btn-primary" style={{ fontSize: 12, padding: '5px 14px' }}>
            {bulking ? 'Updating...' : 'Apply'}
          </button>
          <button onClick={() => setSelected(new Set())} className="btn btn-ghost" style={{ fontSize: 12, padding: '5px 10px' }}>
            <XCircle size={13} /> Clear
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 60 }}>Loading alerts...</div>
      ) : filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
          <Bell size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <div>No alerts found. Try running an attack simulation.</div>
        </div>
      ) : (
        <div>
          {/* Select-all row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, paddingLeft: 4 }}>
            <input type="checkbox" checked={allFiltered} onChange={toggleAll} style={{ cursor: 'pointer' }} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Select all visible</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filtered.map(alert => (
              <div key={alert.id} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer' }}
                  onClick={() => setExpanded(expanded === alert.id ? null : alert.id)}>
                  {/* Checkbox */}
                  <div onClick={e => { e.stopPropagation(); toggleSelect(alert.id) }}
                    style={{ display: 'flex', alignItems: 'center' }}>
                    <input type="checkbox" checked={selected.has(alert.id)} readOnly style={{ cursor: 'pointer' }} />
                  </div>

                  <div style={{ width: 10, height: 10, borderRadius: '50%', flexShrink: 0, background: alert.severity === 'CRITICAL' ? '#ef4444' : alert.severity === 'HIGH' ? '#f59e0b' : '#3b82f6' }} />

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 14, fontWeight: 700 }}>{alert.alert_type.replace(/_/g, ' ')}</span>
                      <span className={`badge badge-${alert.severity.toLowerCase()}`}>{alert.severity}</span>
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4,
                        background: alert.status === 'OPEN' ? 'rgba(239,68,68,0.1)' : alert.status === 'INVESTIGATING' ? 'rgba(245,158,11,0.1)' : alert.status === 'FALSE_POSITIVE' ? 'rgba(100,116,139,0.1)' : 'rgba(16,185,129,0.1)',
                        color: alert.status === 'OPEN' ? '#ef4444' : alert.status === 'INVESTIGATING' ? '#f59e0b' : alert.status === 'FALSE_POSITIVE' ? '#64748b' : '#10b981',
                        fontWeight: 600 }}>
                        {alert.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>
                      User: <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>{alert.user_id}</span>
                      &nbsp;·&nbsp;{alert.date}
                      &nbsp;·&nbsp;Risk: <span style={{ fontWeight: 700, color: '#f59e0b' }}>{(alert.risk_score * 100).toFixed(0)}%</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
                    {alert.status === 'OPEN' && (
                      <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => updateStatus(alert.id, 'INVESTIGATING')}>
                        <Info size={12} /> Investigate
                      </button>
                    )}
                    {alert.status !== 'RESOLVED' && alert.status !== 'FALSE_POSITIVE' && (
                      <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px', color: '#10b981', borderColor: 'rgba(16,185,129,0.3)' }} onClick={() => updateStatus(alert.id, 'RESOLVED')}>
                        <CheckCircle size={12} /> Resolve
                      </button>
                    )}
                    {alert.status === 'OPEN' && (
                      <button className="btn btn-ghost" style={{ fontSize: 11, padding: '4px 10px', color: '#64748b', borderColor: 'rgba(100,116,139,0.3)' }} onClick={() => updateStatus(alert.id, 'FALSE_POSITIVE')}>
                        <XCircle size={12} /> False Positive
                      </button>
                    )}
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: 11, padding: '4px 10px', color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)' }}
                      onClick={() => dismissAlert(alert.id)}
                      title="Dismiss from dashboard (keeps record in database)">
                      <Trash2 size={12} /> Dismiss
                    </button>
                  </div>
                  <ChevronDown size={16} color="var(--text-muted)" style={{ transform: expanded === alert.id ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }} />
                </div>

                {expanded === alert.id && (
                  <div style={{ padding: '0 20px 16px' }}>
                    {/* Full investigation link */}
                    <div style={{ marginBottom: 10 }}>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 12, color: '#8b5cf6', borderColor: 'rgba(139,92,246,0.3)' }}
                        onClick={() => navigate(`/app/alerts/${alert.id}/investigate`)}

                      >
                        <Microscope size={13} /> Full Investigation
                      </button>
                    </div>
                    {alert.notes && (
                      <div style={{ marginBottom: 10, padding: 10, background: 'rgba(245,158,11,0.08)', borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', borderLeft: '3px solid #f59e0b', whiteSpace: 'pre-wrap' }}>
                        📝 {alert.notes}
                      </div>
                    )}
                    <ShapPanel shap={alert.shap_json} />
                    <NoteForm alertId={alert.id} onSave={fetchAlerts} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
