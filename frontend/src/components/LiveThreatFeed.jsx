/**
 * LiveThreatFeed.jsx
 * 
 * Real-time auto-scrolling threat event feed for the SOC Dashboard.
 * Displays incoming alerts from the WebSocket stream with severity
 * color coding, SOAR tier badges, and animated entry effects.
 */

import { useEffect, useRef } from 'react'

const SEVERITY_CONFIG = {
  CRITICAL: { bg: 'bg-red-500/20',   border: 'border-red-500/60',   text: 'text-red-400',   dot: 'bg-red-500',   badge: 'bg-red-600' },
  HIGH:     { bg: 'bg-orange-500/20', border: 'border-orange-500/60', text: 'text-orange-400', dot: 'bg-orange-500', badge: 'bg-orange-600' },
  MEDIUM:   { bg: 'bg-yellow-500/20', border: 'border-yellow-500/60', text: 'text-yellow-400', dot: 'bg-yellow-500', badge: 'bg-yellow-600' },
  LOW:      { bg: 'bg-blue-500/20',   border: 'border-blue-500/60',   text: 'text-blue-400',   dot: 'bg-blue-400',  badge: 'bg-blue-600' },
}

const SOAR_BADGE = {
  1: { label: 'MFA Triggered',   color: 'bg-yellow-700 text-yellow-200' },
  2: { label: 'Session Revoked', color: 'bg-orange-700 text-orange-200' },
  3: { label: '🔴 Host Isolated', color: 'bg-red-800 text-red-200' },
}

const ALERT_TYPE_ICONS = {
  DATA_EXFILTRATION:   '📤',
  PRIVILEGE_ABUSE:     '🔓',
  SUSPICIOUS_LOGIN:    '🔑',
  MASS_DATA_DOWNLOAD:  '📥',
  POTENTIAL_SABOTAGE:  '💥',
  IMPOSSIBLE_TRAVEL:   '🌍',
  BRUTE_FORCE:         '🔒',
}

function FeedEntry({ alert, isNew }) {
  const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.MEDIUM
  const icon = ALERT_TYPE_ICONS[alert.alert_type] || '⚠️'
  const soarInfo = alert.soar_tier ? SOAR_BADGE[alert.soar_tier] : null
  const ts = new Date().toLocaleTimeString()

  return (
    <div className={`
      feed-entry rounded-lg border p-3 mb-2 transition-all duration-500
      ${cfg.bg} ${cfg.border}
      ${isNew ? 'animate-pulse-once' : ''}
    `}>
      <div className="flex items-start gap-2">
        <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${cfg.dot} ${isNew ? 'animate-ping-once' : ''}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm">{icon}</span>
            <span className={`text-xs font-bold ${cfg.text}`}>
              {alert.alert_type?.replace(/_/g, ' ')}
            </span>
            <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${cfg.badge} text-white`}>
              {alert.severity}
            </span>
            {soarInfo && (
              <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ${soarInfo.color}`}>
                {soarInfo.label}
              </span>
            )}
            <span className="text-xs text-gray-500 ml-auto">{ts}</span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5 truncate">
            <span className="text-gray-300 font-medium">{alert.user_id}</span>
            {' · '}{alert.description || 'Threat detected'}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <div className="flex-1 bg-gray-700 rounded-full h-1">
              <div
                className={`h-1 rounded-full ${cfg.dot}`}
                style={{ width: `${(alert.risk_score || 0) * 100}%` }}
              />
            </div>
            <span className={`text-xs font-mono font-bold ${cfg.text}`}>
              {((alert.risk_score || 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function LiveThreatFeed({ alertQueue, isConnected }) {
  const feedRef = useRef(null)

  // Auto-scroll to top when new alert arrives
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0
    }
  }, [alertQueue])

  return (
    <div className="bg-gray-900/80 border border-gray-700 rounded-xl overflow-hidden flex flex-col" style={{ height: '420px' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-800/60">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`} />
          <span className="text-sm font-semibold text-white">Live Threat Feed</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            isConnected
              ? 'bg-green-900/60 text-green-400 border border-green-700'
              : 'bg-red-900/60 text-red-400 border border-red-700'
          }`}>
            {isConnected ? 'LIVE' : 'RECONNECTING...'}
          </span>
          <span className="text-xs text-gray-500">{alertQueue.length} events</span>
        </div>
      </div>

      {/* Feed */}
      <div ref={feedRef} className="flex-1 overflow-y-auto p-3 space-y-1 scrollbar-thin">
        {alertQueue.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <div className="text-4xl mb-3 opacity-30">🛡️</div>
            <p className="text-sm">Monitoring for threats...</p>
            <p className="text-xs mt-1 opacity-60">
              {isConnected ? 'Awaiting activity' : 'Connecting to feed...'}
            </p>
          </div>
        ) : (
          alertQueue.map((alert, idx) => (
            <FeedEntry key={`${alert.alert_id}-${idx}`} alert={alert} isNew={idx === 0} />
          ))
        )}
      </div>
    </div>
  )
}
