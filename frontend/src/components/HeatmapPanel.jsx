import { useMemo } from 'react'

const RISK_COLORS = [
  { max: 0.30, bg: 'rgba(16,185,129,0.15)',  border: 'rgba(16,185,129,0.4)',  text: '#10b981', label: 'Normal'   },
  { max: 0.60, bg: 'rgba(59,130,246,0.15)',  border: 'rgba(59,130,246,0.4)',  text: '#3b82f6', label: 'Low'      },
  { max: 0.75, bg: 'rgba(245,158,11,0.15)',  border: 'rgba(245,158,11,0.4)',  text: '#f59e0b', label: 'Medium'   },
  { max: 0.90, bg: 'rgba(249,115,22,0.2)',   border: 'rgba(249,115,22,0.5)',  text: '#f97316', label: 'High'     },
  { max: 1.01, bg: 'rgba(239,68,68,0.20)',   border: 'rgba(239,68,68,0.5)',   text: '#ef4444', label: 'Critical' },
]

function getRiskColor(score) {
  return RISK_COLORS.find(r => score < r.max) || RISK_COLORS[RISK_COLORS.length - 1]
}

/**
 * HeatmapPanel – visualizes risk aggregated by department.
 * Props: users (array of { user_id, department, risk_score })
 */
export default function HeatmapPanel({ users = [] }) {
  const departments = useMemo(() => {
    const map = {}
    users.forEach(u => {
      const dept = u.department || 'Unknown'
      if (!map[dept]) map[dept] = { scores: [], anomaly_count: 0 }
      map[dept].scores.push(u.risk_score)
      if (u.risk_score >= 0.65) map[dept].anomaly_count++
    })
    return Object.entries(map)
      .map(([dept, v]) => ({
        dept,
        avg: v.scores.reduce((a, b) => a + b, 0) / v.scores.length,
        max: Math.max(...v.scores),
        count: v.scores.length,
        anomaly_count: v.anomaly_count,
      }))
      .sort((a, b) => b.avg - a.avg)
  }, [users])

  if (departments.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>
        No department data available.
      </div>
    )
  }

  return (
    <div>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        {RISK_COLORS.map(r => (
          <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 12, height: 12, borderRadius: 3, background: r.bg, border: `1px solid ${r.border}` }} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.label}</span>
          </div>
        ))}
      </div>

      {/* Heatmap grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 10 }}>
        {departments.map(({ dept, avg, max, count, anomaly_count }) => {
          const c = getRiskColor(avg)
          return (
            <div key={dept} style={{
              padding: '14px 16px', borderRadius: 10,
              background: c.bg, border: `1px solid ${c.border}`,
              transition: 'transform 0.15s, box-shadow 0.15s',
            }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = `0 6px 20px ${c.border}` }}
              onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '' }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{dept}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: c.text }}>{(avg * 100).toFixed(0)}%</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>Avg Risk · {count} users</div>
              <div style={{ fontSize: 10, color: c.text, marginTop: 2, fontWeight: 600 }}>
                {anomaly_count} anomalous · Max {(max * 100).toFixed(0)}%
              </div>
              {/* mini bar */}
              <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.08)', marginTop: 8, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${avg * 100}%`, background: c.text, borderRadius: 2 }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
