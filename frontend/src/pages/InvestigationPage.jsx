import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Tooltip, Legend,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'
import {
  ArrowLeft, Microscope, Clock, FileText, Shield,
  AlertTriangle, MessageSquare, Send, CheckCircle, XCircle, Share2,
} from 'lucide-react'
import api from '../api'
import { useAuth } from '../useAuth'
import NetworkGraph from '../components/NetworkGraph'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend)

const BAR_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { grid: { color: 'rgba(30,45,69,0.5)' }, ticks: { color: '#475569', font: { size: 10 } } },
    y: { grid: { color: 'rgba(30,45,69,0.5)' }, ticks: { color: '#475569', font: { size: 10 } }, beginAtZero: true },
  },
}

const EVENT_ICONS = {
  LOGIN:     { icon: '🔑', color: '#3b82f6' },
  ALERT:     { icon: '🚨', color: '#ef4444' },
  FILE_COPY: { icon: '📋', color: '#f59e0b' },
  USB:       { icon: '💾', color: '#8b5cf6' },
  EMAIL:     { icon: '✉️',  color: '#06b6d4' },
}

export default function InvestigationPage() {
  const { alertId } = useParams()
  const navigate    = useNavigate()
  const { email }   = useAuth()

  const [detail, setDetail]     = useState(null)
  const [timeline, setTimeline] = useState([])
  const [evidence, setEvidence] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [note, setNote]         = useState('')
  const [saving, setSaving]     = useState(false)
  const [tab, setTab]           = useState('overview')   // 'overview' | 'timeline' | 'evidence'

  useEffect(() => {
    if (!alertId) return
    setLoading(true)
    api.get(`/investigation/alerts/${alertId}`)
      .then(r => {
        setDetail(r.data)
        // Load timeline and evidence for this user
        return Promise.all([
          api.get(`/investigation/users/${r.data.user_id}/timeline`),
          api.get(`/investigation/users/${r.data.user_id}/evidence`),
        ])
      })
      .then(([t, e]) => {
        setTimeline(t.data)
        setEvidence(e.data)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [alertId])

  const updateStatus = async (status) => {
    await api.patch(`/investigation/alerts/${alertId}/status`, {
      status,
      reason: `Status changed to ${status} by ${email || 'analyst'}`,
    })
    const r = await api.get(`/investigation/alerts/${alertId}`)
    setDetail(r.data)
  }

  const submitNote = async () => {
    if (!note.trim()) return
    setSaving(true)
    try {
      await api.post(`/investigation/alerts/${alertId}/notes`, {
        note: note.trim(),
        analyst: email || 'analyst',
      })
      setNote('')
      const r = await api.get(`/investigation/alerts/${alertId}`)
      setDetail(r.data)
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--text-muted)' }}>
      <Microscope size={22} style={{ marginRight: 10 }} />Loading investigation...
    </div>
  )

  if (!detail) return (
    <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>Alert not found.</div>
  )

  const riskColor = detail.risk_score >= 0.9 ? '#ef4444' : detail.risk_score >= 0.75 ? '#f59e0b' : '#3b82f6'

  /* Timeline chart — bar per event type */
  const eventCounts = {}
  timeline.forEach(e => { eventCounts[e.event_type] = (eventCounts[e.event_type] || 0) + 1 })
  const timelineBarData = {
    labels: Object.keys(eventCounts),
    datasets: [{ data: Object.values(eventCounts), backgroundColor: Object.keys(eventCounts).map(k => EVENT_ICONS[k]?.color || '#3b82f6'), borderRadius: 6 }],
  }

  const TAB_STYLE = (t) => ({
    padding: '8px 18px', fontSize: 13, fontWeight: 600, cursor: 'pointer', borderBottom: '2px solid',
    borderColor: tab === t ? '#3b82f6' : 'transparent',
    color: tab === t ? '#3b82f6' : 'var(--text-muted)',
    background: 'none', border: 'none', borderBottom: `2px solid ${tab === t ? '#3b82f6' : 'transparent'}`,
  })

  return (
    <div className="animate-in" style={{ maxWidth: 1100 }}>
      {/* Back */}
      <button className="btn btn-ghost" style={{ marginBottom: 20 }} onClick={() => navigate('/alerts')}>
        <ArrowLeft size={14} /> Back to Alerts
      </button>

      {/* Alert hero card */}
      <div className="card" style={{ marginBottom: 20, padding: '20px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <AlertTriangle size={18} color={riskColor} />
              <h1 style={{ fontSize: 20, fontWeight: 800 }}>{detail.alert_type.replace(/_/g, ' ')}</h1>
              <span className={`badge badge-${detail.severity.toLowerCase()}`}>{detail.severity}</span>
              <span style={{
                fontSize: 11, padding: '2px 10px', borderRadius: 20, fontWeight: 700,
                background: detail.status === 'OPEN' ? 'rgba(239,68,68,0.12)' : detail.status === 'INVESTIGATING' ? 'rgba(245,158,11,0.12)' : 'rgba(16,185,129,0.12)',
                color: detail.status === 'OPEN' ? '#ef4444' : detail.status === 'INVESTIGATING' ? '#f59e0b' : '#10b981',
              }}>{detail.status.replace(/_/g,' ')}</span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              User: <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)', fontWeight: 600 }}>{detail.user_id}</span>
              &nbsp;·&nbsp;Date: {detail.date}
              &nbsp;·&nbsp;Alert ID: #{detail.id}
            </div>
          </div>
          {/* Risk gauge */}
          <div style={{ textAlign: 'center', flexShrink: 0 }}>
            <div style={{ fontSize: 42, fontWeight: 900, color: riskColor, lineHeight: 1 }}>{(detail.risk_score * 100).toFixed(0)}%</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Risk Score</div>
          </div>
        </div>

        {/* Quick action buttons */}
        <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
          {detail.status !== 'INVESTIGATING' && detail.status !== 'RESOLVED' && (
            <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => updateStatus('INVESTIGATING')}>
              <Microscope size={13} /> Mark Investigating
            </button>
          )}
          {detail.status !== 'RESOLVED' && (
            <button className="btn btn-ghost" style={{ fontSize: 12, color: '#10b981', borderColor: 'rgba(16,185,129,0.3)' }} onClick={() => updateStatus('RESOLVED')}>
              <CheckCircle size={13} /> Mark Resolved
            </button>
          )}
          {detail.status === 'OPEN' && (
            <button className="btn btn-ghost" style={{ fontSize: 12, color: '#64748b', borderColor: 'rgba(100,116,139,0.3)' }} onClick={() => updateStatus('FALSE_POSITIVE')}>
              <XCircle size={13} /> False Positive
            </button>
          )}
          <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => navigate(`/users/${detail.user_id}`)}>
            <Shield size={13} /> View User Profile
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 20 }}>
        <button style={TAB_STYLE('overview')} onClick={() => setTab('overview')}>Overview &amp; SHAP</button>
        <button style={TAB_STYLE('timeline')} onClick={() => setTab('timeline')}>Activity Timeline ({timeline.length})</button>
        <button style={TAB_STYLE('network')} onClick={() => setTab('network')}>
          <Share2 size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />Network Graph
        </button>
        <button style={TAB_STYLE('evidence')} onClick={() => setTab('evidence')}>Evidence Summary</button>
        <button style={TAB_STYLE('notes')} onClick={() => setTab('notes')}>
          <MessageSquare size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />Notes
        </button>
      </div>

      {/* OVERVIEW TAB */}
      {tab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* SHAP panel */}
          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>
              🔍 SHAP Explanation
            </h3>
            {detail.shap_json && detail.shap_json.length > 0 ? (
              detail.shap_json.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, paddingBottom: 12, borderBottom: i < detail.shap_json.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{f.friendly_name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Observed: {typeof f.value === 'number' ? f.value.toFixed(2) : f.value}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: f.direction === 'increases_risk' ? '#ef4444' : '#10b981' }}>
                      {f.direction === 'increases_risk' ? '▲' : '▼'} {Math.abs(f.shap_value).toFixed(3)}
                    </div>
                    <div style={{ width: 80, height: 4, borderRadius: 2, background: 'var(--border)', marginTop: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(100, Math.abs(f.shap_value) * 200)}%`, background: f.direction === 'increases_risk' ? '#ef4444' : '#10b981', borderRadius: 2 }} />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No SHAP data. Run the ML pipeline to generate explanations.</div>
            )}
          </div>

          {/* Daily features snapshot */}
          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>
              📊 Day-of-Alert Features
            </h3>
            {detail.daily_features ? (
              [
                ['Login Count', detail.daily_features.login_count],
                ['After-Hours Logins', detail.daily_features.after_hours_login_count],
                ['USB Connections', detail.daily_features.usb_connect_count],
                ['File Copies', detail.daily_features.file_copy_count],
                ['External Email Ratio', detail.daily_features.external_email_ratio?.toFixed(3)],
                ['File Sharing Visits', detail.daily_features.file_sharing_visit_count],
                ['Exfil Indicator', detail.daily_features.exfil_indicator?.toFixed(2)],
                ['Behavior Spike Score', detail.daily_features.behavior_spike_score?.toFixed(3)],
              ].map(([label, val]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid rgba(30,45,69,0.5)', fontSize: 13 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'var(--text-primary)' }}>{val ?? '—'}</span>
                </div>
              ))
            ) : <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No feature data for this day.</div>}

            {/* Model score breakdown */}
            {detail.risk_breakdown && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>Model Score Breakdown</div>
                {[['Isolation Forest', detail.risk_breakdown.if_score], ['Autoencoder', detail.risk_breakdown.ae_score], ['LSTM', detail.risk_breakdown.lstm_score], ['GNN', detail.risk_breakdown.gnn_score], ['Rule-Based', detail.risk_breakdown.rule_score]].map(([label, score]) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 110 }}>{label}</span>
                    <div style={{ flex: 1, height: 5, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${(score || 0) * 100}%`, background: '#3b82f6', borderRadius: 3 }} />
                    </div>
                    <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)', minWidth: 36 }}>{((score || 0) * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* NETWORK GRAPH TAB */}
      {tab === 'network' && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Share2 size={15} color="#8b5cf6" />
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Network Activity Graph</h3>
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              Force-directed graph showing relationships between <span style={{ color: '#3b82f6' }}>■ user</span>,{' '}
              <span style={{ color: '#8b5cf6' }}>■ devices</span>,{' '}
              <span style={{ color: '#ef4444' }}>■ alert types</span>, and{' '}
              <span style={{ color: '#10b981' }}>■ activity events</span>. Drag nodes to explore.
            </p>
            <div style={{ height: 380, borderRadius: 10, overflow: 'hidden', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
              <NetworkGraph
                userId={detail.user_id}
                uniquePcs={detail.daily_features?.unique_pcs ?? 2}
                alertTypes={evidence ? Object.keys(evidence.alert_type_breakdown) : [detail.alert_type]}
                eventCounts={eventCounts}
              />
            </div>
          </div>

          {/* Legend */}
          <div className="card">
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12 }}>Legend</h3>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              {[['User', '#3b82f6', 'Central identity node'], ['Device / PC', '#8b5cf6', 'Workstations accessed'], ['Alert Type', '#ef4444', 'Generated alert categories'], ['Activity Event', '#10b981', 'Top behavior event types']].map(([label, color, desc]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 12, height: 12, borderRadius: '50%', background: color, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TIMELINE TAB */}
      {tab === 'timeline' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 20 }}>
          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Event Type Summary</h3>
            <div style={{ height: 180 }}>
              {Object.keys(eventCounts).length > 0
                ? <Bar data={timelineBarData} options={BAR_OPTS} />
                : <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>No events</div>
              }
            </div>
          </div>

          <div className="card" style={{ padding: 0, maxHeight: 460, overflowY: 'auto' }}>
            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                <Clock size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />Chronological Events
              </h3>
            </div>
            {timeline.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>No timeline events found.</div>
            ) : (
              timeline.map((ev, i) => {
                const meta = EVENT_ICONS[ev.event_type] || { icon: '•', color: '#94a3b8' }
                return (
                  <div key={i} style={{ display: 'flex', gap: 12, padding: '10px 16px', borderBottom: '1px solid rgba(30,45,69,0.4)' }}>
                    <div style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>{meta.icon}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 1 }}>{ev.description}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{ev.event_date}&nbsp;·&nbsp;{ev.event_type.replace(/_/g,' ')}</div>
                    </div>
                    {ev.severity && <span className={`badge badge-${ev.severity.toLowerCase()}`} style={{ fontSize: 10 }}>{ev.severity}</span>}
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}

      {/* EVIDENCE TAB */}
      {tab === 'evidence' && evidence && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 16 }}>
              <FileText size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />Evidence Summary
            </h3>
            {[
              ['Total Alerts', evidence.total_alerts],
              ['Open Alerts', evidence.open_alerts],
              ['Peak Risk Score', `${(evidence.peak_risk_score * 100).toFixed(1)}%`],
              ['Peak Risk Date', evidence.peak_risk_date || '—'],
              ['Avg Risk (30d)', `${(evidence.avg_risk_score_30d * 100).toFixed(1)}%`],
            ].map(([label, val]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid rgba(30,45,69,0.5)', fontSize: 13 }}>
                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: 'var(--text-primary)' }}>{val}</span>
              </div>
            ))}

            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>Top Risk Factors</div>
              {evidence.top_risk_factors.slice(0, 5).map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: '#ef4444', fontWeight: 700 }}>#{i + 1}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{f.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Alert Type Breakdown</h3>
            {Object.entries(evidence.alert_type_breakdown).map(([type, count]) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <div style={{ flex: 1, fontSize: 12, color: 'var(--text-secondary)' }}>{type.replace(/_/g, ' ')}</div>
                <div style={{ width: 100, height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${(count / evidence.total_alerts) * 100}%`, background: '#3b82f6', borderRadius: 3 }} />
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', minWidth: 24 }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* NOTES TAB */}
      {tab === 'notes' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>
              <MessageSquare size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Analyst Notes
            </h3>
            {detail.notes ? (
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, padding: 12, background: 'var(--bg-secondary)', borderRadius: 8, border: '1px solid var(--border)' }}>
                {detail.notes}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No notes yet. Add one below.</div>
            )}
          </div>

          <div className="card">
            <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14 }}>Add Note</h3>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Document your findings, evidence, next steps, or resolution..."
              rows={6}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: 13, resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box', lineHeight: 1.5 }}
            />
            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={submitNote}
                disabled={saving || !note.trim()}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <Send size={13} /> {saving ? 'Saving...' : 'Save Note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
