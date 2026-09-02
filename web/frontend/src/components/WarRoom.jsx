import React, { useState, useRef, useEffect } from 'react'

/* ═══════════════════════════════════════════════════════════════════
   LA SALLE DE GUERRE — the one and only voice channel.
   LE DESIGN DU HÉROS « FRAPPER » EST LE DESIGN DE LA SALLE :
   · au repos — le crépuscule complet : spotlight, display, horizon,
     la barre d'ordre 52px avec la pill blanche encastrée.
   · en conversation — le fil au-dessus, la MÊME barre en dessous.
   L'ancien design (header « ligne sécurisée », petit input carré,
   placeholder ◇) est supprimé — une seule silhouette désormais.
   ═══════════════════════════════════════════════════════════════════ */

export default function WarRoom({ chatLog = [], onSend, busy = false,
                                  wsStatus = 'idle', missionId = null,
                                  onSendOperator = null, onClear = null,
                                  streaming = '' }) {
  const [draft, setDraft] = useState('')
  const [note, setNote] = useState(null)
  const endRef = useRef(null)
  const fileRef = useRef(null)
  const warMode = wsStatus === 'idle'
  const empty = chatLog.length === 0 && !streaming

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatLog.length, streaming])

  /* ── le plus — accrocher un fichier à l'ordre ── */
  const attach = async (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    try {
      const head = new Uint8Array(await f.slice(0, 1024).arrayBuffer())
      const kb = (f.size / 1024).toFixed(1)
      if (head.includes(0)) {
        setDraft(d => `${d ? d + '\n\n' : ''}[fichier binaire joint : ${f.name} — ${kb} Ko]`)
        setNote(`${f.name} — binaire, mention seule`)
      } else if (f.size > 200 * 1024) {
        setDraft(d => `${d ? d + '\n\n' : ''}[fichier trop volumineux pour la ligne : ${f.name} — ${kb} Ko]`)
        setNote(`${f.name} — > 200 Ko, mention seule`)
      } else {
        const text = await f.text()
        setDraft(d => `${d ? d + '\n\n' : ''}[fichier : ${f.name}]\n\`\`\`\n${text.trim()}\n\`\`\``)
        setNote(`${f.name} — ${kb} Ko accroché à l'ordre`)
      }
      setTimeout(() => setNote(null), 4000)
    } catch {
      setNote(`${f.name} — illisible`)
      setTimeout(() => setNote(null), 4000)
    }
  }

  const send = async (e) => {
    e.preventDefault()
    const msg = draft.trim()
    if (!msg || busy) return
    setDraft('')
    setNote(null)
    if (warMode && onSend) await onSend(msg)
    else if (!warMode && onSendOperator) {
      await onSendOperator(missionId, msg)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0 panel-frost relative overflow-hidden">
      {/* ── le fil — seulement quand il y a du sang dans la ligne ── */}
      {!empty && (
        <div className="flex-1 min-h-0 overflow-y-auto px-3.5 py-4 space-y-2.5 relative">
          {warMode && chatLog.length > 0 && onClear && (
            <button onClick={onClear} title="nettoyer la salle de guerre"
              className="absolute top-3 right-3 text-[12px] text-faint hover:text-danger transition-colors leading-none z-10">×</button>
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
      )}

      {/* ── le héros de veille — le crépuscule avant l'ordre (design frapper, intact) ── */}
      {empty && (
        <div className="flex-1 min-h-0 relative flex flex-col items-center justify-center text-center px-8 overflow-hidden">
          <div aria-hidden className="spotlight pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[560px] h-[280px] opacity-25" />
          <p className="eyebrow mb-5 relative">salle de guerre</p>
          <h2 className="display text-[32px] text-ink mb-4 relative">
            Un ordre, et la nuit se met au travail.
          </h2>
          <p className="text-[14px] leading-relaxed text-ash mb-8 relative max-w-2xl">
            {warMode
              ? <>Donne le contexte, la cible, les contraintes — le stratège répond,
                 trace le plan d'attaque, et rien ne tire sans ton verdict.</>
              : <>L'agente est en campagne.<br />Tes mots arrivent au prochain round.</>}
          </p>
          <div aria-hidden className="horizon h-[2px] w-44 mx-auto rounded-full opacity-80 relative" />
        </div>
      )}

      {/* ── la voix — LA barre du héros, devenue un vrai chat : + fichiers, ordre, frapper ── */}
      <form onSubmit={send} className="shrink-0 px-8 pb-8 pt-4 relative">
        <div className="relative max-w-xl mx-auto">
          {note && (
            <p className="absolute -top-6 left-2 right-2 text-[10.5px] text-cyan truncate tracking-[.04em] animate-fadeIn">{note}</p>
          )}
          <div className="relative flex items-end rounded-[28px] border border-line2 bg-insetstrong backdrop-blur focus-within:border-volt/60 transition-colors">
            <input ref={fileRef} type="file" className="hidden" onChange={attach} />
            <button type="button" onClick={() => fileRef.current?.click()} title="accrocher un fichier à l'ordre"
              className="shrink-0 my-[5px] ml-[5px] w-[42px] h-[42px] rounded-full flex items-center justify-center text-faint hover:text-cyan hover:bg-voltlite hover:border-volt/30 border border-transparent transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>
            <textarea
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(e) }
              }}
              rows={1}
              spellCheck="false"
              placeholder={warMode
                ? 'ton ordre au stratège — contexte, cible, contraintes…'
                : 'ordre pour l\'agente…'}
              className="flex-1 min-w-0 bg-transparent my-[5px] py-[11px] px-2 text-[13.5px] leading-relaxed text-ink placeholder:text-faint focus:outline-none resize-none max-h-[160px]"
            />
            <button type="submit" disabled={busy || !draft.trim()}
              className="pill-cta btn-strike shrink-0 my-[5px] mr-[5px] h-[42px] px-6 text-[12.5px] tracking-[.04em]">
              frapper
            </button>
          </div>
        </div>
        {empty && (
          <p className="mt-5 text-[11px] text-faint text-center tracking-[.06em]">
            le plan arrive ici — tu le corriges, tu l'approuves, la forge exécute · entrée pour envoyer
          </p>
        )}
      </form>
    </div>
  )
}
