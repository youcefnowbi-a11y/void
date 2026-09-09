import React, { useEffect, useState } from 'react'
import { t as _t } from '../i18n.js';
import axios from 'axios'
import { API_BASE } from '../api.js'

/* WAR DASHBOARD — la mission en un regard.
   Lit la vérité terrain (ledger + findings) via les routes /dashboard/*,
   dessine en SVG maison : timeline colorée par statut, donut sévérité,
   barres de productivité outillle. Zéro dépendance, zéro canvas — du
   SVG inline qui imprime et qui vit. */

const SEV = {
  CRITICAL: { color: '#e5484d', label: _t('sev_critical') },
  HIGH: { color: '#f76b15', label: _t('sev_high') },
  MEDIUM: { color: '#ffb224', label: _t('sev_medium') },
  LOW: { color: '#46a758', label: _t('sev_low') },
}

const fmt = ts => (ts || '').substring(5, 16) // MM-DD HH:MM

function Donut({ counts }) {
  const entries = Object.entries(counts).filter(([, n]) => n > 0)
  const total = entries.reduce((a, [, n]) => a + n, 0)
  if (!total) return <div className="text-mut text-[11px] font-mono">aucun verdict exploitable</div>
  const R = 44, C = 2 * Math.PI * R
  let off = 0
  const segs = entries.map(([sev, n]) => {
    const frac = n / total
    const dash = frac * C
    const seg = (
      <circle key={sev} cx="60" cy="60" r={R} fill="none"
        stroke={SEV[sev]?.color || '#9aa4b2'} strokeWidth="14"
        strokeDasharray={`${dash.toFixed(2)} ${(C - dash).toFixed(2)}`}
        strokeDashoffset={(-off).toFixed(2)}
        transform="rotate(-90 60 60)" />
    )
    off += dash
    return seg
  })
  return (
    <div className="flex items-center gap-3">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={R} fill="none" stroke="#23262e" strokeWidth="14" />
        {segs}
        <text x="60" y="57" textAnchor="middle" fontSize="24" fontWeight="800" fill="#e8e4dc">{total}</text>
        <text x="60" y="74" textAnchor="middle" fontSize="8" letterSpacing="1.5" fill="#9aa4b2">VERDICTS</text>
      </svg>
      <div className="flex flex-col gap-1">
        {entries.map(([sev, n]) => (
          <div key={sev} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ background: SEV[sev]?.color }} />
            <span className="text-[10px] font-mono uppercase tracking-wider text-mut">{SEV[sev]?.label || sev}</span>
            <span className="text-[11px] font-mono font-bold text-ink ml-auto">{n}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Timeline({ events }) {
  /* Barre de vie de la mission : chaque exécution = un segment.
     Vert = ok, orange = verdict exploitable, rouge = échec. */
  if (!events.length) return <div className="text-mut text-[11px] font-mono">ledger vide</div>
  const cols = 40
  const shown = events.slice(-cols * 14) // 14 ranges max
  const rows = Math.ceil(shown.length / cols)
  const w = Math.min(cols * 9, 400)
  const h = rows * 9 + 8
  const cells = shown.map((e, i) => {
    const x = (i % cols) * 9
    const y = Math.floor(i / cols) * 9
    const fill = e.status === _t('dash_legend_ok') || e.status == null
      ? (e.exploitable ? '#f76b15' : '#2f4f46')
      : '#5b2430'
    return <rect key={i} x={x} y={y} width="6" height="6" rx="1" fill={fill}>
      <title>{`${e.ts || ''} ${e.tool || ''} ${e.status || ''}`}</title>
    </rect>
  })
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {cells}
    </svg>
  )
}

function ToolBars({ topTools }) {
  if (!topTools?.length) return <div className="text-mut text-[11px] font-mono">—</div>
  const max = topTools[0][1]
  return (
    <div className="flex flex-col gap-1.5">
      {topTools.map(([name, n]) => (
        <div key={name} className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-mut w-[130px] truncate" title={name}>{name}</span>
          <div className="flex-1 h-2 rounded bg-wash overflow-hidden">
            <div className="h-full rounded"
              style={{ width: `${(n / max) * 100}%`, background: n === max ? '#2f4f46' : '#3b554c' }} />
          </div>
          <span className="font-mono text-[10px] font-bold text-ink w-8 text-right">{n}</span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard({ mission }) {
  const [tl, setTl] = useState(null)
  const [sum, setSum] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    let alive = true
    const load = () => {
      axios.get(`${API_BASE}/dashboard/timeline`, { params: { mission } })
        .then(r => alive && setTl(r.data)).catch(() => alive && setErr(true))
      axios.get(`${API_BASE}/dashboard/summary`, { params: { mission } })
        .then(r => alive && setSum(r.data)).catch(() => {})
    }
    load()
    const iv = setInterval(load, 10000) // refresh live pendant la mission
    return () => { alive = false; clearInterval(iv) }
  }, [mission])

  if (err && !tl) {
    return (
      <div className="h-full flex items-center justify-center text-mut font-mono text-[11px]">
        dashboard unavailable — backend unreachable
      </div>
    )
  }
  if (!tl || !sum) {
    return (
      <div className="h-full flex items-center justify-center text-mut font-mono text-[11px]">
        reading the ledger…
      </div>
    )
  }

  const kpis = [
    { n: sum.total_executions ?? 0, label: _t('dash_executions') },
    { n: sum.distinct_tools ?? 0, label: _t('dash_tools') },
    { n: sum.strikes ?? 0, label: _t('dash_strikes') },
    { n: sum.exploitable_verdicts ?? 0, label: _t('dash_exploitable') },
    { n: sum.findings_count ?? 0, label: _t('dash_banked') },
    { n: sum.failures ?? 0, label: _t('dash_failures') },
  ]

  return (
    <div className="h-full overflow-y-auto pr-1 flex flex-col gap-3">
      {/* KPI header */}
      <div className="grid grid-cols-3 gap-2">
        {kpis.map(k => (
          <div key={k.label} className="panel px-3 py-2 flex flex-col justify-center">
            <span className="font-mono text-[19px] font-bold text-ink leading-none">{k.n}</span>
            <span className="text-[9px] uppercase tracking-[.14em] text-mut font-mono mt-1">{k.label}</span>
          </div>
        ))}
      </div>

      {/* Timeline de vie */}
      <div className="panel px-3 py-2.5">
        <div className="eyebrow mb-2">timeline — vie de la mission</div>
        <Timeline events={tl.events || []} />
        <div className="flex gap-3 mt-2 text-[9px] font-mono text-mut uppercase tracking-wider">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: '#2f4f46' }} /> ok</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: '#f76b15' }} /> exploitable</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: '#5b2430' }} /> failure</span>
        </div>
      </div>

      {/* Sévérité + productivité */}
      <div className="grid grid-cols-2 gap-2">
        <div className="panel px-3 py-2.5">
          <div className="eyebrow mb-2">{_t('dash_sev_title')}</div>
          <Donut counts={sum.severity_mix || {}} />
        </div>
        <div className="panel px-3 py-2.5">
          <div className="eyebrow mb-2">outils les plus productifs</div>
          <ToolBars topTools={sum.top_tools} />
        </div>
      </div>

      {/* Fenêtre temporelle */}
      {(sum.first_ts || sum.last_ts) && (
        <div className="panel px-3 py-2 flex items-center justify-between font-mono text-[10px] text-mut">
          <span>{fmt(sum.first_ts)} → {fmt(sum.last_ts)}</span>
          <span className="text-ink">{tl.target}</span>
        </div>
      )}
    </div>
  )
}
