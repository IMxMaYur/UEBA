import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import { Network } from 'lucide-react'

/**
 * NetworkGraphPage – D3 force-directed graph of user/device/file/domain relationships.
 * Fetches from /api/stats/network-graph (fallback: demo data).
 */
export default function NetworkGraphPage() {
  const svgRef = useRef(null)

  useEffect(() => {
    // Demo graph data when API not available
    const demoNodes = [
      { id: 'U101', type: 'user',   risk: 0.92, label: 'U101' },
      { id: 'U202', type: 'user',   risk: 0.45, label: 'U202' },
      { id: 'U303', type: 'user',   risk: 0.78, label: 'U303' },
      { id: 'U404', type: 'user',   risk: 0.30, label: 'U404' },
      { id: 'U505', type: 'user',   risk: 0.88, label: 'U505' },
      { id: 'DEV-A', type: 'device', risk: 0,   label: 'USB-A' },
      { id: 'DEV-B', type: 'device', risk: 0,   label: 'USB-B' },
      { id: 'FILE-1', type: 'file',  risk: 0,   label: 'proj_data.xlsx' },
      { id: 'FILE-2', type: 'file',  risk: 0,   label: 'confidential.pdf' },
      { id: 'DOM-1', type: 'domain', risk: 0,   label: 'dropbox.com' },
      { id: 'DOM-2', type: 'domain', risk: 0,   label: 'drive.google.com' },
      { id: 'DOM-3', type: 'domain', risk: 0,   label: 'pastebin.com' },
    ]
    const demoLinks = [
      { source: 'U101', target: 'FILE-2', type: 'access' },
      { source: 'U101', target: 'DEV-A',  type: 'transfer' },
      { source: 'U101', target: 'DOM-1',  type: 'communication' },
      { source: 'U101', target: 'DOM-3',  type: 'communication' },
      { source: 'U202', target: 'FILE-1', type: 'access' },
      { source: 'U303', target: 'FILE-2', type: 'access' },
      { source: 'U303', target: 'DEV-B',  type: 'transfer' },
      { source: 'U303', target: 'DOM-2',  type: 'communication' },
      { source: 'U404', target: 'FILE-1', type: 'access' },
      { source: 'U505', target: 'FILE-2', type: 'access' },
      { source: 'U505', target: 'DEV-A',  type: 'transfer' },
    ]

    const width  = svgRef.current.clientWidth || 800
    const height = 500

    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)

    // Arrow marker
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10').attr('refX', 22).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#2d4a6e')

    const sim = d3.forceSimulation(demoNodes)
      .force('link', d3.forceLink(demoLinks).id(d => d.id).distance(110))
      .force('charge', d3.forceManyBody().strength(-320))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(32))

    const typeColors = { user: null, device: '#06b6d4', file: '#8b5cf6', domain: '#f59e0b' }
    const typeRadius = { user: 14, device: 11, file: 11, domain: 11 }

    function userColor(risk) {
      if (risk >= 0.9) return '#ef4444'
      if (risk >= 0.75) return '#f97316'
      if (risk >= 0.6) return '#f59e0b'
      if (risk >= 0.3) return '#3b82f6'
      return '#10b981'
    }

    const linkEl = svg.append('g').selectAll('line')
      .data(demoLinks).join('line')
      .attr('stroke', '#1e2d45').attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)')

    const nodeG = svg.append('g').selectAll('g')
      .data(demoNodes).join('g')
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      )

    // Glow for high-risk users
    nodeG.each(function(d) {
      const g = d3.select(this)
      const r = typeRadius[d.type]
      const col = d.type === 'user' ? userColor(d.risk) : typeColors[d.type]
      if (d.type === 'user' && d.risk >= 0.75) {
        g.append('circle').attr('r', r + 6).attr('fill', col).attr('opacity', 0.2)
      }
      g.append('circle').attr('r', r).attr('fill', col).attr('stroke', '#0a0e1a').attr('stroke-width', 2)
      g.append('text')
        .text(d.label)
        .attr('dy', r + 13)
        .attr('text-anchor', 'middle')
        .attr('font-size', 10)
        .attr('fill', '#94a3b8')
        .attr('font-family', 'JetBrains Mono, monospace')
    })

    // Node type labels inside
    nodeG.append('text')
      .text(d => d.type === 'user' ? '👤' : d.type === 'device' ? '🔌' : d.type === 'file' ? '📄' : '🌐')
      .attr('text-anchor', 'middle').attr('dy', '0.35em').attr('font-size', 10)

    sim.on('tick', () => {
      linkEl
        .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      nodeG.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => sim.stop()
  }, [])

  const legendItems = [
    { label: 'User (Critical)',  color: '#ef4444' },
    { label: 'User (High)',      color: '#f97316' },
    { label: 'User (Normal)',    color: '#10b981' },
    { label: 'Device',          color: '#06b6d4' },
    { label: 'File',            color: '#8b5cf6' },
    { label: 'Domain',          color: '#f59e0b' },
  ]

  return (
    <div className="animate-in" style={{ maxWidth: 1200 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <Network size={20} color="#06b6d4" />
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Network Interaction Graph</h1>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Force-directed visualization of user–device–file–domain relationships</p>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Legend bar */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          {legendItems.map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: item.color }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.label}</span>
            </div>
          ))}
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>Drag nodes to rearrange</span>
        </div>
        <svg ref={svgRef} style={{ width: '100%', height: 500, display: 'block', background: 'var(--bg-secondary)' }} />
      </div>

      <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        {[
          { title: 'Access',        color: '#1e2d45', desc: 'User accessed a file or resource' },
          { title: 'Data Transfer',  color: '#1e2d45', desc: 'File copied to device or uploaded' },
          { title: 'Communication', color: '#1e2d45', desc: 'Email or web communication' },
        ].map(e => (
          <div key={e.title} className="card" style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ height: 2, width: 24, background: '#2d4a6e' }} />
              <span style={{ fontSize: 12, fontWeight: 600 }}>{e.title}</span>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>{e.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
