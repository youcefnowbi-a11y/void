import React, { useState, useEffect } from 'react';
import axios from 'axios';
import LiveConsole from './components/LiveConsole.jsx';
import WarRoom from './components/WarRoom.jsx';
import FindingsLive from './components/FindingsLive.jsx';
import DirectToolRunner from './components/DirectToolRunner.jsx';
import PersonaPanel from './components/PersonaPanel.jsx';
import FreshSessionPanel from './components/FreshSessionPanel.jsx';
import { useMissionSocket } from './hooks/useMissionSocket.js';
import { API_BASE } from './api.js';

const DOC_NO = `VF-${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}${String(new Date().getDate()).padStart(2, '0')}`;

/* ═══════════════════════════════════════════════════════════════════
   VOIDFORGE — DIMENSION, deuxième édition. Reconstruit de zéro.
   Nav flottante détachée, verre dépoli, pills, hairlines, un violet
   en wash. DM Sans fait la voix, le mono fait la guerre.
   ═══════════════════════════════════════════════════════════════════ */

const Ic = {
  doc:   () => <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3h9l4 4v14H6z"/><path d="M10 10h6M10 14h6M10 18h3"/></svg>,
  stop:  () => <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>,
  chat:  () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 1 1 17 0z"/></svg>,
  gear:  () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>,
};

/* chiffres display — Geist, tabulaire, weight 500 */
function Stat({ value, label, tone = 'ink' }) {
  const color = tone === 'danger' ? 'text-danger' : tone === 'gold' ? 'text-gold' : 'text-ink';
  return (
    <div className="text-center py-4 px-2">
      <div className={`font-disp text-[22px] font-medium leading-none tabular-nums ${color}`}>{value}</div>
      <div className="mt-1.5 text-[10px] uppercase tracking-[.16em] text-mut">{label}</div>
    </div>
  );
}

function Section({ title, children, defaultOpen = false }) {
  return (
    <details className="panel group overflow-hidden" open={defaultOpen}>
      <summary className="px-4 py-3 flex items-center justify-between cursor-pointer select-none list-none hover:bg-white/[0.03] transition-colors">
        <span className="text-[12.5px] font-medium text-ink">{title}</span>
        <span className="text-[13px] text-faint group-open:text-cyan group-open:rotate-45 transition-all duration-200 shrink-0">+</span>
      </summary>
      <div className="px-4 pb-4 pt-3 border-t border-line">{children}</div>
    </details>
  );
}

/* le héros de veille — le crépuscule avant l'ordre */
function IdleHero({ onOrder, busy }) {
  const [order, setOrder] = useState('');
  const submit = (e) => {
    e.preventDefault();
    const t = order.trim();
    if (!t) return;
    setOrder('');
    onOrder(t);
  };
  return (
    <div className="panel-frost relative overflow-hidden px-8 py-14 animate-fadeIn">
      <div aria-hidden className="spotlight pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[560px] h-[280px] opacity-25" />
      <div className="relative max-w-2xl mx-auto text-center">
        <p className="eyebrow mb-5">voidforge · ops console</p>
        <h2 className="display text-[34px] text-ink mb-4">
          Un ordre, et la nuit se met au travail.
        </h2>
        <p className="text-[14px] leading-relaxed text-ash mb-8">
          Donne le contexte, la cible, les contraintes — le stratège répond,
          trace le plan d'attaque, et rien ne tire sans ton verdict.
        </p>
        <div aria-hidden className="horizon h-[2px] w-44 mx-auto mb-9 rounded-full opacity-80" />
        <form onSubmit={submit} className="relative max-w-xl mx-auto">
          <input
            value={order}
            onChange={(e) => setOrder(e.target.value)}
            placeholder="ex : cartographie le surface de attack-surface.example — focus exposés Supabase…"
            className="w-full h-[52px] rounded-full border border-line2 bg-black/40 backdrop-blur px-6 pr-36 text-[13.5px] text-ink placeholder:text-faint focus:outline-none focus:border-volt/60 transition-colors"
          />
          <button type="submit" disabled={busy || !order.trim()}
            className="pill-cta btn-strike absolute right-[5px] top-[5px] bottom-[5px] px-6 text-[12.5px] tracking-[.04em]">
            frapper
          </button>
        </form>
        <p className="mt-5 text-[11px] text-faint tracking-[.06em]">
          le plan arrive ici — tu le corriges, tu l'approuves, la forge exécute
        </p>
      </div>
    </div>
  );
}

