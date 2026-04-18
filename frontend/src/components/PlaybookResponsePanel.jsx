/**
 * PlaybookResponsePanel.jsx
 * 
 * Displays the automated SOAR response actions taken for an alert.
 * Fetches from /api/soar/alerts/{alertId}/actions and renders
 * a visual response timeline with tier badges and action details.
 */

import { useEffect, useState } from 'react'

const BASE_URL = `${window.location.protocol}//${window.location.hostname}:${import.meta.env.VITE_API_PORT || 8000}`

const TIER_CONFIG = {
  1: {
    label: 'TIER 1 — MFA Step-Up',
    icon: '🔐',
    color: 'border-yellow-500/60 bg-yellow-900/20',
    badge: 'bg-yellow-700 text-yellow-200',
    tagline: 'Identity Verification Challenge Triggered',
  },
  2: {
    label: 'TIER 2 — Session Revocation',
    icon: '🔑',
    color: 'border-orange-500/60 bg-orange-900/20',
    badge: 'bg-orange-700 text-orange-200',
    tagline: 'All Active Sessions Terminated',
  },
  3: {
    label: 'TIER 3 — Host Isolation',
    icon: '🔴',
    color: 'border-red-500/60 bg-red-900/20',
    badge: 'bg-red-800 text-red-200',
    tagline: 'CRITICAL CONTAINMENT ACTIVATED',
  },
}

export default function PlaybookResponsePanel({ alertId }) {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)

  const token = sessionStorage.getItem('ueba_token')

  const fetchActions = async () => {
    if (!alertId) return
    try {
      const res = await fetch(`${BASE_URL}/api/soar/alerts/${alertId}/actions`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setActions(data)
      }
    } catch (_) {}
    finally { setLoading(false) }
  }

  const executePlaybook = async () => {
    setExecuting(true)
    try {
      const res = await fetch(`${BASE_URL}/api/soar/alerts/${alertId}/execute`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        await fetchActions()
      }
    } catch (_) {}
    finally { setExecuting(false) }
  }

  useEffect(() => { fetchActions() }, [alertId])

  return (
    <div className="bg-gray-900/60 border border-gray-700 rounded-xl p-5 mt-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <h3 className="text-sm font-bold text-white tracking-wide uppercase">
            Automated SOAR Response
          </h3>
        </div>
        {actions.length === 0 && !loading && (
          <button
            onClick={executePlaybook}
            disabled={executing}
            className="text-xs px-3 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600 text-white font-semibold transition disabled:opacity-50"
          >
            {executing ? 'Executing...' : '▶ Execute Playbook'}
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-sm text-gray-500 text-center py-4">Loading response actions...</div>
      ) : actions.length === 0 ? (
        <div className="text-center py-6">
          <div className="text-3xl mb-2 opacity-40">🛡️</div>
          <p className="text-sm text-gray-500">No automated response actions logged.</p>
          <p className="text-xs text-gray-600 mt-1">Risk score below threshold or playbook not yet executed.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {actions.map((action) => {
            const cfg = TIER_CONFIG[action.tier] || TIER_CONFIG[1]
            const ts = new Date(action.executed_at).toLocaleString()
            return (
              <div key={action.id} className={`border rounded-lg p-4 ${cfg.color}`}>
                <div className="flex items-start gap-3">
                  <span className="text-2xl flex-shrink-0">{cfg.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${cfg.badge}`}>
                        {cfg.label}
                      </span>
                      <span className="text-xs text-gray-400">{ts}</span>
                    </div>
                    <p className="text-xs font-semibold text-gray-200 mb-1">{cfg.tagline}</p>
                    <p className="text-xs text-gray-400 leading-relaxed">{action.description}</p>
                    {action.risk_score_at_trigger && (
                      <p className="text-xs text-gray-500 mt-1">
                        Triggered at risk score: {' '}
                        <span className="font-mono text-orange-400">
                          {(action.risk_score_at_trigger * 100).toFixed(1)}%
                        </span>
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}

          {/* Graduated response guide */}
          <div className="mt-4 p-3 bg-gray-800/60 rounded-lg border border-gray-700">
            <p className="text-xs text-gray-500 font-semibold mb-2 uppercase tracking-wide">Response Tiers</p>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[1, 2, 3].map(tier => {
                const cfg = TIER_CONFIG[tier]
                const active = actions.some(a => a.tier === tier)
                return (
                  <div key={tier} className={`rounded p-2 border ${active ? cfg.color : 'border-gray-700 bg-gray-900/40'}`}>
                    <div className="text-lg">{active ? cfg.icon : '○'}</div>
                    <p className={`text-xs font-semibold mt-1 ${active ? 'text-white' : 'text-gray-600'}`}>
                      Tier {tier}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
