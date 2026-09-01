import React, { useRef, useEffect, useState, useCallback } from 'react'

/* LA CONSOLE-DOCK — citoyenne de première classe du PONT UNIQUE.
   Elle ne disparaît JAMAIS : ni au sol, ni en campagne, ni après.
   • poignée de redimensionnement (drag la lisière haute)
   • rabat en liseron 34px qui montre la dernière ligne
   • plein écran pour les longues campagnes
   • séparateurs de session : le journal traverse les missions. */

const LINE_CONFIG = {
  separator: { color: 'log-system',  tag: '····', badge: 'bg-wash text-faint border-line' },
  system:    { color: 'log-system',  tag: 'SYS',   badge: 'bg-infotint text-info border-info/25' },
  plan:      { color: 'log-plan',    tag: 'PLAN',  badge: 'bg-warntint text-warn border-warn/25' },
  tool:      { color: 'log-tool',    tag: 'TOOL',  badge: 'bg-[#1B1533] text-[#C4B5FD] border-[#A78BFA]/25' },
  ok:        { color: 'log-ok',      tag: 'OK',    badge: 'bg-oktint text-ok border-ok/25' },
  error:     { color: 'log-error',   tag: 'ERR',   badge: 'bg-dangertint text-danger border-danger/25' },
  heal:      { color: 'log-heal',    tag: 'HEAL',  badge: 'bg-warntint text-warn border-warn/25' },
  think:     { color: 'log-think',   tag: 'BRAIN', badge: 'bg-[#0E1E38] text-[#93C5FD] border-[#60A5FA]/25' },
  round:     { color: 'log-tool',    tag: 'ROUND', badge: 'bg-[#1B1533] text-[#C4B5FD] border-[#A78BFA]/25' },
  ops:       { color: 'log-plan',    tag: 'OPS',   badge: 'bg-cyantint text-cyan border-cyan/25' },
  chat:      { color: 'log-think',   tag: 'CHAT',  badge: 'bg-[#0E1E38] text-[#93C5FD] border-[#60A5FA]/25' },
  finding:   { color: 'log-finding', tag: 'ALERT', badge: 'bg-dangertint text-danger border-danger/35' },
}

function fmtTime(ts) {
  if (!ts) return '--:--:--'
  try {
    return new Date(ts).toLocaleTimeString('fr-FR', { hour12: false })
  } catch { return '--:--:--' }
}

const H_MIN = 140, H_MAX = 700

