import React, { useState } from 'react'
import axios from 'axios'
import { API_BASE } from '../api.js'

/* ═══════════════════════════════════════════════════════════════════
   SESSION NEUVE — the memory purge panel.
   VOIDFORGE keeps SEVERAL memories; each checkbox maps to one store:
     chat      → missions/_chat/history.json   (war-room conversation)
     pending   → missions/_pending_plan.json   (plan awaiting verdict)
     bandit    → core/bandit.json              (learned tool reliability)
     healer    → core/learned_fixes.json       (learned error fixes)
     intel     → data/intel/<domain>.json      (Living Graph per target)
   forged tools and missions.db are NEVER touched from here.
   ═══════════════════════════════════════════════════════════════════ */

const STORES = [
  { id: 'chat', label: 'conversation war room', hint: 'la ligne sécurisée repart de zéro' },
  { id: 'pending', label: 'plan en attente', hint: 'verdict annulé, panel vidé' },
  { id: 'bandit', label: 'fiabilité apprise (bandit)', hint: 'elle réapprendra de zéro' },
  { id: 'healer', label: 'fixes appris (healer)', hint: 'les réparations apprises sont oubliées' },
]

export default function FreshSessionPanel({ onPurge }) {
  const [sel, setSel] = useState({ chat: true, pending: true, bandit: false, healer: false, intel: false })
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const toggle = (id) => setSel(s => ({ ...s, [id]: !s[id] }))

  const purge = async () => {
    const what = Object.keys(sel).filter(k => sel[k] && k !== 'intel')
    if (!sel.intel && what.length === 0) return
    const label = [
      ...what.map(w => STORES.find(s => s.id === w)?.label),
      ...(sel.intel ? [`intel ${target || 'toutes cibles'}`] : []),
    ].join(' · ')
    if (!window.confirm(`SESSION NEUVE — purge définitive :\n${label}\n\nContinuer ?`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await axios.post(`${API_BASE}/admin/fresh`, {
        chat: !!sel.chat, pending: !!sel.pending, bandit: !!sel.bandit,
        healer: !!sel.healer, intel: !!sel.intel, target: (target || '').trim(),
      })
      setMsg({ ok: true, text: `✓ purgé : ${r.data.cleared.join(' · ') || 'rien sélectionné'}` })
      onPurge && onPurge()
    } catch (err) {
      setMsg({ ok: false, text: `✗ ${err.response?.data?.detail || err.message}` })
    } finally { setBusy(false) }
  }

  const Box = ({ id }) => (
    <label className="flex items-start gap-2 cursor-pointer group">
      <input type="checkbox" checked={!!sel[id]} onChange={() => toggle(id)}
        className="mt-0.5 accent-gold shrink-0" />
      <span className="min-w-0">
        <span className="block text-[11px] text-ink group-hover:text-volt transition-colors">
          {STORES.find(s => s.id === id)?.label}
        </span>
        <span className="block text-[9px] text-faint leading-snug">
          {STORES.find(s => s.id === id)?.hint}
        </span>
      </span>
    </label>
  )

  return (
    <div className="space-y-2.5">
      <div className="space-y-2">
        {STORES.map(s => <Box key={s.id} id={s.id} />)}
        <div className="border-t border-line pt-2">
          <label className="flex items-start gap-2 cursor-pointer group">
            <input type="checkbox" checked={!!sel.intel} onChange={() => toggle('intel')}
              className="mt-0.5 accent-gold shrink-0" />
            <span className="min-w-0 flex-1">
              <span className="block text-[11px] text-ink group-hover:text-volt transition-colors">
                intel Living Graph
              </span>
              <span className="block text-[9px] text-faint leading-snug">
                la carte vivante d'une cible (data/intel)
              </span>
            </span>
          </label>
          {sel.intel && (
            <input value={target} onChange={(e) => setTarget(e.target.value)}
              placeholder="domaine (vide = TOUTES les cibles)"
              className="mt-1.5 w-full bg-mist border border-line rounded-[10px] px-2 py-1 font-mono text-[10.5px] text-ink focus:outline-none focus:border-volt" />
          )}
        </div>
      </div>
      <button onClick={purge} disabled={busy}
        className="w-full btn-strike rounded-full border border-danger/50 text-danger font-disp font-semibold uppercase tracking-[.12em] text-[10.5px] px-3 py-2 hover:bg-danger hover:text-white transition-colors disabled:opacity-40">
        {busy ? '···' : '⚡ purger — session neuve'}
      </button>
      {msg && (
        <p className={`text-[10px] leading-snug ${msg.ok ? 'text-ok' : 'text-danger'}`}>
          {msg.text}
        </p>
      )}
      <p className="text-[9px] text-faint leading-relaxed">
        jamais touché : outils forgés, historique des missions (missions.db), rapports
      </p>
    </div>
  )
}
