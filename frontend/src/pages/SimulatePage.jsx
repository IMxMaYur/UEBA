import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap, CheckCircle, AlertTriangle, Play, Lock, Database, ExternalLink, Cpu } from 'lucide-react'
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
]

function ResultCard({ result, color, onViewUser }) {
  if (!result) return null
  if (!result.success) return (
    <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
      <div style={{ fontSize: 12, color: '#ef4444' }}>⚠ {result.error}</div>
    </div>
  )

  const isCert = result.data?.mode === 'cert_dataset'
  const d = result.data

  return (
    <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 8, background: isCert ? 'rgba(16,185,129,0.06)' : 'rgba(16,185,129,0.08)', border: `1px solid ${isCert ? 'rgba(16,185,129,0.4)' : 'rgba(16,185,129,0.25)'}` }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        {isCert ? <Database size={14} color="#10b981" style={{ flexShrink: 0, marginTop: 1 }} /> : <CheckCircle size={14} color="#10b981" style={{ flexShrink: 0, marginTop: 1 }} />}
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#10b981', marginBottom: 4 }}>
            {isCert ? '🔬 Real CERT User Detected by ML Models' : 'Simulation triggered successfully'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>
            User: <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-secondary)' }}>{d.user_id}</span>
            &nbsp;·&nbsp;Risk: <span style={{ fontWeight: 700, color: '#f59e0b' }}>{(d.risk_score * 100).toFixed(0)}%</span>
            {d.date && <>&nbsp;·&nbsp;Date: {d.date}</>}
          </div>
          {/* Model scores for CERT detections */}
          {isCert && d.model_scores && (
            <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {[
                ['IF', d.model_scores.if_score],
                ['AE', d.model_scores.ae_score],
                ['LSTM', d.model_scores.lstm_score],
                ['GNN', d.model_scores.gnn_score],
              ].map(([label, score]) => (
                <div key={label} style={{ padding: '3px 8px', borderRadius: 4, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.2)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{label} </span>
                  <span style={{ color: '#10b981', fontWeight: 700 }}>{((score || 0) * 100).toFixed(0)}%</span>
                </div>
              ))}
              {d.shap_count > 0 && (
                <span style={{ fontSize: 10, color: '#10b981', padding: '3px 8px', borderRadius: 4, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.2)' }}>
                  🔍 {d.shap_count} SHAP features
                </span>
              )}
            </div>
          )}
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            {isCert
              ? <span>Navigate to <strong>Alerts</strong> to investigate, or <button onClick={onViewUser} style={{ background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', fontSize: 11, padding: 0, textDecoration: 'underline' }}>view user profile <ExternalLink size={10} style={{ verticalAlign: 'middle' }} /></button></span>
              : <>Check <strong>Alerts</strong> to see the generated alert.</>
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
  const [progress, setProgress] = useState({}) // scenario_mode -> 0-100
  const { isAdmin } = useAuth()
  const navigate    = useNavigate()

  const setLoad = (id, mode, val) => setLoading(l => ({ ...l, [`${id}_${mode}`]: val }))
  const isLoad  = (id, mode) => loading[`${id}_${mode}`]

  const trigger = async (scenarioId, mode = 'synthetic') => {
    const key = `${scenarioId}_${mode}`
    setLoad(scenarioId, mode, true)
    setResults(r => ({ ...r, [key]: null }))

    // For CERT detect: simulate progressive loading (the real call takes a few seconds)
    let pct = 0
    let progressInterval = null
    if (mode === 'cert') {
      setProgress(p => ({ ...p, [key]: 0 }))
      progressInterval = setInterval(() => {
        pct = Math.min(pct + Math.random() * 12, 90)
        setProgress(p => ({ ...p, [key]: Math.round(pct) }))
      }, 300)
    }

    try {
      const url = mode === 'cert' ? `/simulate/${scenarioId}/detect` : `/simulate/${scenarioId}`
      const { data } = await api.post(url)
      if (progressInterval) { clearInterval(progressInterval); setProgress(p => ({ ...p, [key]: 100 })) }
      setResults(r => ({ ...r, [key]: { success: true, data } }))
    } catch (err) {
      if (progressInterval) { clearInterval(progressInterval); setProgress(p => ({ ...p, [key]: 0 })) }
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

              {/* CERT detect with progress bar */}
              {progress[`${scenario.id}_cert`] !== undefined && isLoad(scenario.id, 'cert') && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
                    <span>Running ML models on CERT dataset…</span>
                    <span>{progress[`${scenario.id}_cert`]}%</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${progress[`${scenario.id}_cert`]}%`, background: '#10b981', borderRadius: 2, transition: 'width 0.3s' }} />
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>IF → AE → LSTM → GNN → scoring…</div>
                </div>
              )}

              {/* Results */}
              <ResultCard
                result={synthResult}
                color={scenario.color}
                onViewUser={() => synthResult?.data?.user_id && navigate(`/app/users/${synthResult.data.user_id}`)}
              />
              <ResultCard
                result={certResult}
                color="#10b981"
                onViewUser={() => certResult?.data?.user_id && navigate(`/app/users/${certResult.data.user_id}`)}
              />

            </div>
          )
        })}
      </div>
    </div>
  )
}
