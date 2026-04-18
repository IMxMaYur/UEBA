import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap, CheckCircle, Play, Lock, Database, ExternalLink } from 'lucide-react'
import api from '../api'
import { useAuth } from '../useAuth'

const SCENARIOS = [
  {
    id: 'data_exfiltration',
    title: 'Data Exfiltration',
    icon: '💾',
    description: 'Late-night login followed by mass USB file copy (85+ files)',
    severity: 'CRITICAL',
    expectedAlert: 'DATA_EXFILTRATION',
    color: '#ef4444',
    behaviors: ['After-hours login', 'Mass file copy', 'USB device usage', 'High exfiltration indicator'],
  },
  {
    id: 'privilege_abuse',
    title: 'Privilege Abuse',
    icon: '🔑',
    description: 'Employee accesses restricted servers and downloads confidential files',
    severity: 'HIGH',
    expectedAlert: 'PRIVILEGE_ABUSE',
    color: '#f59e0b',
    behaviors: ['Unusual server access', 'Sensitive file download', '7+ unique PCs logged'],
  },
  {
    id: 'credential_compromise',
    title: 'Credential Compromise',
    icon: '🔓',
    description: 'Account logged in from a new device and rapidly accesses multiple systems',
    severity: 'HIGH',
    expectedAlert: 'SUSPICIOUS_LOGIN',
    color: '#f59e0b',
    behaviors: ['New device login', 'Multiple system access', '15+ login events', 'High HTTP activity'],
  },
  {
    id: 'mass_download',
    title: 'Mass Data Download',
    icon: '📥',
    description: 'Unusual spike in file access and data transfer compared to normal behavior',
    severity: 'HIGH',
    expectedAlert: 'MASS_DATA_DOWNLOAD',
    color: '#8b5cf6',
    behaviors: ['120+ file copies', '500+ HTTP requests', '8 file-sharing visits', 'High exfil indicator'],
  },
  {
    id: 'sabotage',
    title: 'Insider Sabotage',
    icon: '💥',
    description: 'Employee accesses production systems and deletes or modifies critical files',
    severity: 'CRITICAL',
    expectedAlert: 'POTENTIAL_SABOTAGE',
    color: '#ef4444',
    behaviors: ['Production server access', 'File deletion/modification', 'Config changes', 'After-hours activity'],
  },
  {
    id: 'impossible_travel',
    title: 'Impossible Travel',
    icon: '🌍',
    description: 'Two logins from geographically impossible locations within minutes — credential theft indicator',
    severity: 'CRITICAL',
    expectedAlert: 'IMPOSSIBLE_TRAVEL',
    color: '#06b6d4',
    behaviors: ['Mumbai login → New York in 45min', 'Geographic impossibility', 'Different country login', 'Credential theft indicator'],
  },
  {
    id: 'brute_force',
    title: 'Brute Force Attack',
    icon: '🔒',
    description: '47 failed login attempts in 3 minutes from a Tor exit node — automated credential attack detected',
    severity: 'CRITICAL',
    expectedAlert: 'BRUTE_FORCE',
    color: '#8b5cf6',
    behaviors: ['47 failed logins in 3min', 'Tor exit node source', 'Known malicious IP', 'IP blocked at edge firewall'],
  },
]

