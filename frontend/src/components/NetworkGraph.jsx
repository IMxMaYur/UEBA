/**
 * NetworkGraph.jsx
 * D3.js force-directed graph showing user → device → alert_type relationships.
 * Props:
 *   userId       – central user node ID
 *   uniquePcs    – how many device nodes to generate
 *   alertTypes   – array of alert type strings
 *   eventCounts  – { event_type: count } from timeline
 */
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const TYPE_COLOR = {
  user:       '#3b82f6',
  device:     '#8b5cf6',
  alert:      '#ef4444',
  activity:   '#10b981',
}

export default function NetworkGraph({ userId, uniquePcs = 2, alertTypes = [], eventCounts = {} }) {
  const svgRef = useRef(null)

  useEffect(() => {
    if (!svgRef.current) return

    const width  = svgRef.current.clientWidth  || 500
    const height = svgRef.current.clientHeight || 340

    // ----- build nodes & links ----
    const nodes = [{ id: userId, type: 'user', label: userId, r: 22 }]
    const links = []

    // Device nodes
    const pcCount = Math.min(uniquePcs, 8)
    for (let i = 0; i < pcCount; i++) {
      const id = `PC-${String(i + 1).padStart(3, '0')}`
      nodes.push({ id, type: 'device', label: id, r: 14 })
      links.push({ source: userId, target: id, strength: 0.6 })
    }

    // Alert type nodes
    alertTypes.slice(0, 5).forEach(at => {
      const id = `alert_${at}`
      nodes.push({ id, type: 'alert', label: at.replace(/_/g, ' '), r: 16 })
      links.push({ source: userId, target: id, strength: 0.5 })
    })

    // Activity event nodes (top 3 by count)
    const topEvents = Object.entries(eventCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
    topEvents.forEach(([evType, count]) => {
      const id = `ev_${evType}`
      if (!nodes.find(n => n.id === id)) {
        nodes.push({ id, type: 'activity', label: `${evType.replace(/_/g,' ')} ×${count}`, r: 12 })
        links.push({ source: userId, target: id, strength: 0.4 })
      }
    })

    // ----- D3 setup ----
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    svg
      .attr('width', width)
      .attr('height', height)

    // Gradient defs for links
    const defs = svg.append('defs')
    defs.append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '-0 -5 10 10')
        .attr('refX', 26)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
      .append('path')
        .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
        .attr('fill', '#334155')

    const simulation = d3.forceSimulation(nodes)
      .force('link',   d3.forceLink(links).id(d => d.id).distance(100).strength(d => d.strength))
      .force('charge', d3.forceManyBody().strength(-280))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => d.r + 14))

    // Links
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
        .attr('stroke', '#1e2d45')
        .attr('stroke-width', 1.5)
        .attr('marker-end', 'url(#arrowhead)')

    // Node groups
    const nodeGroup = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
        .attr('cursor', 'pointer')
        .call(d3.drag()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end',  (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            d.fx = null; d.fy = null
          })
        )

    // Glow circles (outer ring)
    nodeGroup.append('circle')
      .attr('r', d => d.r + 5)
      .attr('fill', d => TYPE_COLOR[d.type] + '22')

    // Main circles
    nodeGroup.append('circle')
      .attr('r', d => d.r)
      .attr('fill', d => TYPE_COLOR[d.type] + 'cc')
      .attr('stroke', d => TYPE_COLOR[d.type])
      .attr('stroke-width', 2)

    // Labels
    nodeGroup.append('text')
      .attr('dy', d => d.r + 14)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94a3b8')
      .attr('font-size', 10)
      .attr('font-family', 'Inter, sans-serif')
      .text(d => d.label.length > 16 ? d.label.slice(0, 15) + '…' : d.label)

    // Icon letters inside circles
    nodeGroup.append('text')
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .attr('font-size', d => d.r * 0.65)
      .attr('font-weight', 700)
      .attr('font-family', 'Inter, sans-serif')
      .text(d => {
        if (d.type === 'user')     return 'U'
        if (d.type === 'device')   return '💻'
        if (d.type === 'alert')    return '🚨'
        return '⚡'
      })

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => simulation.stop()
  }, [userId, uniquePcs, alertTypes, eventCounts])

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', background: 'transparent' }}
    />
  )
}
