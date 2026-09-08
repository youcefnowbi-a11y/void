import React, { useState, useRef, useEffect, useMemo } from 'react';
import MarkdownMessage from './MarkdownMessage.jsx';
import PayloadMessage from './PayloadMessage.jsx';

const STARTER_ICONS = {
  recon: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-cyan">
      <circle cx="12" cy="12" r="10"/>
      <line x1="22" y1="12" x2="18" y2="12"/>
      <line x1="6" y1="12" x2="2" y2="12"/>
      <line x1="12" y1="6" x2="12" y2="2"/>
      <line x1="12" y1="22" x2="12" y2="18"/>
    </svg>
  ),
  auth: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-volt">
      <circle cx="7.5" cy="15.5" r="5.5"/>
      <path d="m21 2-9.6 9.6"/>
      <path d="m15.5 7.5 3 3"/>
    </svg>
  ),
  smash: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-warn">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
};

const STARTERS = [
  {
    id: 'recon',
    title: 'Reconnaissance Furtive',
    desc: 'Cartographie passive des sous-domaines, ports et technologies exposées.',
    prompt: '/recon https://target.com cartographie l\'ensemble des sous-domaines et endpoints exposés'
  },
  {
    id: 'auth',
    title: 'Audit de Session & Auth',
    desc: 'Analyse des flux Clerk/JWT, cookies de session et contrôle d\'accès (IDOR).',
    prompt: '/auth analyse les tokens de session et vérifie les failles de contrôle d\'accès'
  },
  {
    id: 'smash',
    title: 'Choc de Concurrence',
    desc: 'Tests de race condition sur les endpoints sensibles (coupons, double débit).',
    prompt: '/smash teste les race conditions sur les endpoints de débit et d\'attribution'
  }
];

const SLASH_COMMANDS = [
  { cmd: '/recon', desc: 'Cartographie furtive & reconnaissance DNS/HTTP', example: '/recon https://target.com' },
  { cmd: '/auth', desc: 'Audit des flux d\'authentification Clerk & cookies', example: '/auth vérifie les sessions' },
  { cmd: '/smash', desc: 'Test de race condition & requêtes concurrentes', example: '/smash test coupons simultanés' },
  { cmd: '/crawl', desc: 'Extraction des routes SPA & secrets côté client', example: '/crawl https://target.com' },
  { cmd: '/report', desc: 'Compilation immédiate du rapport d\'engagement', example: '/report' },
  { cmd: '/clear', desc: 'Nettoyer la salle de guerre', example: '/clear' },
];

