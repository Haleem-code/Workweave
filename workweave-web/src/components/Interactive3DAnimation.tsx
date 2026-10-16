'use client'

import React, { useEffect, useRef, useState } from 'react'

interface Node3D {
  x: number
  y: number
  z: number
  label: string
  code: string
  type: 'doc' | 'team' | 'graph' | 'task' | 'memory' | 'reasoning'
  description: string
}

export function Interactive3DAnimation() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const isDraggingRef = useRef(false)
  const lastMouseRef = useRef({ x: 0, y: 0 })
  const rotRef = useRef({ x: 0.32, y: -0.55 })
  const velRef = useRef({ x: 0.0015, y: 0.003 })
  const [activeNode, setActiveNode] = useState<string>('03. DEPENDENCY GRAPH')
  const [meshMode, setMeshMode] = useState<'lattice' | 'flow'>('lattice')

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let time = 0

    // 6 Primary Nodes representing the Workweave information architecture
    // Documents & Records -> Teams -> Dependencies -> Tasks -> Remembered Outcomes
    const size = 115
    const rawNodes: Node3D[] = [
      { x: -size, y: -size * 0.8, z: -size * 0.7, label: 'DOCS & RECORDS', code: '01', type: 'doc', description: 'Spreadsheets, Google Drive, PDFs, and SOP guides' },
      { x: size, y: -size * 0.8, z: -size * 0.7, label: 'TEAMS & ROLES', code: '02', type: 'team', description: 'Operations, Procurement, and CS ownership matrix' },
      { x: 0, y: -size * 0.2, z: size * 0.9, label: 'DEPENDENCY GRAPH', code: '03', type: 'graph', description: 'Deterministic FalkorDB mathematical relationships' },
      { x: -size, y: size * 0.8, z: -size * 0.2, label: 'INTERNAL TASKS', code: '04', type: 'task', description: 'Synthesized review action items with owner assignments' },
      { x: size, y: size * 0.8, z: -size * 0.2, label: 'REMEMBRANCE', code: '05', type: 'memory', description: 'Retained task outcomes and approved procedure audits' },
      { x: 0, y: size * 0.4, z: size * 0.4, label: 'REASONING PROBES', code: '06', type: 'reasoning', description: 'Multi-hop autonomous probes with ground-truth citations' },
    ]

    // Connected edges showing data and workflow propagation
    const edges: [number, number][] = [
      [0, 1], // Docs connect to Teams
      [0, 2], // Docs feed the Dependency Graph
      [1, 2], // Teams anchor to Graph entities
      [2, 5], // Graph feeds Reasoning Probes
      [5, 3], // Probes synthesize Internal Tasks
      [3, 4], // Completed Tasks become Remembrance
      [4, 2], // Remembrance informs future Graph investigations
      [0, 3], // Evidence traces directly to Tasks
      [1, 3], // Teams assign to Tasks
      [5, 4], // Probes cite historical episodes
    ]

    // Animated data packets
    const particles = Array.from({ length: 18 }, (_, i) => ({
      edgeIndex: i % edges.length,
      progress: i / 18,
      speed: 0.005 + (i % 3) * 0.002
    }))

    const render = () => {
      time += 0.016
      const dpr = window.devicePixelRatio || 1
      const width = canvas.clientWidth
      const height = canvas.clientHeight

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr
        canvas.height = height * dpr
      }

      ctx.save()
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, width, height)

      // Background subtle precision grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)'
      ctx.lineWidth = 1
      const step = 32
      for (let x = 0; x < width; x += step) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
        ctx.stroke()
      }
      for (let y = 0; y < height; y += step) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
        ctx.stroke()
      }

      // Smooth idle rotation
      if (!isDraggingRef.current) {
        rotRef.current.y += velRef.current.y
        rotRef.current.x += velRef.current.x
      }

      const rx = rotRef.current.x
      const ry = rotRef.current.y

      // 3D projection math
      const project = (x: number, y: number, z: number) => {
        const cosY = Math.cos(ry)
        const sinY = Math.sin(ry)
        const x1 = x * cosY - z * sinY
        const z1 = z * cosY + x * sinY

        const cosX = Math.cos(rx)
        const sinX = Math.sin(rx)
        const y2 = y * cosX - z1 * sinX
        const z2 = z1 * cosX + y * sinX

        const focal = 460
        const scale = focal / (focal + z2 + 220)
        const px = width / 2 + x1 * scale
        const py = height / 2 + y2 * scale
        return { x: px, y: py, z: z2, scale }
      }

      const projected = rawNodes.map(n => ({
        ...n,
        p: project(n.x, n.y, n.z)
      }))

      // Core knowledge engine diamond in center
      const coreSize = Math.sin(time * 2.5) * 6 + 28
      const corePoints = [
        project(0, -coreSize, 0),
        project(coreSize, 0, 0),
        project(0, coreSize, 0),
        project(-coreSize, 0, 0),
        project(0, 0, -coreSize),
        project(0, 0, coreSize)
      ]

      ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)'
      ctx.lineWidth = 1
      for (let i = 0; i < 4; i++) {
        const next = (i + 1) % 4
        ctx.beginPath()
        ctx.moveTo(corePoints[i].x, corePoints[i].y)
        ctx.lineTo(corePoints[next].x, corePoints[next].y)
        ctx.stroke()

        ctx.beginPath()
        ctx.moveTo(corePoints[i].x, corePoints[i].y)
        ctx.lineTo(corePoints[4].x, corePoints[4].y)
        ctx.stroke()

        ctx.beginPath()
        ctx.moveTo(corePoints[i].x, corePoints[i].y)
        ctx.lineTo(corePoints[5].x, corePoints[5].y)
        ctx.stroke()
      }

      // Draw Edges
      edges.forEach(([i, j], edgeIdx) => {
        const p1 = projected[i].p
        const p2 = projected[j].p
        const depthAlpha = Math.max(0.12, Math.min(0.55, 0.35 + (p1.z + p2.z) / 900))

        ctx.strokeStyle = `rgba(255, 255, 255, ${depthAlpha})`
        ctx.lineWidth = edgeIdx === 1 || edgeIdx === 3 ? 1.5 : 1
        ctx.beginPath()
        ctx.moveTo(p1.x, p1.y)
        ctx.lineTo(p2.x, p2.y)
        ctx.stroke()
      })

      // Traveling data packets
      particles.forEach(pt => {
        pt.progress += pt.speed
        if (pt.progress > 1) pt.progress = 0

        const [i, j] = edges[pt.edgeIndex]
        const p1 = projected[i].p
        const p2 = projected[j].p

        const curX = p1.x + (p2.x - p1.x) * pt.progress
        const curY = p1.y + (p2.y - p1.y) * pt.progress

        ctx.fillStyle = '#ffffff'
        ctx.fillRect(curX - 2, curY - 2, 4, 4)
      })

      // Draw Nodes (sorted by depth)
      projected.sort((a, b) => b.p.z - a.p.z)
      projected.forEach(node => {
        const { x, y, scale } = node.p
        const isSelected = activeNode.includes(node.code)

        const box = isSelected ? 11 : 7
        ctx.fillStyle = isSelected ? '#ffffff' : '#09090b'
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = isSelected ? 2 : 1
        ctx.fillRect(x - box / 2, y - box / 2, box, box)
        ctx.strokeRect(x - box / 2, y - box / 2, box, box)

        if (isSelected) {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)'
          ctx.strokeRect(x - box - 3, y - box - 3, (box + 3) * 2, (box + 3) * 2)
        }

        ctx.font = `600 ${Math.max(9, Math.round(11 * scale))}px "Geist Mono", "JetBrains Mono", monospace`
        ctx.fillStyle = isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.7)'
        ctx.fillText(`${node.code}. ${node.label}`, x + box + 5, y + 4)
      })

      // Telemetry HUD info
      ctx.font = '500 10px "Geist Mono", "JetBrains Mono", monospace'
      ctx.fillStyle = 'rgba(255, 255, 255, 0.45)'
      ctx.fillText(`Cluster: Local Kernel · 127.0.0.1`, 16, 22)
      ctx.fillText(`Rotation X: ${(rx * (180 / Math.PI)).toFixed(1)}° · Y: ${(ry * (180 / Math.PI)).toFixed(1)}°`, 16, 36)
      ctx.fillText(`Knowledge Flow: 6 Active Nodes · Deterministic`, 16, 50)

      ctx.restore()
      animId = requestAnimationFrame(render)
    }

    render()

    const onMouseDown = (e: MouseEvent) => {
      isDraggingRef.current = true
      lastMouseRef.current = { x: e.clientX, y: e.clientY }
    }
    const onMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return
      const dx = e.clientX - lastMouseRef.current.x
      const dy = e.clientY - lastMouseRef.current.y
      rotRef.current.y += dx * 0.007
      rotRef.current.x += dy * 0.007
      lastMouseRef.current = { x: e.clientX, y: e.clientY }
    }
    const onMouseUp = () => {
      isDraggingRef.current = false
    }

    canvas.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)

    return () => {
      cancelAnimationFrame(animId)
      canvas.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [activeNode, meshMode])

  return (
    <div className="three-d-container">
      <div className="three-d-hud">
        <div className="hud-badge">3D Architecture Telemetry</div>
        <div className="hud-controls">
          <span className="hud-hint">Drag to rotate lattice</span>
          <button
            type="button"
            className="bracket-btn text-button"
            onClick={() => setMeshMode(m => (m === 'lattice' ? 'flow' : 'lattice'))}
          >
            {meshMode === 'lattice' ? 'Lattice view' : 'Flow view'}
          </button>
        </div>
      </div>
      <canvas ref={canvasRef} className="three-d-canvas" />
      <div className="three-d-disclaimer">
        <span>ARCHITECTURAL PREVIEW · DECORATIVE · COMPANY DATA VERIFICATION OCCURS AFTER WORKSPACE ACTIVATION</span>
      </div>
      <div className="three-d-node-bar">
        {[
          { code: '01', title: 'DOCS & RECORDS', desc: 'Spreadsheets, Guides, Drive' },
          { code: '02', title: 'TEAMS & ROLES', desc: 'Ownership & Responsibility' },
          { code: '03', title: 'DEPENDENCY GRAPH', desc: 'Deterministic FalkorDB Mesh' },
          { code: '04', title: 'INTERNAL TASKS', desc: 'Action Items & Resolutions' },
          { code: '05', title: 'REMEMBRANCE', desc: 'Memory & Procedure History' }
        ].map(item => (
          <button
            key={item.code}
            type="button"
            className={`node-pill ${activeNode.includes(item.code) ? 'active' : ''}`}
            onClick={() => setActiveNode(`${item.code}. ${item.title}`)}
          >
            <strong>{item.code}. {item.title}</strong>
            <small>{item.desc}</small>
          </button>
        ))}
      </div>
    </div>
  )
}
