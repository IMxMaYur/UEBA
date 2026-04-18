import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ForceGraph2D from 'react-force-graph-2d'
import { GitBranch, User, Monitor, Usb, Globe, ArrowLeft, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react'
import api from '../api'

// ─── Node styling ────────────────────────────────────────────────────────────
const NODE_COLORS = {
  user:    '#8b5cf6',
  pc:      '#3b82f6',
  usb:     '#f59e0b',
  ip:      '#ef4444',
  email:   '#10b981',
  default: '#6b7280',
}
const NODE_ICONS = { user: '👤', pc: '🖥️', usb: '💾', ip: '🌐', email: '📧' }

function buildGraphFromData(data) {
  const nodes = []
  const links = []
  const nodeSet = new Set()

  const addNode = (id, type, label, risk = 0) => {
    if (!nodeSet.has(id)) {
      nodeSet.add(id)
      nodes.push({ id, type, label, risk, color: NODE_COLORS[type] || NODE_COLORS.default })
    }
  }

  // Central user node
  addNode(data.user_id, 'user', data.user_name || data.user_id, data.risk_score || 0)

  // PCs accessed
  ;(data.pcs || []).forEach(pc => {
    addNode(pc.id, 'pc', pc.id, 0)
    links.push({ source: data.user_id, target: pc.id, label: `${pc.logon_count} logons` })
  })

  // USB devices
  ;(data.usb_devices || []).forEach((usb, i) => {
    const uid = `USB-${i}`
    addNode(uid, 'usb', uid, 0)
    links.push({ source: data.user_id, target: uid, label: 'USB connected' })
  })

  // External email recipients
  ;(data.external_emails || []).slice(0, 8).forEach((addr, i) => {
    const uid = `EMAIL-${i}`
    addNode(uid, 'email', addr.length > 20 ? addr.slice(0, 18) + '…' : addr, 0)
    links.push({ source: data.user_id, target: uid, label: 'emailed' })
  })

  // External IPs from the logon dataset (augmented)
  ;(data.external_ips || []).forEach((ip, i) => {
    const uid = `IP-${i}`
    addNode(uid, 'ip', ip, 0.9)
    links.push({ source: data.user_id, target: uid, label: 'login from', color: '#ef4444' })
  })

  return { nodes, links }
}

export default function KnowledgeGraphPage() {
  const { userId } = useParams()
  const navigate   = useNavigate()
  const fgRef      = useRef()

  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [rawData, setRawData]     = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [alertId, setAlertId]     = useState(null)

  // Read optional alert_id from query params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    setAlertId(params.get('alert_id'))
  }, [])

  const loadGraph = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const endpoint = alertId
        ? `/investigation/graph?alert_id=${alertId}`
        : `/investigation/graph?user_id=${userId}`
      const { data } = await api.get(endpoint)
      setRawData(data)
      setGraphData(buildGraphFromData(data))
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load graph data')
    } finally {
      setLoading(false)
    }
  }, [userId, alertId])

  useEffect(() => { loadGraph() }, [loadGraph])

  // Custom node painting
  const paintNode = useCallback((node, ctx, globalScale) => {
    const size    = node.type === 'user' ? 10 : 6
    const label   = node.label || node.id
    const fontSize = Math.max(10 / globalScale, 2)

    // Glow for high-risk nodes
    if (node.risk > 0.6) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI)
      ctx.fillStyle = node.risk > 0.8 ? 'rgba(239,68,68,0.25)' : 'rgba(245,158,11,0.25)'
      ctx.fill()
    }

    // Node circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI)
    ctx.fillStyle = node.color || '#6b7280'
    ctx.fill()
    ctx.strokeStyle = hoveredNode?.id === node.id ? '#fff' : 'rgba(255,255,255,0.3)'
    ctx.lineWidth = hoveredNode?.id === node.id ? 2 / globalScale : 0.5 / globalScale
    ctx.stroke()

    // Label
    ctx.font = `${fontSize}px Inter, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    const shortLabel = label.length > 14 ? label.slice(0, 12) + '…' : label
    ctx.fillText(shortLabel, node.x, node.y + size + 2 / globalScale)
  }, [hoveredNode])

  const paintLink = useCallback((link, ctx) => {
    ctx.strokeStyle = link.color || 'rgba(139,92,246,0.4)'
    ctx.lineWidth = 1.2
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '70vh', flexDirection: 'column', gap: 16 }}>
      <div style={{ width: 48, height: 48, border: '3px solid var(--border)', borderTopColor: '#8b5cf6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
      <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>Building knowledge graph…</span>
    </div>
  )

  if (error) return (
    <div style={{ padding: 32, textAlign: 'center' }}>
      <div style={{ color: '#ef4444', marginBottom: 12 }}>⚠ {error}</div>
      <button className="btn btn-ghost" onClick={() => navigate(-1)}>← Back</button>
    </div>
  )

  return (
    <div className="animate-in" style={{ height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column', gap: 0 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 0 16px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost" style={{ padding: '6px 10px' }} onClick={() => navigate(-1)}>
            <ArrowLeft size={16} />
          </button>
          <GitBranch size={20} color="#8b5cf6" />
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>Insider Threat Knowledge Graph</h1>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {rawData?.user_id} · {graphData.nodes.length} entities · {graphData.links.length} connections
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => fgRef.current?.zoomToFit(400)}>
            <ZoomIn size={14} /> Fit
          </button>
          <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={loadGraph}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexShrink: 0, flexWrap: 'wrap' }}>
        {Object.entries(NODE_ICONS).map(([type, icon]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-muted)' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: NODE_COLORS[type], display: 'inline-block' }} />
            {icon} {type.charAt(0).toUpperCase() + type.slice(1)}
          </div>
        ))}
        <div style={{ marginLeft: 'auto', fontSize: 12, color: '#ef4444', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: 'rgba(239,68,68,0.4)', boxShadow: '0 0 8px #ef4444', display: 'inline-block' }} />
          Glow = High Risk
        </div>
      </div>

      {/* Graph canvas */}
      <div style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden', background: 'var(--bg-secondary)', position: 'relative' }}>
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeCanvasObject={paintNode}
          linkCanvasObject={paintLink}
          linkLabel="label"
          onNodeHover={setHoveredNode}
          onNodeClick={setSelectedNode}
          nodeRelSize={6}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          cooldownTicks={100}
          backgroundColor="transparent"
          width={undefined}
          height={undefined}
        />

        {/* Selected node info panel */}
        {selectedNode && (
          <div style={{
            position: 'absolute', top: 12, right: 12,
            background: 'var(--bg-primary)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '12px 16px', minWidth: 200, zIndex: 10,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 13 }}>{NODE_ICONS[selectedNode.type]} {selectedNode.type.toUpperCase()}</span>
              <button onClick={() => setSelectedNode(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>✕</button>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>{selectedNode.id}</div>
            {selectedNode.risk > 0 && (
              <div style={{ marginTop: 8, fontSize: 12 }}>
                Risk: <span style={{ fontWeight: 700, color: selectedNode.risk > 0.7 ? '#ef4444' : '#f59e0b' }}>
                  {Math.round(selectedNode.risk * 100)}%
                </span>
              </div>
            )}
            {selectedNode.type === 'user' && (
              <button
                className="btn btn-primary"
                style={{ marginTop: 10, fontSize: 11, padding: '5px 10px' }}
                onClick={() => navigate(`/users/${selectedNode.id}`)}
              >
                View Profile →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