function ResultCard({ result, color, onViewUser }) {
  if (!result) return null
  if (!result.success) return (
    <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
      <div style={{ fontSize: 12, color: '#ef4444' }}>⚠ {result.error}</div>
    </div>
  )

  const isCert   = result.data?.mode === 'cert_dataset'
  const d        = result.data
  const soarTier = d?.soar_response?.tier

  const SOAR_BADGE = {
    1: { label: 'MFA Triggered',    color: '#f59e0b' },
    2: { label: 'Session Revoked',  color: '#f97316' },
    3: { label: '🔴 Host Isolated', color: '#ef4444' },
  }

  const MEDAL = ['🥇', '🥈', '🥉']

  const riskBar = (score) => {
    const pct = Math.round(score * 100)
    const c   = score >= 0.75 ? '#ef4444' : score >= 0.5 ? '#f59e0b' : '#10b981'
    return (
      <div style={{ flex: 1, height: 5, borderRadius: 3, background: 'rgba(255,255,255,0.07)', overflow: 'hidden', margin: '0 8px' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg, ${c}88, ${c})`, borderRadius: 3, transition: 'width 0.5s ease' }} />
      </div>
    )
  }

  return (
    <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 8, background: isCert ? 'rgba(16,185,129,0.06)' : 'rgba(16,185,129,0.08)', border: `1px solid ${isCert ? 'rgba(16,185,129,0.4)' : 'rgba(16,185,129,0.25)'}` }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        {isCert ? <Database size={14} color="#10b981" style={{ flexShrink: 0, marginTop: 1 }} /> : <CheckCircle size={14} color="#10b981" style={{ flexShrink: 0, marginTop: 1 }} />}
        <div style={{ flex: 1 }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>
              {isCert
                ? `🔬 Top ${d.top_users?.length || 1} CERT Insider Threats Detected`
                : 'Simulation triggered successfully'}
            </span>
            {soarTier && (
              <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 12, background: `${SOAR_BADGE[soarTier]?.color}25`, color: SOAR_BADGE[soarTier]?.color, border: `1px solid ${SOAR_BADGE[soarTier]?.color}50` }}>
                SOAR: {SOAR_BADGE[soarTier]?.label}
              </span>
            )}
          </div>

          {/* Non-CERT single result */}
          {!isCert && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>
              User: <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>{d.user_id}</span>
              &nbsp;·&nbsp;Risk: <span style={{ fontWeight: 700, color: '#f59e0b' }}>{(d.risk_score * 100).toFixed(0)}%</span>
              {d.date && <>&nbsp;·&nbsp;{d.date}</>}
            </div>
          )}

          {/* CERT top user (primary) */}
          {isCert && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 4 }}>
              🥇 <strong style={{ color: 'var(--text-secondary)' }}>{d.user_id}</strong>
              &nbsp;·&nbsp;Risk: <span style={{ fontWeight: 700, color: '#f59e0b' }}>{(d.risk_score * 100).toFixed(0)}%</span>
              {d.date && <>&nbsp;·&nbsp;{d.date}</>}
            </div>
          )}

          {/* Narrative */}
          {d.narrative && (
            <div style={{ margin: '8px 0', padding: '8px 10px', borderRadius: 6, background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.2)', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              🤖 {d.narrative.slice(0, 180)}{d.narrative.length > 180 ? '...' : ''}
            </div>
          )}

          {/* Top-5 ranking bars — CERT only */}
          {isCert && d.top_users && d.top_users.length > 1 && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(16,185,129,0.15)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>
                Risk Ranking
              </div>
              {d.top_users.map((u, i) => {
                const pct   = Math.round(u.risk_score * 100)
                const rc    = u.risk_score >= 0.75 ? '#ef4444' : u.risk_score >= 0.5 ? '#f59e0b' : '#10b981'
                const medal = i < 3 ? MEDAL[i] : `#${i + 1}`
                const isTop = i === 0
                return (
                  <div key={u.user_id} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: isTop ? '5px 8px' : '3px 4px',
                    marginBottom: 4, borderRadius: 6,
                    background: isTop ? `${rc}12` : 'transparent',
                    border: isTop ? `1px solid ${rc}30` : 'none',
                  }}>
                    <span style={{ minWidth: 22, fontSize: isTop ? 13 : 11, textAlign: 'center' }}>{medal}</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: isTop ? 'var(--text-primary)' : 'var(--text-secondary)', flex: 1, fontWeight: isTop ? 700 : 400 }}>
                      {u.user_id}
                    </span>
                    {riskBar(u.risk_score)}
                    <span style={{ fontWeight: 700, fontSize: 11, color: rc, minWidth: 32, textAlign: 'right' }}>
                      {pct}%
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Footer nav */}
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            {isCert
              ? <span>Navigate to <strong>Alerts</strong> to investigate, or <button onClick={onViewUser} style={{ background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', fontSize: 11, padding: 0, textDecoration: 'underline' }}>view user profile <ExternalLink size={10} style={{ verticalAlign: 'middle' }} /></button></span>
              : <>Check <strong>Incidents</strong> to see the generated alert and SOAR response.</>
            }
          </div>
        </div>
      </div>
    </div>
  )
}


