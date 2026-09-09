import React, { useState } from 'react'
import { t as _t } from '../i18n.js';
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
  { id: 'chat', label: _t('fresh_chat'), hint: _t('fresh_chat_hint') },
  { id: 'pending', label: _t('fresh_pending'), hint: _t('fresh_pending_hint') },
  { id: 'bandit', label: _t('fresh_bandit'), hint: _t('fresh_bandit_hint') },
  { id: 'healer', label: _t('fresh_healer'), hint: _t('fresh_healer_hint') },
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
    if (!window.confirm(_t('fresh_confirm', { label }))) return
    setBusy(true); setMsg(null)
    try {
      const r = await axios.post(`${API_BASE}/admin/fresh`, {
        chat: !!sel.chat, pending: !!sel.pending, bandit: !!sel.bandit,
        healer: !!sel.healer, intel: !!sel.intel, target: (target || '').trim(),
      })
      setMsg({ ok: true, text: _t('fresh_purged', { list: r.data.cleared.join(' · ') || _t('fresh_nothing') }) })
      onPurge && onPurge()
    } catch (err) {
      setMsg({ ok: false, text: `✗ ${err.response?.data?.detail || err.message}` })
    } finally { setBusy(false) }
  }

  const Box = ({ id }) => (
    <label className="flex items-start gap-2.5 cursor-pointer group">
      <input type="checkbox" checked={!!sel[id]} onChange={() => toggle(id)}
        className="mt-0.5 accent-volt shrink-0" />
      <span className="min-w-0">
        <span className="block text-[12px] text-ash group-hover:text-ink transition-colors">
          {STORES.find(s => s.id === id)?.label}
        </span>
        <span className="block text-[10px] text-faint leading-snug">
          {STORES.find(s => s.id === id)?.hint}
        </span>
      </span>
    </label>
  )

  return (
    <div className="space-y-3">
      <div className="space-y-2.5">
        {STORES.map(s => <Box key={s.id} id={s.id} />)}
        <div className="border-t border-line pt-2.5">
          <label className="flex items-start gap-2.5 cursor-pointer group">
            <input type="checkbox" checked={!!sel.intel} onChange={() => toggle('intel')}
              className="mt-0.5 accent-volt shrink-0" />
            <span className="min-w-0 flex-1">
              <span className="block text-[12px] text-ash group-hover:text-ink transition-colors">
                intel Living Graph
              </span>
              <span className="block text-[10px] text-faint leading-snug">
                la carte vivante d'une cible (data/intel)
              </span>
            </span>
          </label>
          {sel.intel && (
            <input value={target} onChange={(e) => setTarget(e.target.value)}
              placeholder="domaine (vide = TOUTES les cibles)"
              className="mt-2 w-full bg-insetstrong border border-line rounded-ui px-2.5 py-1.5 font-mono text-[11px] text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint" />
          )}
        </div>
      </div>
      <button onClick={purge} disabled={busy}
        className="w-full pill-ghost btn-strike !border-danger/50 !text-danger hover:!border-danger hover:!bg-dangertint px-3 py-2 text-[11px] uppercase tracking-[.12em]">
        {busy ? '···' : 'purger — session neuve'}
      </button>
      {msg && (
        <p className={`text-[11px] leading-snug ${msg.ok ? 'text-ok' : 'text-danger'}`}>
          {msg.text}
        </p>
      )}
      <p className="text-[10px] text-faint leading-relaxed">
        jamais touché : outils forgés, historique des missions (missions.db), rapports
      </p>
    </div>
  )
}