export default function LiveConsole({ logs, status, onClear }) {
  const endRef = useRef(null)
  const containerRef = useRef(null)
  const [pinned, setPinned] = useState(true)
  const [filter, setFilter] = useState('all')
  const [isExpanded, setIsExpanded] = useState(false)
  const [isFolded, setIsFolded] = useState(false)
  const [height, setHeight] = useState(300)
  const [copied, setCopied] = useState(false)
  const dragRef = useRef(null)

  useEffect(() => {
    if (pinned && endRef.current && !isFolded) {
      endRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, pinned, isFolded])

  /* ── la poignée : drag la lisière haute du dock ── */
  const onHandleDown = useCallback((e) => {
    e.preventDefault()
    dragRef.current = { startY: e.clientY, startH: height }
    const move = (ev) => {
      if (!dragRef.current) return
      const h = dragRef.current.startH + (dragRef.current.startY - ev.clientY)
      setHeight(Math.max(H_MIN, Math.min(H_MAX, h)))
    }
    const up = () => {
      dragRef.current = null
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }, [height])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 40)
  }

  const copyLogs = () => {
    const text = filtered.map(l => `[${fmtTime(l.ts)}] [${(l.type || 'info').toUpperCase()}] ${l.text}`).join('\n')
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const filtered = filter === 'all' ? logs : logs.filter(l => {
    if (filter === 'tools') return l.type === 'tool' || l.type === 'ok' || l.type === 'error' || l.type === 'heal'
    if (filter === 'findings') return l.type === 'finding'
    if (filter === 'ai') return l.type === 'think'
    if (filter === 'errors') return l.type === 'error'
    return true
  })

  const counts = {
    all: logs.length,
    tools: logs.filter(l => l.type === 'tool' || l.type === 'ok' || l.type === 'error' || l.type === 'heal').length,
    findings: logs.filter(l => l.type === 'finding').length,
    ai: logs.filter(l => l.type === 'think').length,
    errors: logs.filter(l => l.type === 'error').length,
  }

  const filters = [
    { key: 'all', label: 'tout', count: counts.all },
    { key: 'tools', label: 'outils', count: counts.tools },
    { key: 'findings', label: 'alertes', count: counts.findings },
    { key: 'ai', label: 'ia', count: counts.ai },
    { key: 'errors', label: 'erreurs', count: counts.errors },
  ]

  const lastLine = logs.length ? logs[logs.length - 1] : null

  /* ── LIZERON : la console rabattue, une ligne de vie ── */
  if (isFolded && !isExpanded) {
    return (
      <div className="panel-raised overflow-hidden select-none">
        <button onClick={() => setIsFolded(false)}
          className="w-full px-4 py-2 flex items-center gap-3 text-left hover:bg-wash transition-colors group">
          <span className="font-mono text-[9px] uppercase tracking-[.24em] text-mut shrink-0">console</span>
          <span className="w-1.5 h-1.5 rounded-full shrink-0 bg-volt animate-pulse" />
          <span className="flex-1 font-mono text-[11px] text-slate truncate">
            {lastLine ? `${lastLine.type === 'separator' ? '— ' : ''}${lastLine.text}` : 'en attente…'}
          </span>
          <span className="font-mono text-[10px] text-faint shrink-0">{logs.length} lignes</span>
          <span className="font-mono text-[11px] text-faint group-hover:text-volt transition-colors shrink-0">▲ déplier</span>
        </button>
      </div>
    )
  }

  return (
    <div className={`panel-raised overflow-hidden flex flex-col transition-all ${
      isExpanded ? 'fixed inset-4 z-50' : ''
    }`} style={isExpanded ? undefined : { height }}>

      {/* ── poignée de redimensionnement ── */}
      {!isExpanded && (
        <div onPointerDown={onHandleDown}
          className="h-2 shrink-0 cursor-row-resize bg-transparent hover:bg-volt/20 transition-colors relative group"
          title="glisser pour redimensionner">
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-[3px] rounded-full bg-line2 group-hover:bg-volt transition-colors" />
        </div>
      )}

      {/* Header */}
      <div className={`px-3.5 py-2 border-b flex items-center justify-between flex-wrap gap-2 border-line bg-wash`}>
        <div className="flex items-center gap-2">
          <span className="font-disp text-[13px] font-bold text-volt">06</span>
          <span className="eyebrow">console de campagne — toujours vivante</span>
          {status === 'running' && (
            <span className="flex items-center gap-1.5 ml-2 px-2 py-0.5 rounded-full border bg-voltlite border-volt/30">
              <span className="w-1.5 h-1.5 bg-volt rounded-full animate-pulse" />
              <span className="font-mono text-[10px] text-volt tracking-widest uppercase font-bold">live</span>
            </span>
          )}
          <span className="font-mono text-[10px] ml-1 text-faint">{logs.length} lignes</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex gap-px rounded-full p-0.5 border bg-paper border-line">
            {filters.map(f => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`px-2.5 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  filter === f.key ? 'bg-volt text-mist font-bold' : 'text-mut hover:text-ink'
                }`}>
                {f.label} {f.count > 0 && <span className="opacity-70 text-[9px]">({f.count})</span>}
              </button>
            ))}
          </div>

          <button onClick={copyLogs} disabled={filtered.length === 0} title="Copier le journal"
            className="px-2.5 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-wider border border-line text-mut hover:text-volt hover:border-volt/40 transition-colors">
            {copied ? '✓ copié' : 'copier'}
          </button>

          {onClear && (
            <button onClick={onClear} title="Effacer le journal (les sessions passées aussi)"
              className="px-2.5 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-wider border border-line text-mut hover:text-danger hover:border-danger/40 transition-colors">
              vider
            </button>
          )}

          <button onClick={() => setIsFolded(true)} title="Rabattre en liseron"
            className="px-2.5 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-wider border border-line text-mut hover:text-volt hover:border-volt/40 transition-colors">
            ▼ rabattre
          </button>
          <button onClick={() => setIsExpanded(!isExpanded)} title={isExpanded ? 'Réduire' : 'Plein écran'}
            className="px-2.5 py-0.5 rounded-full font-mono text-[10px] uppercase tracking-wider border border-line text-mut hover:text-volt hover:border-volt/40 transition-colors">
            {isExpanded ? 'réduire' : 'plein écran'}
          </button>
        </div>
      </div>

      {/* Terminal body */}
      <div ref={containerRef} onScroll={handleScroll}
        className={`terminal-bg px-4 py-3 overflow-y-auto select-text flex-1 min-h-0 ${isExpanded ? '' : ''}`}>
        {filtered.length === 0 && (
          <div className="text-center py-14 font-mono text-xs flex flex-col items-center gap-2 text-faint">
            <span className="text-2xl text-volt">⚡</span>
            <span>{status === 'idle' ? "▶ le journal est ouvert — un ordre de frappe l’animera." : 'aucune entrée pour ce filtre.'}</span>
          </div>
        )}

        <div className="space-y-1">
          {filtered.map((line, i) => {
            if (line.type === 'separator') {
              return (
                <div key={i} className="flex items-center gap-3 py-2">
                  <div className="flex-1 h-px bg-line2" />
                  <span className="font-mono text-[9px] uppercase tracking-[.3em] text-faint">{line.text}</span>
                  <div className="flex-1 h-px bg-line2" />
                </div>
              )
            }
            const cfg = LINE_CONFIG[line.type] || LINE_CONFIG.system
            return (
              <div key={i} className="flex items-start gap-2 rounded px-1 py-0.5 transition-colors group hover:bg-white/[0.03]">
                <span className="text-[11.5px] select-none font-mono shrink-0 pt-0.5 text-faint">
                  [{fmtTime(line.ts)}]
                </span>
                <span className={`text-[9px] uppercase font-bold tracking-widest px-1.5 py-0.5 rounded border shrink-0 select-none ${cfg.badge}`}>
                  {cfg.tag}
                </span>
                <span className={`flex-1 break-words font-mono text-[12.5px] leading-relaxed ${cfg.color}`}>
                  {line.text}
                </span>
              </div>
            )
          })}
        </div>
        <div ref={endRef} />
      </div>

      {!pinned && (
        <button onClick={() => { setPinned(true); endRef.current?.scrollIntoView({ behavior: 'smooth' }) }}
          className="w-full py-2 text-center font-mono text-[10px] text-mist bg-gradient-to-r from-volt to-cyan hover:opacity-90 transition-opacity uppercase tracking-widest font-semibold flex items-center justify-center gap-1">
          <span>↓ flux en pause — cliquer pour suivre</span>
        </button>
      )}
    </div>
  )
}
