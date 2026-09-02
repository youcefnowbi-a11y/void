import React, { useState, useRef, useEffect } from 'react'

/* ═══════════════════════════════════════════════════════════════════
   LA LIGNE SÉCURISÉE — the operator's private channel.
   Pre-mission: the strategist (tool-aware, tool-stripped) absorbs context
   and answers questions — everything becomes ORDRES DU COMMANDANT.
   Mid-mission: the same line delivers orders to the running agent.
   Bubbles, not logs: the operator speaks right, the counsel answers left.
   ═══════════════════════════════════════════════════════════════════ */

export default function WarRoom({ chatLog = [], onSend, busy = false,
                                  wsStatus = 'idle', missionId = null,
                                  onSendOperator = null, onClear = null,
                                  streaming = '' }) {
  const [draft, setDraft] = useState('')
  const endRef = useRef(null)
  const warMode = wsStatus === 'idle'

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatLog.length, streaming])

  const send = async (e) => {
    e.preventDefault()
    const msg = draft.trim()
    if (!msg || busy) return
    setDraft('')
    if (warMode && onSend) await onSend(msg)
    else if (!warMode && onSendOperator) {
      await onSendOperator(missionId, msg)
    }
  }

  const label = warMode ? 'stratège · salle de guerre'
              : wsStatus === 'running' ? 'agente · ligne directe'
              : 'agente · continuation'

  return (
    <div className="flex flex-col h-full panel-raised overflow-hidden">
      {/* ── header — la ligne et son état ── */}
      <div className="px-3 py-2.5 border-b border-line bg-wash flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${warMode ? 'bg-volt animate-pulse' : 'bg-cyan animate-pulse'}`} />
          <span className="eyebrow truncate">ligne sécurisée</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-faint">{label}</span>
          {warMode && chatLog.length > 0 && onClear && (
            <button onClick={onClear} title="nettoyer la salle de guerre"
              className="text-[11px] text-mut hover:text-danger transition-colors">×</button>
          )}
        </div>
      </div>

      {/* ── le fil — bulles du commandant et du stratège ── */}
      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-2.5">
        {chatLog.length === 0 && (
          <div className="text-center py-10 px-2">
            <div className="font-disp text-xl text-faint mb-2">◇</div>
            <p className="text-[11.5px] text-mut leading-relaxed">
              {warMode
                ? <>La ligne est ouverte.<br />Donne ton contexte, pose tes questions,<br />répète tes contraintes —<br /><span className="text-volt">ici, aucun outil ne tire.</span></>
                : <>L'agente est en campagne.<br />Tes mots arrivent au prochain round.</>}
            </p>
          </div>
        )}
        {chatLog.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[92%] rounded-xl px-3 py-2 ${
              m.role === 'user'
                ? 'bg-voltlite border border-volt/30 rounded-tr-sm'
                : 'bg-[#0E1E38]/60 border border-[#60A5FA]/25 rounded-tl-sm'
            }`}>
              <div className={`text-[9px] uppercase tracking-[.18em] mb-1 ${m.role === 'user' ? 'text-volt' : 'text-[#93C5FD]'}`}>
                {m.role === 'user' ? 'commandant' : 'stratège'}{m.time ? ` · ${m.time}s` : ''}
              </div>
              <p className="text-[12px] leading-relaxed text-slate whitespace-pre-wrap break-words">
                {m.text}
              </p>
            </div>
          </div>
        ))}
        {(streaming || (busy && !streaming)) && (
          <div className="flex justify-start">
            <div className="max-w-[92%] rounded-xl px-3 py-2 bg-[#0E1E38]/60 border border-[#60A5FA]/25 rounded-tl-sm">
              <div className="text-[9px] uppercase tracking-[.18em] mb-1 text-[#93C5FD]">
                stratège{streaming ? ' · écrit' : ' · réfléchit'}
              </div>
              {streaming
                ? <p className="text-[12px] leading-relaxed text-slate whitespace-pre-wrap break-words">
                    {streaming}<span className="inline-block w-1.5 h-3.5 bg-[#93C5FD] animate-pulse align-text-bottom ml-0.5" />
                  </p>
                : <p className="text-[12px] text-mut animate-pulse">···</p>}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* ── input — la voix ── */}
      <form onSubmit={send} className="p-2.5 border-t border-line bg-paper flex items-end gap-2 shrink-0">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(e) }
          }}
          rows={2}
          placeholder={warMode
            ? 'ex: le keypool tourne sur FastAPI, 60 req/min max, focus /api/admin…'
            : 'ordre pour l\'agente…'}
          className="flex-1 bg-mist border border-line rounded-[10px] px-2.5 py-1.5 text-[12px] leading-relaxed text-ink placeholder:text-faint focus:outline-none focus:border-volt resize-none"
        />
        <button type="submit" disabled={!draft.trim() || busy}
          className="btn-strike rounded-full bg-snow text-[#0A0A0A] font-disp font-semibold uppercase tracking-[.08em] text-[10.5px] px-3 py-2 disabled:opacity-40 shrink-0">
          {busy ? '…' : '▸'}
        </button>
      </form>
    </div>
  )
}