export default function WarRoom({
  chatLog = [],
  onSend,
  busy = false,
  wsStatus = 'idle',
  missionId = null,
  onSendOperator = null,
  onClear = null,
  streaming = '',
}) {
  const [draft, setDraft] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [note, setNote] = useState(null);
  const [pinned, setPinned] = useState(true);
  const [copiedIndex, setCopiedIndex] = useState(null);

  const endRef = useRef(null);
  const chatContainerRef = useRef(null);
  const fileRef = useRef(null);
  const textareaRef = useRef(null);

  const warMode = wsStatus === 'idle';
  const empty = chatLog.length === 0 && !streaming;

  // Détection du scroll de l'utilisateur
  const handleChatScroll = () => {
    const el = chatContainerRef.current;
    if (!el) return;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    setPinned(isAtBottom);
  };

  // Scroll automatique uniquement si l'utilisateur est pinned en bas
  useEffect(() => {
    if (pinned && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatLog.length, streaming, pinned]);

  // Pièces jointes sous forme de chips
  const attach = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    try {
      const head = new Uint8Array(await f.slice(0, 1024).arrayBuffer());
      const kb = (f.size / 1024).toFixed(1);
      if (head.includes(0)) {
        setAttachments(prev => [
          ...prev,
          { id: Date.now() + Math.random(), name: f.name, kb, isBinary: true, text: `[fichier binaire joint : ${f.name} — ${kb} Ko]` }
        ]);
        setNote(`${f.name} — binaire joint`);
      } else if (f.size > 200 * 1024) {
        setAttachments(prev => [
          ...prev,
          { id: Date.now() + Math.random(), name: f.name, kb, isBinary: true, text: `[fichier > 200 Ko joint : ${f.name} — ${kb} Ko]` }
        ]);
        setNote(`${f.name} — > 200 Ko joint`);
      } else {
        const text = await f.text();
        setAttachments(prev => [
          ...prev,
          { id: Date.now() + Math.random(), name: f.name, kb, isBinary: false, text }
        ]);
        setNote(`${f.name} (${kb} Ko) prêt à l'envoi`);
      }
      setTimeout(() => setNote(null), 3500);
    } catch {
      setNote(`${f.name} — lecture impossible`);
      setTimeout(() => setNote(null), 3500);
    }
  };

  const removeAttachment = (id) => {
    setAttachments(prev => prev.filter(a => a.id !== id));
  };

  // Gestion des commandes Slash
  const isSlash = draft.startsWith('/');
  const filteredCommands = useMemo(() => {
    if (!isSlash) return [];
    const q = draft.slice(1).toLowerCase().split(' ')[0];
    return SLASH_COMMANDS.filter(c => c.cmd.slice(1).toLowerCase().startsWith(q));
  }, [draft, isSlash]);
  const [slashIdx, setSlashIdx] = useState(0);

  const applySlashCommand = (cmdObj) => {
    setDraft(cmdObj.example + ' ');
    setSlashIdx(0);
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.style.height = 'auto';
    }
  };

  const copyMessage = (text, idx) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIndex(idx);
      setTimeout(() => setCopiedIndex(null), 2000);
    });
  };

  const send = async (e) => {
    e.preventDefault();
    const rawMsg = draft.trim();
    if ((!rawMsg && attachments.length === 0) || busy) return;

    // Commande rapide /clear
    if (rawMsg === '/clear') {
      if (onClear) onClear();
      setDraft('');
      return;
    }

    let finalPayload = rawMsg;
    if (attachments.length > 0) {
      const filesBlocks = attachments.map(a =>
        a.isBinary
          ? a.text
          : `[fichier : ${a.name}]\n\`\`\`\n${a.text.trim()}\n\`\`\``
      ).join('\n\n');
      finalPayload = finalPayload ? `${finalPayload}\n\n${filesBlocks}` : filesBlocks;
    }

    setDraft('');
    setAttachments([]);
    setNote(null);
    setPinned(true);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    if (warMode && onSend) await onSend(finalPayload);
    else if (!warMode && onSendOperator) {
      await onSendOperator(missionId, finalPayload);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 panel-frost relative overflow-hidden">
      {/* ── LE FIL DE CONVERSATION ── */}
      {!empty && (
        <div
          ref={chatContainerRef}
          onScroll={handleChatScroll}
          className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3 relative select-text"
        >
          {warMode && chatLog.length > 0 && onClear && (
            <button
              onClick={onClear}
              title="Nettoyer la salle de guerre"
              className="absolute top-3 right-3 w-6 h-6 rounded-full flex items-center justify-center text-faint hover:text-danger hover:bg-dangertint/30 transition-colors z-10 text-[13px]"
            >
              ×
            </button>
          )}

          {chatLog.map((m, i) => {
            const isUser = m.role === 'user';
            return (
              <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'} group`}>
                <div
                  className={`max-w-[92%] sm:max-w-[85%] rounded-2xl px-4 py-3 shadow-sm relative transition-all ${
                    isUser
                      ? 'bg-wash/90 border border-line2 rounded-tr-md'
                      : 'bg-inset/70 border border-line rounded-tl-md'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3 mb-1.5 select-none">
                    <span
                      className={`text-[9.5px] uppercase tracking-[.18em] font-medium font-mono ${
                        isUser ? 'text-cyan' : 'text-mut'
                      }`}
                    >
                      {isUser ? 'commandant' : 'stratège'}{m.time ? ` · ${m.time}s` : ''}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyMessage(m.text, i)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-[9.5px] text-faint hover:text-ink font-mono uppercase tracking-wider px-1 py-0.5 rounded"
                      title="Copier le message brut"
                    >
                      {copiedIndex === i ? 'copié ✓' : 'copier'}
                    </button>
                  </div>
                  <PayloadMessage text={m.text} />
                </div>
              </div>
            );
          })}

          {(streaming || (busy && !streaming)) && (
            <div className="flex justify-start">
              <div className="max-w-[92%] sm:max-w-[85%] rounded-2xl px-4 py-3 bg-inset/70 border border-line rounded-tl-md shadow-sm">
                <div className="text-[9.5px] uppercase tracking-[.18em] mb-1.5 text-mut font-mono flex items-center gap-1.5 select-none">
                  <span className="w-1.5 h-1.5 rounded-full bg-volt animate-pulse" />
                  <span>stratège{streaming ? ' · transmission' : ' · réflexion'}</span>
                </div>
                {streaming ? (
                  <div className="relative">
                    <MarkdownMessage content={streaming} isStreaming={true} />
                    <span className="inline-block w-1.5 h-3.5 bg-volt align-middle ml-1 animate-pulse" />
                  </div>
                ) : (
                  <p className="text-[12px] text-mut animate-pulse">···</p>
                )}
              </div>
            </div>
          )}

          <div ref={endRef} />

          {/* Pastille flottante si l'utilisateur a scrollé vers le haut */}
          {!pinned && (
            <div className="sticky bottom-2 flex justify-center z-20 pointer-events-none">
              <button
                type="button"
                onClick={() => {
                  setPinned(true);
                  endRef.current?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="pointer-events-auto pill-solid btn-strike px-3.5 py-1 text-[10px] uppercase tracking-[.12em] shadow-lg animate-fadeIn flex items-center gap-1.5"
              >
                <span>↓</span>
                <span>reprendre le fil</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── ÉTAT VIDE (HUB D'ASSAUT & STARTERS) ── */}
      {empty && (
        <div className="flex-1 min-h-0 relative flex flex-col items-center justify-center text-center px-6 py-6 overflow-y-auto">
          <div aria-hidden className="spotlight pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[560px] h-[280px] opacity-25" />
          
          {/* Logo d'Obsidienne & Halo respirant */}
          <div
            className="relative mb-3 group cursor-pointer"
            onClick={() => textareaRef.current?.focus()}
            title="Cliquer pour armer la saisie"
          >
            <div className="w-14 h-14 rounded-full border border-line bg-wash/80 p-2.5 flex items-center justify-center shadow-lg transition-transform group-hover:scale-105 duration-300">
              <img src="/voidforge-white.png" alt="VOIDFORGE Logo" className="w-full h-full object-contain dark:block hidden drop-shadow-[0_0_12px_rgba(167,139,250,0.4)]" />
              <img src="/voidforge-dark.png" alt="VOIDFORGE Logo" className="w-full h-full object-contain dark:hidden block drop-shadow-[0_0_12px_rgba(167,139,250,0.4)]" />
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-volt border-2 border-paper animate-pulse" title="Système prêt à l'assaut" />
          </div>

          <p className="eyebrow mb-1.5 relative">salle de guerre</p>
          <h2 className="display text-[24px] sm:text-[28px] text-ink mb-2 tracking-tight relative">
            Un ordre, et la nuit se met au travail.
          </h2>
          <p className="text-[12.5px] leading-relaxed text-ash mb-5 relative max-w-lg">
            {warMode ? (
              <>Donne le contexte, la cible, ou sélectionne un protocole tactique ci-dessous pour lancer l'offensive autonome :</>
            ) : (
              <>L'agente est en campagne active. Tes ordres arrivent au prochain cycle.</>
            )}
          </p>

          {/* Cartes d'Assaut Rapide (Starters) */}
          {warMode && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 max-w-2xl w-full text-left mb-4 animate-fadeIn">
              {STARTERS.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setDraft(s.prompt);
                    if (textareaRef.current) {
                      textareaRef.current.focus();
                      textareaRef.current.style.height = 'auto';
                      textareaRef.current.style.height = '64px';
                    }
                  }}
                  className="rounded-card border border-line hover:border-volt/50 bg-wash/50 hover:bg-wash p-3 space-y-1.5 transition-all group text-left shadow-xs hover:shadow-md hover:-translate-y-0.5"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-md bg-wash border border-line flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                      {STARTER_ICONS[s.id]}
                    </span>
                    <span className="text-[11.5px] font-medium text-ink tracking-tight">{s.title}</span>
                  </div>
                  <p className="text-[10.5px] text-ash leading-relaxed line-clamp-2 font-sans">
                    {s.desc}
                  </p>
                  <span className="inline-flex items-center gap-1 text-[9.5px] font-mono text-cyan tracking-wider uppercase opacity-80 group-hover:opacity-100">
                    amorcer <span>→</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          <div aria-hidden className="horizon h-[2px] w-44 mx-auto rounded-full opacity-80 relative" />
        </div>
      )}

      {/* ── BARRE DE SAISIE DE L'ORDRE ── */}
      <form onSubmit={send} className="shrink-0 px-6 pb-6 pt-2 relative">
        <div className="relative max-w-2xl mx-auto">
          {note && (
            <p className="absolute -top-6 left-2 right-2 text-[10.5px] text-cyan truncate tracking-[.04em] animate-fadeIn">
              {note}
            </p>
          )}

          {/* Menu flottant des Commandes Slash (/) */}
          {isSlash && filteredCommands.length > 0 && (
            <div className="absolute bottom-full mb-2.5 left-0 right-0 rounded-card border border-line bg-paper/95 backdrop-blur-xl shadow-2xl p-2 z-40 animate-fadeIn space-y-1">
              <div className="px-2 py-1 border-b border-line/60 flex items-center justify-between text-[10px] uppercase font-mono text-faint select-none">
                <span>commandes tactiques ({filteredCommands.length})</span>
                <span>↑↓ naviguer · entrée choisir</span>
              </div>
              <div className="max-h-[220px] overflow-y-auto space-y-0.5 py-1">
                {filteredCommands.map((c, idx) => (
                  <button
                    key={c.cmd}
                    type="button"
                    onClick={() => applySlashCommand(c)}
                    className={`w-full text-left px-3 py-2 rounded-lg flex items-center justify-between gap-3 text-[12px] font-mono transition-colors ${
                      slashIdx === idx
                        ? 'bg-voltlite border border-volt/40 text-ink'
                        : 'hover:bg-hover text-ash hover:text-ink'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-cyan font-bold">{c.cmd}</span>
                      <span className="text-ash truncate text-[11.5px] font-sans">{c.desc}</span>
                    </div>
                    <span className="text-[10px] text-faint shrink-0 hidden sm:inline">{c.example}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chips des fichiers attachés */}
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2 px-1 animate-fadeIn">
              {attachments.map(att => (
                <span
                  key={att.id}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono border border-line bg-paper/90 text-ash shadow-sm"
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-cyan shrink-0">
                    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  <span className="truncate max-w-[180px]">{att.name}</span>
                  <span className="text-[9.5px] text-faint">({att.kb}K)</span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(att.id)}
                    className="ml-0.5 text-faint hover:text-danger leading-none text-xs transition-colors"
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="relative flex items-end rounded-[28px] border border-line2 bg-insetstrong backdrop-blur focus-within:border-volt/60 transition-colors shadow-sm">
            <input ref={fileRef} type="file" className="hidden" onChange={attach} />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              title="Accrocher un fichier à l'ordre"
              className="shrink-0 my-[5px] ml-[5px] w-[42px] h-[42px] rounded-full flex items-center justify-center text-faint hover:text-cyan hover:bg-voltlite hover:border-volt/30 border border-transparent transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
              }}
              onKeyDown={(e) => {
                // Navigation dans les commandes slash
                if (isSlash && filteredCommands.length > 0) {
                  if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    setSlashIdx(prev => (prev + 1) % filteredCommands.length);
                    return;
                  }
                  if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    setSlashIdx(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
                    return;
                  }
                  if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey && filteredCommands[slashIdx])) {
                    if (draft.trim() === filteredCommands[slashIdx].cmd) {
                      e.preventDefault();
                      applySlashCommand(filteredCommands[slashIdx]);
                      return;
                    }
                  }
                }

                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(e);
                }
              }}
              rows={1}
              spellCheck="false"
              placeholder={
                warMode
                  ? 'ton ordre au stratège (tape / pour les commandes rapides)…'
                  : "ordre pour l'agente…"
              }
              className="flex-1 min-w-0 bg-transparent my-[5px] py-[11px] px-2 text-[13.5px] leading-relaxed text-ink placeholder:text-faint focus:outline-none resize-none max-h-[160px]"
            />
            <button
              type="submit"
              disabled={busy || (!draft.trim() && attachments.length === 0)}
              className="pill-cta btn-strike shrink-0 my-[5px] mr-[5px] h-[42px] px-6 text-[12.5px] tracking-[.04em]"
            >
              frapper
            </button>
          </div>
        </div>

        {empty && (
          <p className="mt-3 text-[10.5px] text-faint text-center tracking-[.06em]">
            tape <span className="font-mono text-cyan">/</span> pour voir les commandes rapides · entrée pour envoyer
          </p>
        )}
      </form>
    </div>
  );
}