export default function SimulatePage() {
  const [results, setResults]   = useState({})
  const [loading, setLoading]   = useState({})
  const { isAdmin } = useAuth()
  const navigate    = useNavigate()

  const setLoad = (id, mode, val) => setLoading(l => ({ ...l, [`${id}_${mode}`]: val }))
  const isLoad  = (id, mode) => loading[`${id}_${mode}`]

  const trigger = async (scenarioId, mode = 'synthetic') => {
    const key = `${scenarioId}_${mode}`
    setLoad(scenarioId, mode, true)
    setResults(r => ({ ...r, [key]: null }))
    try {
      const url = mode === 'cert' ? `/simulate/${scenarioId}/detect` : `/simulate/${scenarioId}`
      const { data } = await api.post(url)
      setResults(r => ({ ...r, [key]: { success: true, data } }))
    } catch (err) {
      setResults(r => ({ ...r, [key]: { success: false, error: err.response?.data?.detail || 'Failed' } }))
    } finally {
      setLoad(scenarioId, mode, false)
    }
  }

  if (!isAdmin) {
    return (
      <div className="animate-in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 64, height: 64, borderRadius: 16, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', marginBottom: 20 }}>
            <Lock size={28} color="#ef4444" />
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Admin Access Required</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, maxWidth: 360 }}>
            Attack scenario simulation is restricted to admin users only.<br />
            Log in with <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#3b82f6' }}>admin@ueba.local</span> to access this page.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-in" style={{ maxWidth: 960 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <Zap size={20} color="#f59e0b" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Attack Scenario Simulator</h1>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Inject synthetic data or run real ML detection on the CERT insider threat dataset.
        </p>
      </div>




      {/* Mode info */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
        <div style={{ padding: '12px 16px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 10, fontSize: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Play size={14} color="#3b82f6" />
            <strong style={{ color: '#3b82f6' }}>Synthetic Simulation</strong>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Creates a fake user with hardcoded extreme feature values. Instant results, no dataset needed.</div>
        </div>
        <div style={{ padding: '12px 16px', background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 10, fontSize: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Database size={14} color="#10b981" />
            <strong style={{ color: '#10b981' }}>CERT Dataset Detection</strong>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loads real CERT employee logs, runs all 4 trained ML models, finds the most anomalous real user. Requires trained models.</div>
        </div>
      </div>

      {/* Scenario cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16 }}>
        {SCENARIOS.map(scenario => {
          const synthResult = results[`${scenario.id}_synthetic`]
          const certResult  = results[`${scenario.id}_cert`]

          return (
            <div key={scenario.id} className="card" style={{ borderLeft: `3px solid ${scenario.color}` }}>
              {/* Card header */}
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 24 }}>{scenario.icon}</span>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 2 }}>{scenario.title}</div>
                    <span className={`badge badge-${scenario.severity.toLowerCase()}`}>{scenario.severity}</span>
                  </div>
                </div>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, padding: '3px 8px', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
                  {scenario.expectedAlert}
                </span>
              </div>

              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>{scenario.description}</p>

              {/* Behavior tags */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 16 }}>
                {scenario.behaviors.map((b, i) => (
                  <span key={i} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, background: `${scenario.color}15`, color: scenario.color, border: `1px solid ${scenario.color}30` }}>{b}</span>
                ))}
              </div>

              {/* Two buttons */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {/* Synthetic */}
                <button
                  className="btn btn-primary"
                  onClick={() => trigger(scenario.id, 'synthetic')}
                  disabled={isLoad(scenario.id, 'synthetic')}
                  style={{ justifyContent: 'center', background: isLoad(scenario.id, 'synthetic') ? 'var(--border)' : scenario.color, opacity: isLoad(scenario.id, 'synthetic') ? 0.7 : 1, fontSize: 12 }}
                >
                  {isLoad(scenario.id, 'synthetic')
                    ? <><span style={{ animation: 'spin 1s linear infinite' }}>⟳</span> Running...</>
                    : <><Play size={12} /> Synthetic</>
                  }
                </button>

                {/* CERT real detection */}
                <button
                  className="btn btn-ghost"
                  onClick={() => trigger(scenario.id, 'cert')}
                  disabled={isLoad(scenario.id, 'cert')}
                  style={{ justifyContent: 'center', color: '#10b981', borderColor: 'rgba(16,185,129,0.4)', fontSize: 12 }}
                >
                  {isLoad(scenario.id, 'cert')
                    ? <><span style={{ animation: 'spin 1s linear infinite' }}>⟳</span> Detecting...</>
                    : <><Database size={12} /> CERT Detect</>
                  }
                </button>
              </div>

              {/* Results */}
              <ResultCard
                result={synthResult}
                color={scenario.color}
                onViewUser={() => synthResult?.data?.user_id && navigate(`/users/${synthResult.data.user_id}`)}
              />
              <ResultCard
                result={certResult}
                color="#10b981"
                onViewUser={() => certResult?.data?.user_id && navigate(`/users/${certResult.data.user_id}`)}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