function App() {
  const [mission, setMission] = useState('');
  const [reports, setReports] = useState([]);
  const [health, setHealth] = useState(null);
  const [provider, setProvider] = useState(null);
  const [provForm, setProvForm] = useState({ base_url: '', api_key: '', model: '', max_tokens: 2600 });
  const [provMsg, setProvMsg] = useState(null);
  const [isTestingProv, setIsTestingProv] = useState(false);
  const [reading, setReading] = useState(null);
  const [workspace, setWorkspace] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [toolsCount, setToolsCount] = useState(0);

  const {
    logs, findings, graph, stats,
    status: wsStatus, missionId, missionText, connected,
    reset, clearConsole, abortMission, sendOperatorMessage,
    pendingPlan, sendChatMessage, clearChat, chatLog, chatBusy, chatStreaming, approvePlan,
  } = useMissionSocket();
  const [editedPlan, setEditedPlan] = useState('');
  const [strikeMode, setStrikeMode] = useState('IA');
  const [showLeft, setShowLeft] = useState(true);
  const [leftTab, setLeftTab] = useState('chat'); // 'chat' | 'registres'

  // le plan arrive → le textarea s'arme pour l'édition (Option B)
  useEffect(() => {
    if (pendingPlan?.plan) setEditedPlan(pendingPlan.plan);
  }, [pendingPlan?.plan]);

  const fetchReports = () => axios.get(`${API_BASE}/reports`).then(r => setReports(r.data)).catch(() => {});
  const fetchHealth = () => axios.get(`${API_BASE}/health`).then(r => setHealth(r.data)).catch(() => setHealth(null));
  const fetchProvider = async () => {
    try {
      const r = await axios.get(`${API_BASE}/provider`);
      setProvider(r.data);
      setProvForm(f => ({ ...f, base_url: r.data.base_url || '', model: r.data.model || '',
                          max_tokens: r.data.max_tokens || 2600 }));
    } catch { setProvider(null); }
  };

  useEffect(() => {
    fetchHealth(); fetchReports(); fetchProvider();
    axios.get(`${API_BASE}/tools`).then(r => setToolsCount((r.data.tools || []).length)).catch(() => {});
    const t = setInterval(fetchHealth, 30000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (wsStatus !== 'running' || !stats.startedAt) { setElapsed(0); return; }
    const t0 = new Date(stats.startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - t0) / 1000));
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [wsStatus, stats.startedAt]);

  useEffect(() => {
    if (wsStatus === 'complete') {
      fetchReports();
      axios.get(`${API_BASE}/workspace`, { params: { mission: missionText } })
        .then(r => setWorkspace(r.data)).catch(() => {});
    }
  }, [wsStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  const rompre = async () => {
    if (!missionId) return;
    await abortMission(missionId);
  };

  const nouvelleSession = () => {
    reset();
    setMission('');
    setWorkspace(null);
  };

  const saveProvider = async (e) => {
    e.preventDefault();
    setIsTestingProv(true);
    setProvMsg({ ok: null, text: '⏳ ping « Reply with OK »...' });
    try {
      const cleanKey = provForm.api_key?.trim() || null;
      const mt = parseInt(provForm.max_tokens, 10);
      const r = await axios.post(`${API_BASE}/provider`, {
        base_url: provForm.base_url.trim(), api_key: cleanKey, model: provForm.model.trim(),
        chat_max_tokens: Number.isFinite(mt) ? mt : null,
      });
      setProvMsg({ ok: true, text: r.data.message });
      setProvForm(f => ({ ...f, api_key: '' }));
      fetchProvider();
    } catch (err) {
      setProvMsg({ ok: false, text: `✗ ${err.response?.data?.detail || err.message}` });
    } finally { setIsTestingProv(false); }
  };

  const openReport = async (name) => {
    setReading({ name, content: null });
    try {
      const r = await axios.get(`${API_BASE}/reports/${encodeURIComponent(name)}`);
      setReading({ name, content: r.data.content });
    } catch (err) {
      setReading({ name, content: `✗ lecture impossible : ${err.response?.data?.detail || err.message}` });
    }
  };

  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');
  const hbClass = wsStatus === 'running' ? 'running' : wsStatus === 'complete' ? 'complete' : wsStatus === 'error' ? 'error' : '';

  const inputCls = "w-full rounded-ui border border-line bg-white/[0.04] px-3 py-2 text-[13px] text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint";

  const idle = wsStatus === 'idle' && !pendingPlan;

  return (
    <div className="h-screen flex flex-col overflow-hidden relative">
      <div className={`heartbeat ${hbClass}`} aria-hidden />
      {/* spotlight d'ambiance — le crépuscule entre par la fenêtre */}
      <div aria-hidden className="spotlight pointer-events-none fixed -top-28 left-1/2 -translate-x-1/2 w-[640px] h-[240px] opacity-[0.13] z-0" />

      {/* ── nav flottante — la signature Dimension, détachée des bords (16px) ── */}
      <div className="shrink-0 px-4 pt-4 pb-3 relative z-10">
        <header className="nav-float h-12 px-5 flex items-center gap-3.5 shadow-nav">
          <h1 className="font-disp text-[15px] font-medium tracking-[-0.03em] shrink-0 relative">
            <span className="text-ink">VOID</span><span className="text-ash">FORGE</span>
            <span aria-hidden className="wash-violet absolute left-0 -bottom-[3px] h-[2px] w-full" />
          </h1>
          <span className="hidden xl:inline font-mono text-[9px] uppercase tracking-[.2em] text-faint shrink-0">{DOC_NO}</span>
          <div className="min-w-0 flex-1">
            {missionText
              ? <p className="text-[12.5px] text-ash truncate" title={missionText}>{missionText}</p>
              : <p className="text-[12.5px] text-faint truncate">le cœur veille — un ordre l'éveillera</p>}
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] uppercase tracking-[.14em] font-mono shrink-0
            ${wsStatus === 'running' ? 'border-volt/40 bg-voltlite text-cyan' : wsStatus === 'complete' ? 'border-gold/40 bg-goldtint text-gold' : wsStatus === 'error' ? 'border-danger/40 bg-dangertint text-danger' : 'border-line text-mut'}`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${wsStatus === 'running' ? 'bg-volt animate-pulse' : wsStatus === 'complete' ? 'bg-gold' : wsStatus === 'error' ? 'bg-danger' : 'bg-mut'}`} />
            {wsStatus === 'running' ? 'campagne' : wsStatus === 'complete' ? 'terminée' : wsStatus === 'error' ? 'rompue' : 'veille'}
          </span>
          {wsStatus === 'running' && (
            <span className="font-mono text-[11px] tabular-nums text-ash shrink-0">{mm}:{ss}</span>
          )}
          {wsStatus === 'running' && (
            <button type="button" onClick={rompre} title="rompre la campagne"
              className="btn-strike rounded-full border border-danger/50 text-danger px-2.5 py-1.5 flex items-center hover:bg-dangertint shrink-0">
              <Ic.stop />
            </button>
          )}
          {(wsStatus === 'complete' || wsStatus === 'error') && (
            <button type="button" onClick={nouvelleSession} title="nouvelle session"
              className="pill-ghost btn-strike px-4 py-1.5 text-[10.5px] uppercase tracking-[.12em] shrink-0">
              reset
            </button>
          )}
          <button onClick={() => {
            if (showLeft && leftTab === 'chat') setShowLeft(false);
            else { setShowLeft(true); setLeftTab('chat'); }
          }}
            title={showLeft && leftTab === 'chat' ? 'fermer la barre latérale' : 'ouvrir le chat'}
            className={`rounded-full px-2.5 py-1.5 border transition-colors shrink-0 ${showLeft && leftTab === 'chat' ? 'bg-voltlite text-cyan border-volt/30' : 'bg-white/[0.04] text-mut border-line hover:text-ink'}`}>
            <Ic.chat />
          </button>
          <button onClick={() => {
            if (showLeft && leftTab === 'registres') setShowLeft(false);
            else { setShowLeft(true); setLeftTab('registres'); }
          }}
            title={showLeft && leftTab === 'registres' ? 'fermer la barre latérale' : 'ouvrir les registres'}
            className={`rounded-full px-2.5 py-1.5 border transition-colors shrink-0 ${showLeft && leftTab === 'registres' ? 'bg-voltlite text-cyan border-volt/30' : 'bg-white/[0.04] text-mut border-line hover:text-ink'}`}>
            <Ic.gear />
          </button>
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${connected ? 'bg-ok' : 'bg-danger animate-pulse'}`} title={connected ? 'flux live' : 'flux coupé'} />
        </header>
      </div>

      {/* ── corps : SALON · CENTRE · REGISTRES ── */}
      <div className="relative z-10 flex flex-1 min-h-0 gap-3 px-4 pb-4">

        {/* ══ BARRE LATÉRALE — la ligne sécurisée ou les registres ══ */}
        {showLeft && (
          <aside className="w-[360px] shrink-0 min-h-0">
            {leftTab === 'chat' ? (
              <div className="h-full min-h-0">
                <WarRoom
                  chatLog={chatLog}
                  onSend={sendChatMessage}
                  busy={chatBusy}
                  wsStatus={wsStatus}
                  missionId={missionId}
                  onSendOperator={sendOperatorMessage}
                  onClear={clearChat}
                  streaming={chatStreaming}
                />
              </div>
            ) : (
              <div className="h-full min-h-0 panel p-3.5 space-y-3 overflow-y-auto">
                <Section title="rapports">
                  {reports.length === 0
                    ? <p className="text-[12.5px] text-mut">Aucun rapport archivé.</p>
                    : <ul className="divide-y divide-line max-h-48 overflow-y-auto">
                        {reports.map(r => (
                          <li key={r.name} onClick={() => openReport(r.name)}
                            className="py-2 px-1.5 -mx-1.5 rounded-ui flex items-center gap-2 group cursor-pointer hover:bg-white/[0.04] transition-colors">
                            <span className="text-faint group-hover:text-cyan transition-colors"><Ic.doc /></span>
                            <span className="text-[12.5px] text-ash group-hover:text-ink transition-colors truncate">{r.name.replace(/report_|\.md/g, '')}</span>
                            <span className="ml-auto font-mono text-[10px] text-faint shrink-0">{(r.size / 1024).toFixed(0)}K</span>
                          </li>
                        ))}
                      </ul>}
                </Section>

                <Section title="cerveau — provider">
                  <form onSubmit={saveProvider} className="space-y-2.5">
                    <input value={provForm.base_url} onChange={(e) => setProvForm(f => ({ ...f, base_url: e.target.value }))}
                      placeholder="https://api.deepseek.com/v1" className={inputCls} />
                    <input type="password" value={provForm.api_key} onChange={(e) => setProvForm(f => ({ ...f, api_key: e.target.value }))}
                      placeholder={provider?.api_key_masked ? `${provider.api_key_masked} (inchangée)` : 'sk-…'}
                      autoComplete="new-password" className={inputCls} />
                    <input value={provForm.model} onChange={(e) => setProvForm(f => ({ ...f, model: e.target.value }))}
                      placeholder="deepseek-chat" className={inputCls} />
                    <div className="flex items-center gap-2">
                      <label className="text-[10px] uppercase tracking-[.14em] text-mut shrink-0">
                        plafond chat
                      </label>
                      <input type="number" min="256" step="100"
                        value={provForm.max_tokens}
                        onChange={(e) => setProvForm(f => ({ ...f, max_tokens: e.target.value }))}
                        className={`${inputCls} w-24 shrink-0`} />
                      <span className="text-[10.5px] text-faint">tokens — missions non plafonnées</span>
                    </div>
                    <div className="flex items-center justify-between gap-2 pt-1">
                      <span className={`text-[11px] break-words flex-1 ${
                        provMsg?.ok === true ? 'text-ok' : provMsg?.ok === false ? 'text-danger' :
                        isTestingProv ? 'text-warn animate-pulse' : provider?.api_key_set ? 'text-mut' : 'text-danger'}`}>
                        {provMsg ? provMsg.text : provider?.api_key_set ? `clé ${provider.api_key_masked}` : 'aucune clé'}
                      </span>
                      <button type="submit" disabled={isTestingProv} className="pill-cta btn-strike px-5 py-1.5 text-[11px] uppercase tracking-[.1em] shrink-0">
                        {isTestingProv ? '...' : 'armer'}
                      </button>
                    </div>
                  </form>
                </Section>

                <Section title="masque — personnalité">
                  <PersonaPanel />
                </Section>

                <Section title="frappe directe — l'arsenal à la main" defaultOpen={false}>
                  <DirectToolRunner onToolExecuted={() => { fetchReports(); }} />
                </Section>

                <Section title="session neuve — purge mémoire" defaultOpen={false}>
                  <FreshSessionPanel
                    onPurge={() => { reset(); setMission(''); setWorkspace(null); setReading(null); }} />
                </Section>

                <p className="px-1 pt-1 pb-1 text-[9px] tracking-[.18em] text-faint uppercase">
                  forge opérative · forgé par voidforge
                </p>
              </div>
            )}
          </aside>
        )}

        {/* ══ CENTRE — LA SALLE DES MACHINES ══ */}
        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="space-y-4">

            {/* héros de veille — la forge dort, l'ordre l'éveille */}
            {idle && <IdleHero onOrder={(t) => { setMission(t); setShowLeft(true); setLeftTab('chat'); sendChatMessage(t); }} busy={chatBusy} />}

            {/* barre d'état — cinq chiffres */}
            <div className="panel grid grid-cols-5 divide-x divide-line overflow-hidden">
              <Stat value={wsStatus === 'running' ? mm + ':' + ss : '—'} label="chrono" />
              <Stat value={stats.rounds} label="rounds" />
              <Stat value={stats.toolsFired} label="frappes" />
              <Stat value={stats.findings} label="findings" tone={stats.findings > 0 ? 'danger' : 'ink'} />
              <Stat value={graph.nodes.length} label="nœuds" tone={wsStatus === 'complete' ? 'gold' : 'ink'} />
            </div>

            {/* LA CONSOLE — toujours vivante */}
            <LiveConsole logs={logs} status={wsStatus} onClear={clearConsole} />

            {/* PLAN EN ATTENTE — l'opérateur lit, corrige, tranche */}
            {pendingPlan && (
              <div className="panel overflow-hidden animate-fadeIn">
                <div className="relative px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
                  <span aria-hidden className="wash-violet absolute inset-x-0 top-0 h-[2px]" />
                  <span className="text-[13px] font-medium text-ink">Plan d'attaque — approbation requise</span>
                  <div className="flex items-center gap-1.5">
                    {['IA', 'Swarm'].map(m => (
                      <button key={m} type="button" onClick={() => setStrikeMode(m)}
                        className={`px-3.5 py-1.5 rounded-full text-[11px] uppercase tracking-[.1em] transition-all
                          ${strikeMode === m ? 'bg-snow text-[#0A0A0A] font-medium' : 'border border-line text-mut hover:text-ink'}`}>
                        {m.toLowerCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <textarea value={editedPlan} onChange={(e) => setEditedPlan(e.target.value)}
                  rows={16}
                  className="w-full terminal-bg text-[11.5px] leading-relaxed text-ink p-4 resize-y focus:outline-none border-0 bg-transparent"
                  spellCheck="false" />
                <div className="px-5 py-3.5 border-t border-line bg-white/[0.03] flex items-center justify-between gap-3">
                  <span className="text-[11px] text-mut">
                    corrige librement — ta version part à la frappe · mode {strikeMode.toLowerCase()}
                    {strikeMode === 'Swarm' ? ' : subagents du plan' : ' : agent unique plan-guidé'}
                  </span>
                  <div className="flex items-center gap-2">
                    <button onClick={() => approvePlan(false, '', '')}
                      className="pill-ghost btn-strike px-4 py-1.5 text-[11px] uppercase tracking-[.1em] hover:!border-danger hover:!text-danger">
                      rejeter
                    </button>
                    <button onClick={() => approvePlan(true, editedPlan, strikeMode)}
                      disabled={!editedPlan.trim()}
                      className="pill-cta btn-strike px-5 py-1.5 text-[11px] uppercase tracking-[.1em]">
                      approuver — lancer la frappe
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* rapport de puissance — quand la campagne ferme */}
            {wsStatus === 'complete' && workspace?.exists && (
              <div className="panel overflow-hidden animate-fadeIn">
                <div aria-hidden className="horizon h-[2px] w-full" />
                <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3">
                  <span className="text-[13px] font-medium text-ink">Rapport de puissance — missions/{workspace.target}/</span>
                  <span className="font-mono text-[10.5px] text-mut">
                    {workspace.ledger_lines} entrées · {workspace.findings.length} findings · {workspace.extractions.length} extractions
                  </span>
                </div>
                <div className="grid md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-line">
                  <pre className="terminal-bg p-4 m-0 whitespace-pre-wrap break-words text-[12px] max-h-[320px] overflow-y-auto">{workspace.power_report || '⏳'}</pre>
                  <div className="p-4 space-y-4 max-h-[320px] overflow-y-auto">
                    <div>
                      <p className="eyebrow mb-2">findings</p>
                      {workspace.findings.length === 0
                        ? <p className="font-mono text-[11.5px] text-mut">aucun — cible dure.</p>
                        : <ul className="space-y-1">{workspace.findings.map(f => (
                            <li key={f} className="font-mono text-[11.5px] text-ash truncate">▸ {f}</li>))}
                          </ul>}
                    </div>
                    <div>
                      <p className="eyebrow mb-2">extractions ({workspace.extractions.length})</p>
                      <ul className="space-y-1 max-h-28 overflow-y-auto">{workspace.extractions.slice(0, 12).map(x => (
                        <li key={x} className="font-mono text-[11.5px] text-ash truncate">▸ {x}</li>))}
                      </ul>
                    </div>
                    {workspace.final_report && (
                      <button onClick={() => setReading({ name: 'rapport final', content: workspace.final_report })}
                        className="pill-cta btn-strike px-4 py-1.5 text-[11px] uppercase tracking-[.1em]">
                        rapport final
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* findings — que quand il y a du sang sur le sol */}
            {findings.length > 0 && <FindingsLive findings={findings} />}
          </div>
        </main>
      </div>

      {reading && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4 md:p-8" onClick={() => setReading(null)}>
          <div className="w-full max-w-3xl max-h-[85vh] panel flex flex-col overflow-hidden animate-fadeIn" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b border-line flex items-center justify-between gap-3">
              <span className="font-mono text-[11px] uppercase tracking-[.16em] text-ash truncate">{reading.name}</span>
              <button onClick={() => setReading(null)} className="pill-cta btn-strike px-4 py-1.5 text-[10.5px] uppercase tracking-[.1em] shrink-0">fermer</button>
            </div>
            <pre className="flex-1 overflow-y-auto terminal-bg p-4 m-0 whitespace-pre-wrap break-words">{reading.content ?? '⏳ chargement…'}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
