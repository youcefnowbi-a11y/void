import React from 'react'

/* Severity = signal strength on daylight: critical burns signal red,
   high burns orange, medium amber, low mint, info slate. The color IS
   the urgency — no reading required. La sémantique prime sur l'esthétique. */

const SEV_STYLES = {
  critical: { border: 'border-danger', dot: 'bg-danger',    tint: 'bg-dangertint', label: 'CRITIQUE' },
  high:     { border: 'border-warn',   dot: 'bg-warn',     tint: 'bg-warntint',   label: 'ÉLEVÉ' },
  medium:   { border: 'border-warn/60', dot: 'bg-warn/70', tint: 'bg-white/[0.03]', label: 'MOYEN' },
  low:      { border: 'border-ok/50',  dot: 'bg-ok',       tint: 'bg-oktint',     label: 'FAIBLE' },
  info:     { border: 'border-line2',  dot: 'bg-mut',      tint: 'bg-white/[0.03]', label: 'INFO' },
}

export default function FindingsLive({ findings }) {
  if (findings.length === 0) return null
  return (
    <div className="panel overflow-hidden">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="font-disp text-[13px] font-medium text-danger">⚠</span>
          <span className="eyebrow">renseignement extrait</span>
        </div>
        <span className="text-[11px] tracking-[.1em] uppercase font-medium text-ink">
          {findings.length} verdict{findings.length > 1 ? 's' : ''}
        </span>
      </div>
      <div className="max-h-[280px] overflow-y-auto divide-y divide-line">
        {findings.map((f, i) => {
          const s = SEV_STYLES[f.severity] || SEV_STYLES.info
          return (
            <div key={i} className={`finding-card px-4 py-3 border-l-2 ${s.border} ${s.tint}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2 h-2 rounded-full ${s.dot}`} />
                <span className="text-[10px] tracking-[.16em] uppercase font-medium text-ink">
                  {s.label}
                </span>
                {f.tool && (
                  <span className="font-mono text-[10px] text-mut ml-auto">
                    {f.tool}
                  </span>
                )}
              </div>
              <p className="text-[12.5px] leading-relaxed text-ash">
                {(f.detail || f.summary || '')?.substring(0, 200) || '—'}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
