import { LogIn, FileText, Usb, Globe, Mail, AlertTriangle, Shield } from 'lucide-react'

const EVENT_ICONS = {
  LOGIN: LogIn,
  FILE_ACCESS: FileText,
  USB_CONNECT: Usb,
  USB_COPY: Usb,
  WEB_VISIT: Globe,
  EMAIL_SEND: Mail,
  ALERT: AlertTriangle,
  default: Shield,
}

const SEV_COLORS = {
  CRITICAL: '#ef4444',
  HIGH:     '#f59e0b',
  MEDIUM:   '#3b82f6',
  LOW:      '#10b981',
  NORMAL:   '#475569',
}

function getSevColor(score) {
  if (score >= 0.9) return SEV_COLORS.CRITICAL
  if (score >= 0.75) return SEV_COLORS.HIGH
  if (score >= 0.6) return SEV_COLORS.MEDIUM
  if (score >= 0.3) return SEV_COLORS.LOW
  return SEV_COLORS.NORMAL
}

function formatTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
  catch { return ts }
}

function formatDate(ts) {
  if (!ts) return ''
  try { return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' }) }
  catch { return '' }
}

/**
 * TimelineViewer – interactive chronological timeline of security events.
 * Props: events (array), title (string)
 *
 * Event shape: { id, timestamp, event_type, description, severity_score, resource, details }
 */
export default function TimelineViewer({ events = [], title = 'Activity Timeline' }) {
  if (events.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>
        No activity events to display.
      </div>
    )
  }

  // Group by date
  const grouped = {}
  events.forEach(ev => {
    const date = formatDate(ev.timestamp)
    if (!grouped[date]) grouped[date] = []
    grouped[date].push(ev)
  })

  return (
    <div>
      {Object.entries(grouped).map(([date, dayEvents]) => (
        <div key={date} style={{ marginBottom: 24 }}>
          {/* Date header */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16,
          }}>
            <div style={{ height: 1, flex: '0 0 40px', background: 'var(--border)' }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
              {date}
            </span>
            <div style={{ height: 1, flex: 1, background: 'var(--border)' }} />
          </div>

          {/* Events */}
          <div style={{ position: 'relative', paddingLeft: 24 }}>
            {/* Vertical line */}
            <div style={{ position: 'absolute', left: 15, top: 0, bottom: 0, width: 2, background: 'var(--border)' }} />

            {dayEvents.map((ev, idx) => {
              const Icon = EVENT_ICONS[ev.event_type] || EVENT_ICONS.default
              const color = getSevColor(ev.severity_score || 0)
              return (
                <div key={ev.id || idx} style={{ position: 'relative', marginBottom: 14, paddingLeft: 28 }}>
                  {/* Dot on line */}
                  <div style={{
                    position: 'absolute', left: -1, top: 8,
                    width: 12, height: 12, borderRadius: '50%',
                    background: color, border: '2px solid var(--bg-card)',
                    boxShadow: `0 0 6px ${color}66`,
                  }} />

                  <div style={{
                    padding: '10px 14px', borderRadius: 10,
                    background: 'var(--bg-secondary)',
                    border: `1px solid ${color}30`,
                    transition: 'border-color 0.15s, background 0.15s',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = color; e.currentTarget.style.background = 'var(--bg-card-hover)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = `${color}30`; e.currentTarget.style.background = 'var(--bg-secondary)' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Icon size={13} color={color} />
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                          {ev.event_type?.replace(/_/g, ' ') || 'Unknown Event'}
                        </span>
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>
                        {formatTime(ev.timestamp)}
                      </span>
                    </div>

                    {ev.description && (
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: ev.resource ? 4 : 0 }}>
                        {ev.description}
                      </div>
                    )}

                    {ev.resource && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
                        {ev.resource}
                      </div>
                    )}

                    {ev.severity_score > 0 && (
                      <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ height: 3, flex: 1, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${(ev.severity_score || 0) * 100}%`, background: color, borderRadius: 2 }} />
                        </div>
                        <span style={{ fontSize: 10, color, fontWeight: 700, minWidth: 32, textAlign: 'right' }}>
                          {((ev.severity_score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
