/**
 * KPICard – reusable metric card for the security dashboard.
 * Props: icon, label, value, sub, color, pulse, trend, trendLabel
 */
export default function KPICard({ icon: Icon, label, value, sub, color = '#3b82f6', pulse = false, trend, trendLabel }) {
  const trendColor = trend > 0 ? '#ef4444' : trend < 0 ? '#10b981' : '#475569'
  const trendArrow = trend > 0 ? '▲' : trend < 0 ? '▼' : '—'

  return (
    <div className={`card ${pulse ? 'pulse-critical' : ''}`}
      style={{ display: 'flex', flexDirection: 'column', gap: 12, position: 'relative', overflow: 'hidden' }}>
      {/* top accent line */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${color}, transparent)` }} />

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ padding: 10, borderRadius: 10, background: `${color}20` }}>
          <Icon size={20} color={color} />
        </div>
        {trend !== undefined && (
          <span style={{ fontSize: 11, fontWeight: 700, color: trendColor }}>
            {trendArrow} {Math.abs(trend)}{trendLabel || ''}
          </span>
        )}
      </div>

      <div>
        <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.1 }}>{value}</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginTop: 4 }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  )
}
