import React, { useState, useRef, useEffect } from 'react'

/* ═══════════════════════════════════════════════════════════════════
   LA LIGNE SÉCURISÉE — the operator's private channel.
   Pre-mission: the strategist (tool-aware, tool-stripped) absorbs context
   and answers questions — everything becomes ORDRES DU COMMANDANT.
   Mid-mission: the same line delivers orders to the running agent.
   Frosted glass, hairlines, pills — la conversation, pas le chrome.
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
    <div className="flex flex-col h-full min-h-0 panel-frost overflow-hidden">
      {/* ── header — la ligne et son état ── */}
      <div className="px-4 py-3 border-b border-line flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${warMode ? 'bg-volt animate-pulse' : 'bg-cyan animate-pulse'}`} />
          <span className="eyebrow truncate">ligne sécurisée</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-slate">{label}</span>
          {warMode && chatLog.length > 0 && onClear && (
            <button onClick={onClear} title="nettoyer la salle de guerre"
              className="text-[12px] text-mut hover:text-danger transition-colors leading-none">×</button>
          )}
        </div>
      </div>

      {/* ── le fil — bulles du commandant et du stratège ── */}
      <div className="flex-1 min-h-0 overflow-y-auto px-3.5 py-3.5 space-y-2.5">
        {chatLog.length === 0 && (
          <div className="text-center py-12 px-3">
            <div className="font-disp text-xl text-faint mb-3">◇</div>
            <p className="text-[12px] text-mut leading-relaxed">
              {warMode
                ? <>La ligne est ouverte.<br />Donne ton contexte, pose tes questions,<br />répète tes contraintes —<br /><span className="text-cyan">ici, aucun outil ne tire.</span></>
                : <>L'agente est en campagne.<br />Tes mots arrivent au prochain round.</>}
            </p>
          </div>
        )}
        {chatLog.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[92%] rounded-2xl px-3.5 py-2.5 ${
              m.role === 'user'
                ? 'bg-voltlite border border-volt/30 rounded-tr-md'
                : 'bg-inset border border-line rounded-tl-md'
            }`}>
              <div className={`text-[9px] uppercase tracking-[.18em] mb-1.5 ${m.role === 'user' ? 'text-cyan' : 'text-mut'}`}>
                {m.role === 'user' ? 'commandant' : 'stratège'}{m.time ? ` · ${m.time}s` : ''}
              </div>
              <p className="text-[12.5px] leading-relaxed text-ash whitespace-pre-wrap break-words">
                {m.text}
              </p>
            </div>
          </div>
        ))}
        {(streaming || (busy && !streaming)) && (
          <div className="flex justify-start">
            <div className="max-w-[92%] rounded-2xl px-3.5 py-2.5 bg-inset border border-line rounded-tl-md">
              <div className="text-[9px] uppercase tracking-[.18em] mb-1.5 text-mut">
                stratège{streaming ? ' · écrit' : ' · réfléchit'}
              </div>
              {streaming
                ? <p className="text-[12.5px] leading-relaxed text-ash whitespace-pre-wrap break-words">
                    {streaming}<span className="inline-block w-1.5 h-3.5 bg-ash animate-pulse align-text-bottom ml-0.5" />
                  </p>
                : <p className="text-[12px] text-mut animate-pulse">···</p>}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* ── input — la voix ── */}
      <form onSubmit={send} className="p-3 border-t border-line flex items-end gap-2 shrink-0">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(e) }
          }}
          rows={2}
          placeholder={warMode
            ? 'ex : le keypool tourne sur FastAPI, 60 req/min max, focus /api/admin…'
            : 'ordre pour l\'agente…'}
          className="flex-1 bg-insetstrong border border-line rounded-ui px-3 py-2 text-[12.5px] leading-relaxed text-ink placeholder:text-faint focus:outline-none focus:border-volt/60 resize-none transition-colors"
        />
        <button type="submit" disabled={!draft.trim() || busy}
          className="pill-cta btn-strike px-4 py-2.5 text-[11px] shrink-0">
          ▸
        </button>
      </form>
    </div>
  )
}
