import React, { useState, useEffect } from 'react';
import axios from 'axios';
import LiveConsole from './components/LiveConsole.jsx';
import WarRoom from './components/WarRoom.jsx';
import FindingsLive from './components/FindingsLive.jsx';
import SurfaceMap from './components/SurfaceMap.jsx';
import AttackGraph from './components/AttackGraph.jsx';
import FindingsVault from './components/FindingsVault.jsx';
import Dashboard from './components/Dashboard.jsx';
import SessionSidebar from './components/SessionSidebar.jsx';
import DirectToolRunner from './components/DirectToolRunner.jsx';
import PersonaPanel from './components/PersonaPanel.jsx';
import FreshSessionPanel from './components/FreshSessionPanel.jsx';
import { useMissionSocket } from './hooks/useMissionSocket.js';
import { API_BASE } from './api.js';
import { t as _t, setLang as _setLang } from './i18n.js';

const DOC_NO = `VF-${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}${String(new Date().getDate()).padStart(2, '0')}`;

/* ═══════════════════════════════════════════════════════════════════
   VOIDFORGE — DIMENSION. La géographie du pont (v4) :
   · CENTRE       — LA SALLE DE GUERRE. Tout s'y passe : la veille (héros
                    intégré au fil), la conversation, le plan en verdict.
   · DROITE       — la console de campagne, à l'activité seulement :
                    stats, feed, findings, rapport de puissance.
   · BAS-GAUCHE   — paramètres : le tiroir des registres (rapports,
                    cerveau, masque, arsenal, purge), un flottant discret.
   Deux thèmes : crépuscule (défaut) et aurore — mêmes tokens, autre heure.
   ═══════════════════════════════════════════════════════════════════ */

const Ic = {
  doc:   () => <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3h9l4 4v14H6z"/><path d="M10 10h6M10 14h6M10 18h3"/></svg>,
  stop:  () => <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>,
  gear:  () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  term:  () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>,
  sun:   () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="4.9" y1="4.9" x2="6.3" y2="6.3"/><line x1="17.7" y1="17.7" x2="19.1" y2="19.1"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/><line x1="4.9" y1="19.1" x2="6.3" y2="17.7"/><line x1="17.7" y1="6.3" x2="19.1" y2="4.9"/></svg>,
  moon:  () => <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>,
};

/* chiffres display — Geist, tabulaire, weight 500 */
function Stat({ value, label, tone = 'ink' }) {
  const color = tone === 'danger' ? 'text-danger' : tone === 'gold' ? 'text-gold' : 'text-ink';
  return (
    <div className="text-center py-3 px-1">
      <div className={`font-disp text-[18px] font-medium leading-none tabular-nums ${color}`}>{value}</div>
      <div className="mt-1 text-[10px] uppercase tracking-[.14em] text-mut font-mono">{label}</div>
    </div>
  );
}

function Section({ title, children, defaultOpen = false }) {
  return (
    <details className="panel group overflow-hidden" open={defaultOpen}>
      <summary className="px-4 py-3 flex items-center justify-between cursor-pointer select-none list-none hover:bg-hover transition-colors">
        <span className="text-[13px] font-medium text-ink">{title}</span>
        <span className="text-[13px] text-faint group-open:text-cyan group-open:rotate-45 transition-all duration-200 shrink-0">+</span>
      </summary>
      <div className="px-4 pb-4 pt-3 border-t border-line">{children}</div>
    </details>
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
  const [showParams, setShowParams] = useState(false);
  const [paramsTab, setParamsTab] = useState('cerveau');

  const {
    logs, findings, graph, stats,
    status: wsStatus, missionId, missionText, connected,
    reset, clearConsole, abortMission, sendOperatorMessage,
    pendingPlan, sendChatMessage, clearChat, chatLog, chatBusy, chatStreaming, approvePlan,
  } = useMissionSocket();
  const [editedPlan, setEditedPlan] = useState('');
  const [strikeMode, setStrikeMode] = useState('IA');

  /* ── panneaux & établi ── */
  const [consolePinned, setConsolePinned] = useState(null); // null = auto (l'activité décide)
  const hasActivity = logs.length > 0 || chatLog.length > 0 || wsStatus !== 'idle';
  const consoleOpen = consolePinned !== null ? consolePinned : hasActivity;
  const [workbenchTab, setWorkbenchTab] = useState('console'); // 'console' | 'surface' | 'findings'
  const [showSidebar, setShowSidebar] = useState(false);

  // Raccourci Ctrl+B / Cmd+B pour ouvrir/fermer la barre latérale des sessions
  useEffect(() => {
    const handleKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setShowSidebar(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  /* ── thème — crépuscule (Dark Mode permanent par défaut) ── */
  const theme = 'crepuscule';
  useEffect(() => {
    document.documentElement.dataset.theme = 'crepuscule';
    localStorage.setItem('vf-theme', 'crepuscule');
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) metaTheme.setAttribute('content', '#0A0A0A');
  }, []);

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

  // i18n boot: the product language comes from the same knob the
  // backend reads (provider.yaml). One fetch at mount, that's all.
  useEffect(() => {
    axios.get(`${API_BASE}/provider`)
      .then(r => _setLang(r.data?.language || 'en')).catch(() => {});
  }, []);

  useEffect(() => {
    if (wsStatus === 'complete') {
      fetchReports();
      axios.get(`${API_BASE}/workspace`, { params: { mission: missionText } })
        .then(r => setWorkspace(r.data)).catch(() => {});
    }
  }, [wsStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (reading) setReading(null);
        else if (showParams) setShowParams(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [reading, showParams]);

  const rompre = async () => {
    if (!missionId) return;
    await abortMission(missionId);
  };

  const nouvelleSession = () => {
    reset();
    if (clearChat) clearChat();
    setMission('');
    setWorkspace(null);
    setConsolePinned(null); // la console se rendort avec la session
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
      setReading({ name, content: `✗ unreadable: ${err.response?.data?.detail || err.message}` });
    }
  };

  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');
  const hbClass = wsStatus === 'running' ? 'running' : wsStatus === 'complete' ? 'complete' : wsStatus === 'error' ? 'error' : '';

  const inputCls = "w-full rounded-ui border border-line bg-inset px-3 py-2 text-[13px] text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint";

  return (
    <div className="h-screen flex flex-col overflow-hidden relative">
      <div className={`heartbeat ${hbClass}`} aria-hidden />

      {/* ── Fond immersif Matrix Cyber Corridor ── */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 bg-cover bg-center bg-no-repeat opacity-50 transition-opacity duration-700"
        style={{
          backgroundImage: "url('/matrix-bg.jpg')",
          filter: "saturate(1.2) brightness(0.95)"
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background: "radial-gradient(ellipse at center, rgba(10, 10, 10, 0.18) 0%, rgba(10, 10, 10, 0.78) 100%)"
        }}
      />

      {/* spotlight d'ambiance — le crépuscule entre par la fenêtre */}
      <div aria-hidden className="spotlight pointer-events-none fixed -top-28 left-1/2 -translate-x-1/2 w-[640px] h-[240px] opacity-[0.13] z-0" />

      {/* ── nav flottante — la signature Dimension, détachée des bords (16px) ── */}
      <div className="shrink-0 px-4 pt-4 pb-3 relative z-10">
        <header className="nav-float h-12 px-5 flex items-center gap-3.5">
          <div className="flex items-center gap-2.5 shrink-0">
            <img
              src="/voidforge-white.png"
              alt="REDACTED Logo"
              className="w-7 h-7 object-contain transition-transform duration-300 hover:scale-110 drop-shadow-[0_0_8px_rgba(167,139,250,0.35)]"
            />
            <h1 className="font-disp text-[15px] font-medium tracking-[.08em] shrink-0 relative">
              <span className="text-ink font-bold">REDACTED</span>
              <span aria-hidden className="wash-violet absolute left-0 -bottom-[3px] h-[2px] w-full" />
            </h1>
          </div>
          <span className="hidden xl:inline font-mono text-[10px] uppercase tracking-[.2em] text-faint shrink-0">{DOC_NO}</span>
          
          {/* Chip Provider & Modèle Tactique */}
          <button
            type="button"
            onClick={() => { setShowParams(true); setParamsTab('cerveau'); }}
            title="Intelligence Provider — click to configure"
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-mono shrink-0 transition-all hover:border-line2 ${
              !provider || !provider.api_key_set
                ? 'border-danger/50 bg-dangertint text-danger animate-pulse'
                : 'border-line bg-wash/60 text-ash hover:text-ink'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${!provider || !provider.api_key_set ? 'bg-danger' : 'bg-ok'}`} />
            <span className="truncate max-w-[130px]">
              {!provider || !provider.api_key_set ? '⚠ NO API KEY' : (provider.model || 'model armed')}
            </span>
          </button>

          <div className="min-w-0 flex-1">
            {missionText
              ? <p className="text-[13px] text-ash truncate" title={missionText}>{missionText}</p>
              : <p className="text-[13px] text-faint truncate">{_t('app_idle_hint')}</p>}
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] uppercase tracking-[.14em] font-mono shrink-0
            ${wsStatus === 'running' ? 'border-volt/40 bg-voltlite text-cyan' : wsStatus === 'complete' ? 'border-gold/40 bg-goldtint text-gold' : wsStatus === 'error' ? 'border-danger/40 bg-dangertint text-danger' : 'border-line text-mut'}`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${wsStatus === 'running' ? 'bg-volt animate-pulse' : wsStatus === 'complete' ? 'bg-gold' : wsStatus === 'error' ? 'bg-danger' : 'bg-mut'}`} />
            {wsStatus === 'running' ? _t('status_campaign') : wsStatus === 'complete' ? _t('status_complete') : wsStatus === 'error' ? _t('status_error') : _t('status_idle')}
          </span>
          {wsStatus === 'running' && (
            <span className="font-mono text-[11px] tabular-nums text-ash shrink-0">{mm}:{ss}</span>
          )}
          {wsStatus === 'running' && (
            <button type="button" onClick={rompre} title={_t('abort_campaign')}
              className="btn-strike rounded-full border border-danger/50 text-danger px-2.5 py-1.5 flex items-center hover:bg-dangertint shrink-0">
              <Ic.stop />
            </button>
          )}
          {(wsStatus === 'complete' || wsStatus === 'error') && (
            <button type="button" onClick={nouvelleSession} title={_t('new_session')}
              className="pill-ghost btn-strike px-4 py-1.5 text-[11px] uppercase tracking-[.12em] shrink-0">
              reset
            </button>
          )}
          <button onClick={() => setShowParams(s => !s)}
            title="Operational Settings (Brain, Arsenal, Mask, Purge)"
            className={`rounded-full px-2.5 py-1.5 border transition-colors shrink-0 ${showParams ? 'bg-voltlite text-cyan border-volt/30' : 'bg-inset text-mut border-line hover:text-ink'}`}>
            <Ic.gear />
          </button>
          <button onClick={() => setShowSidebar(s => !s)}
            title="Missions & Sessions (Ctrl+B)"
            className={`rounded-full px-2.5 py-1.5 border transition-colors shrink-0 ${showSidebar ? 'bg-voltlite text-cyan border-volt/30' : 'bg-inset text-mut border-line hover:text-ink'}`}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/></svg>
          </button>
          <button onClick={() => setConsolePinned(!consoleOpen)}
            title={consoleOpen ? _t('console_close') : _t('console_open')}
            className={`relative rounded-full px-2.5 py-1.5 border transition-colors shrink-0 ${consoleOpen ? 'bg-voltlite text-cyan border-volt/30' : 'bg-inset text-mut border-line hover:text-ink'}`}>
            <Ic.term />
            {!consoleOpen && hasActivity && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-volt" title={_t('activity_live')} />
            )}
          </button>
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${connected ? 'bg-ok' : 'bg-danger animate-pulse'}`} title={connected ? 'live stream' : 'stream down'} />
        </header>
      </div>

      {/* ── corps : SALLE DE GUERRE (centre) · CONSOLE (droite) ── */}
      <div className="relative z-10 flex flex-1 min-h-0 gap-3 px-4 pb-16">

        {/* ══ CENTRE — LA SALLE DE GUERRE ══ */}
        <main className="flex-1 min-w-0 flex flex-col gap-3 min-h-0">
          {pendingPlan && (
            <div className="panel overflow-hidden animate-fadeIn shrink-0 max-h-[46%] flex flex-col">
              <div className="relative px-5 py-3 border-b border-line flex items-center justify-between gap-3 shrink-0">
                <span aria-hidden className="wash-violet absolute inset-x-0 top-0 h-[2px]" />
                <span className="text-[13px] font-medium text-ink">Plan d'attaque — approbation requise</span>
                <div className="flex items-center gap-1.5">
                  {['IA', 'Swarm'].map(m => (
                    <button key={m} type="button" onClick={() => setStrikeMode(m)}
                      className={`px-3.5 py-1.5 rounded-full text-[11px] uppercase tracking-[.1em] transition-all
                        ${strikeMode === m ? 'pill-solid font-medium' : 'border border-line text-mut hover:text-ink'}`}>
                      {m.toLowerCase()}
                    </button>
                  ))}
                </div>
              </div>
              <textarea value={editedPlan} onChange={(e) => setEditedPlan(e.target.value)}
                rows={10}
                className="w-full terminal-bg text-[11.5px] leading-relaxed p-4 resize-y focus:outline-none border-0 bg-transparent min-h-0"
                spellCheck="false" />
              <div className="px-5 py-3 border-t border-line bg-hover flex items-center justify-between gap-3 shrink-0">
                <span className="text-[11px] text-mut">
                  {_t('plan_edit_hint')} · mode {strikeMode.toLowerCase()}
                  {strikeMode === 'Swarm' ? ' · ' + _t('mode_swarm') : ' · ' + _t('mode_solo')}
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

          <div className="flex-1 min-h-0">
            <WarRoom
              chatLog={chatLog}
              onSend={sendChatMessage}
              busy={chatBusy}
              wsStatus={wsStatus}
              missionId={missionId}
              onSendOperator={sendOperatorMessage}
              onClear={clearChat}
              streaming={chatStreaming}
              strikeMode={strikeMode}
              setStrikeMode={setStrikeMode}
            />
          </div>
        </main>

        {/* ══ DROITE — LA CONSOLE DE CAMPAGNE ══
            Sur desktop (lg+), partage harmonieux (42-46%).
            Sur mobile/tablette (<lg), dock/overlay fluide plein format sans écraser la salle de guerre. */}
        {/* ── DROITE — LA CONSOLE DE CAMPAGNE ──
            Ouvert (lg+) : partage harmonieux (42-46%).
            Fermé : une barre d'icônes 40px reste VISIBLE — le workbench
            se découvre, un clic ouvre l'onglet voulu. Plus de panneau
            fantôme que personne ne sait exister. */}
        {!consoleOpen && (
          <div className="hidden lg:flex w-10 shrink-0 flex-col items-center gap-1.5 py-2 border-l border-line/60 bg-wash/30">
            {[
              { tab: 'console', title: 'Console', icon: <Ic.term /> },
              { tab: 'surface', title: 'Surface', icon: (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20"/></svg>
              ) },
              { tab: 'chain', title: 'Chain', icon: (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 17H7A5 5 0 0 1 7 7h2"/><path d="m15 7h2a5 5 0 0 1 0 10h-2"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              ) },
              { tab: 'findings', title: 'Findings', icon: (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
              ) },
              { tab: 'dashboard', title: 'Dashboard', icon: (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
              ) },
            ].map(({ tab, title, icon }) => (
              <button
                key={tab}
                type="button"
                onClick={() => { setWorkbenchTab(tab); setConsolePinned(true); }}
                title={`${title} — open workbench`}
                className="relative w-8 h-8 rounded-lg border border-line bg-inset text-mut hover:text-ink hover:border-volt/50 hover:bg-wash transition-all flex items-center justify-center shrink-0"
              >
                {icon}
                {tab === 'findings' && findings.length > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[14px] h-[14px] px-0.5 rounded-full bg-danger text-white text-[8px] font-bold flex items-center justify-center">
                    {findings.length > 99 ? '99+' : findings.length}
                  </span>
                )}
                {tab === 'console' && logs.length > 0 && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-volt animate-pulse" />
                )}
              </button>
            ))}
          </div>
        )}
        <aside
          aria-hidden={!consoleOpen}
          className={`shrink-0 min-h-0 flex flex-col transition-all duration-300 ease-[cubic-bezier(.22,1,.36,1)] ${
            consoleOpen
              ? 'w-[46%] xl:w-[42%] opacity-100'
              : 'w-0 opacity-0 overflow-hidden pointer-events-none'
          }`}
        >
          <div className="h-full w-full flex flex-col gap-2.5 min-w-0">
            {/* Sélecteur de vue de l'établi droit (Workbench Multi-Vues) */}
            <div className="flex items-center justify-between gap-2 px-1 shrink-0 select-none">
              <div className="flex items-center gap-1 p-1 rounded-full border border-line bg-wash/60">
                <button
                  type="button"
                  onClick={() => setWorkbenchTab('console')}
                  className={`px-3 py-1 rounded-full text-[10.5px] uppercase font-mono tracking-wider transition-all ${
                    workbenchTab === 'console'
                      ? 'pill-solid font-medium shadow-xs'
                      : 'text-mut hover:text-ink hover:bg-hover'
                  }`}
                >
                  <span>{_t('tab_console')}</span>
                  {logs.length > 0 && <span className="ml-1 opacity-75">({logs.length})</span>}
                </button>

                <button
                  type="button"
                  onClick={() => setWorkbenchTab('surface')}
                  className={`px-3 py-1 rounded-full text-[10.5px] uppercase font-mono tracking-wider transition-all ${
                    workbenchTab === 'surface'
                      ? 'pill-solid font-medium shadow-xs'
                      : 'text-mut hover:text-ink hover:bg-hover'
                  }`}
                >
                  <span>{_t('tab_surface')}</span>
                  {graph.nodes.length > 0 && <span className="ml-1 opacity-75">({graph.nodes.length})</span>}
                </button>

                <button
                  type="button"
                  onClick={() => setWorkbenchTab('chain')}
                  className={`px-3 py-1 rounded-full text-[10.5px] uppercase font-mono tracking-wider transition-all ${
                    workbenchTab === 'chain'
                      ? 'pill-solid font-medium shadow-xs'
                      : 'text-mut hover:text-ink hover:bg-hover'
                  }`}
                >
                  <span>{_t('tab_chain')}</span>
                  {(graph.nodes.length > 0 || findings.length > 0) && (
                    <span className="ml-1 opacity-75">({graph.nodes.length + findings.length})</span>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setWorkbenchTab('dashboard')}
                  className={`px-3 py-1 rounded-full text-[10.5px] uppercase font-mono tracking-wider transition-all ${
                    workbenchTab === 'dashboard'
                      ? 'pill-solid font-medium shadow-xs'
                      : 'text-mut hover:text-ink hover:bg-hover'
                  }`}
                >
                  <span>Dashboard</span>
                </button>

                <button
                  type="button"
                  onClick={() => setWorkbenchTab('findings')}
                  className={`px-3 py-1 rounded-full text-[10.5px] uppercase font-mono tracking-wider transition-all ${
                    workbenchTab === 'findings'
                      ? 'pill-solid font-medium shadow-xs'
                      : 'text-mut hover:text-ink hover:bg-hover'
                  }`}
                >
                  <span>{_t('tab_findings')}</span>
                  {findings.length > 0 && (
                    <span className="ml-1 px-1.5 py-0.2 rounded-full bg-danger text-white text-[9px] font-bold">
                      {findings.length}
                    </span>
                  )}
                </button>
              </div>

              {workbenchTab === 'console' && logs.length > 0 && (
                <button
                  type="button"
                  onClick={clearConsole}
                  className="text-[10px] uppercase font-mono text-faint hover:text-danger px-2 py-0.5 rounded transition-colors"
                  title="Vider le journal console"
                >
                  {''+ _t('console_clear')}
                </button>
              )}
            </div>

            {/* Corps de l'établi actif */}
            <div className="flex-1 min-h-[220px] overflow-hidden">
              {workbenchTab === 'console' && (
                <LiveConsole logs={logs} status={wsStatus} onClear={clearConsole}
                  onClose={() => setConsolePinned(false)} />
              )}
              {workbenchTab === 'surface' && (
                <SurfaceMap graph={graph} />
              )}
              {workbenchTab === 'chain' && (
                <AttackGraph graph={graph} findings={findings} />
              )}
              {workbenchTab === 'dashboard' && (
                <Dashboard mission={missionText} />
              )}
              {workbenchTab === 'findings' && (
                <FindingsVault findings={findings} />
              )}
            </div>

            {wsStatus === 'complete' && workspace?.exists && (
              <div className="panel overflow-hidden shrink-0 animate-fadeIn flex flex-col">
                <div aria-hidden className="horizon h-[2px] w-full shrink-0" />
                <div className="px-4 py-2.5 border-b border-line flex items-center justify-between gap-2 shrink-0">
                  <span className="text-[12px] font-medium text-ink">rapport de puissance</span>
                  <span className="font-mono text-[10px] text-mut shrink-0">{workspace.findings.length}F · {workspace.extractions.length}X</span>
                </div>
                <pre className="terminal-bg p-3 m-0 whitespace-pre-wrap break-words text-[11.5px] max-h-[160px] overflow-y-auto">{workspace.power_report || '⏳'}</pre>
                <div className="px-4 py-2.5 border-t border-line flex items-center justify-between gap-2 shrink-0">
                  <span className="text-[10px] font-mono text-faint truncate">missions/{workspace.target}/ · {workspace.ledger_lines} entrées</span>
                  {workspace.final_report && (
                    <button onClick={() => setReading({ name: 'rapport final', content: workspace.final_report })}
                      className="pill-cta btn-strike px-3 py-1 text-[10px] uppercase tracking-[.1em] shrink-0">
                      final
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* Rail vertical d'accès rapide au workbench quand la console est repliée */}
        {!consoleOpen && (
          <aside className="shrink-0 flex flex-col items-center py-2.5 px-1 rounded-card border border-line bg-paper/60 backdrop-blur-md gap-2 z-20 animate-fadeIn select-none self-start shadow-sm">
            <button
              type="button"
              onClick={() => { setWorkbenchTab('console'); setConsolePinned(true); }}
              title="Ouvrir la Console de campagne"
              className={`w-7 h-7 rounded-md flex items-center justify-center transition-all relative ${
                workbenchTab === 'console' ? 'text-cyan bg-voltlite border border-volt/40' : 'text-mut hover:text-ink hover:bg-hover border border-transparent'
              }`}
            >
              <Ic.term />
              {logs.length > 0 && <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-volt" />}
            </button>
            <button
              type="button"
              onClick={() => { setWorkbenchTab('surface'); setConsolePinned(true); }}
              title="Surface d'attaque découverte"
              className={`w-7 h-7 rounded-md flex items-center justify-center transition-all relative ${
                workbenchTab === 'surface' ? 'text-cyan bg-voltlite border border-volt/40' : 'text-mut hover:text-ink hover:bg-hover border border-transparent'
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              {graph.nodes?.length > 0 && <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-cyan" />}
            </button>
            <button
              type="button"
              onClick={() => { setWorkbenchTab('chain'); setConsolePinned(true); }}
              title="Chaîne d'attaque tactique"
              className={`w-7 h-7 rounded-md flex items-center justify-center transition-all ${
                workbenchTab === 'chain' ? 'text-cyan bg-voltlite border border-volt/40' : 'text-mut hover:text-ink hover:bg-hover border border-transparent'
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            </button>
            <button
              type="button"
              onClick={() => { setWorkbenchTab('dashboard'); setConsolePinned(true); }}
              title="Dashboard & KPIs"
              className={`w-7 h-7 rounded-md flex items-center justify-center transition-all ${
                workbenchTab === 'dashboard' ? 'text-cyan bg-voltlite border border-volt/40' : 'text-mut hover:text-ink hover:bg-hover border border-transparent'
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>
            </button>
            <button
              type="button"
              onClick={() => { setWorkbenchTab('findings'); setConsolePinned(true); }}
              title="Failles & Vulnérabilités"
              className={`w-7 h-7 rounded-md flex items-center justify-center transition-all relative ${
                workbenchTab === 'findings' ? 'text-danger bg-dangertint border border-danger/40' : 'text-mut hover:text-danger hover:bg-hover border border-transparent'
              }`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              {findings.length > 0 && (
                <span className="absolute -top-1 -right-1 px-1 rounded-full bg-danger text-white text-[8px] font-bold">
                  {findings.length}
                </span>
              )}
            </button>
          </aside>
        )}
      </div>

      {/* ── BARRE LATÉRALE DES MISSIONS & SESSIONS (Ctrl+B) ── */}
      <SessionSidebar
        open={showSidebar}
        onClose={() => setShowSidebar(false)}
        reports={reports}
        onSelectReport={(r) => {
          openReport(r.name);
        }}
        onNewSession={nouvelleSession}
        onOpenParams={() => setShowParams(true)}
        wsStatus={wsStatus}
        missionText={missionText}
      />

      {/* ── PARAMÈTRES — Le Slide-Over Drawer ergonomique ── */}
      {showParams && (
        <div className="fixed inset-0 z-50 flex justify-end animate-fadeIn">
          {/* Backdrop avec flou dépoli */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
            onClick={() => setShowParams(false)}
            aria-hidden="true"
          />

          {/* Tiroir latéral coulissant — SOLIDE et opaque */}
          <aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="params-drawer-title"
            className="relative z-50 w-full sm:w-[500px] md:w-[540px] h-full bg-paper border-l border-line flex flex-col shadow-2xl overflow-hidden"
          >
            {/* Header du tiroir */}
            <div className="px-5 py-3.5 border-b border-line flex items-center justify-between gap-3 shrink-0 bg-wash/60">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-full border border-line bg-inset flex items-center justify-center text-cyan shrink-0">
                  <Ic.gear />
                </span>
                <div>
                  <h2 id="params-drawer-title" className="text-[13px] font-medium text-ink tracking-tight">Operational Settings</h2>
                  <p className="text-[10px] text-faint uppercase tracking-[.14em]">Configuration et arsenal du pont</p>
                </div>
              </div>
              <button
                onClick={() => setShowParams(false)}
                title="Close (Esc)"
                className="w-7 h-7 rounded-full border border-line text-mut hover:text-danger hover:border-danger/40 flex items-center justify-center transition-colors text-[13px]"
              >
                ✕
              </button>
            </div>

            {/* Barre de navigation par onglets */}
            <div className="px-4 py-2 border-b border-line flex items-center gap-1.5 overflow-x-auto shrink-0 bg-wash/30">
              {[
                { id: 'cerveau', label: 'Cerveau' },
                { id: 'arsenal', label: 'Arsenal' },
                { id: 'masque', label: 'Masque' },
                { id: 'rapports', label: 'Rapports', count: reports.length },
                { id: 'purge', label: 'Purge' },
              ].map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setParamsTab(t.id)}
                  className={`px-3 py-1 rounded-full text-[11px] uppercase tracking-[.08em] transition-all shrink-0 ${
                    paramsTab === t.id
                      ? 'pill-solid font-medium shadow-sm'
                      : 'text-mut hover:text-ink hover:bg-hover'
                  }`}
                >
                  {t.label}
                  {t.count !== undefined && t.count > 0 && (
                    <span className="ml-1 opacity-70 font-mono text-[10px]">({t.count})</span>
                  )}
                </button>
              ))}
            </div>

            {/* Corps du panneau actif avec scroll indépendant */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {paramsTab === 'cerveau' && (
                <div className="space-y-4 animate-fadeIn">
                  <div className="border-b border-line pb-2.5">
                    <span className="eyebrow">intelligence provider</span>
                    <p className="text-[12px] text-ash mt-1">Configure the model and API gateway for autonomous missions and the strategist.</p>
                  </div>

                  <form onSubmit={saveProvider} className="space-y-4">
                    <div className="rounded-card border border-line bg-wash/40 p-4 space-y-3.5">
                      <div className="space-y-1">
                        <label className="text-[10px] uppercase tracking-[.14em] text-mut font-mono">URL de base (API)</label>
                        <input value={provForm.base_url} onChange={(e) => setProvForm(f => ({ ...f, base_url: e.target.value }))}
                          placeholder="https://api.deepseek.com/v1" className={inputCls} />
                      </div>

                      <div className="space-y-1">
                        <label className="text-[10px] uppercase tracking-[.14em] text-mut font-mono">Secret API key</label>
                        <input type="password" value={provForm.api_key} onChange={(e) => setProvForm(f => ({ ...f, api_key: e.target.value }))}
                          placeholder={provider?.api_key_masked ? `${provider.api_key_masked} (unchanged)` : 'sk-…'}
                          autoComplete="new-password" className={inputCls} />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-[10px] uppercase tracking-[.14em] text-mut font-mono">Model</label>
                          <input value={provForm.model} onChange={(e) => setProvForm(f => ({ ...f, model: e.target.value }))}
                            placeholder="deepseek-chat" className={inputCls} />
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center justify-between">
                            <label className="text-[10px] uppercase tracking-[.14em] text-mut font-mono">Plafond Jetons</label>
                            <span className="text-[9.5px] text-faint font-mono">chat</span>
                          </div>
                          <input type="number" min="256" step="100"
                            value={provForm.max_tokens}
                            onChange={(e) => setProvForm(f => ({ ...f, max_tokens: e.target.value }))}
                            className={inputCls} />
                        </div>
                      </div>
                    </div>

                    <div className="pt-1 flex items-center justify-between gap-3">
                      <span className={`text-[11px] font-mono break-words flex-1 ${
                        provMsg?.ok === true ? 'text-ok' : provMsg?.ok === false ? 'text-danger' :
                        isTestingProv ? 'text-warn animate-pulse' : provider?.api_key_set ? 'text-mut' : 'text-danger'}`}>
                        {provMsg ? provMsg.text : provider?.api_key_set ? `✓ key armed (${provider.api_key_masked})` : 'no key armed'}
                      </span>
                      <button type="submit" disabled={isTestingProv} className="pill-cta btn-strike px-5 py-2 text-[11px] uppercase tracking-[.1em] shrink-0">
                        {isTestingProv ? 'test en cours...' : 'armer le cerveau'}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {paramsTab === 'arsenal' && (
                <div className="space-y-3 animate-fadeIn">
                  <div className="border-b border-line pb-2.5">
                    <span className="eyebrow">arsenal & direct strike</span>
                    <p className="text-[12px] text-ash mt-1">Manual trigger of forged tools and unit checks without launching a full campaign.</p>
                  </div>
                  <DirectToolRunner onToolExecuted={() => { fetchReports(); }} />
                </div>
              )}

              {paramsTab === 'masque' && (
                <div className="space-y-3 animate-fadeIn">
                  <div className="border-b border-line pb-2.5">
                    <span className="eyebrow">masque & doctrine</span>
                    <p className="text-[12px] text-ash mt-1">Personality, operational tone, verbal signatures and free directives engraved in the mask.</p>
                  </div>
                  <PersonaPanel />
                </div>
              )}

              {paramsTab === 'rapports' && (
                <div className="space-y-3 animate-fadeIn">
                  <div className="border-b border-line pb-2.5 flex items-center justify-between">
                    <div>
                      <span className="eyebrow">report registry</span>
                      <p className="text-[12px] text-ash mt-1">Mission reports and vulnerability synopses archived locally.</p>
                    </div>
                    <button onClick={fetchReports} title="Refresh" className="pill-ghost text-[10px] px-2.5 py-1 uppercase tracking-[.1em]">
                      refresh
                    </button>
                  </div>
                  {reports.length === 0 ? (
                    <div className="text-center py-10 text-mut text-xs">
                      <p>No archived reports yet.</p>
                    </div>
                  ) : (
                    <ul className="divide-y divide-line rounded-card border border-line overflow-hidden bg-inset/40">
                      {reports.map(r => (
                        <li key={r.name} onClick={() => openReport(r.name)}
                          className="py-2.5 px-3.5 flex items-center gap-2.5 group cursor-pointer hover:bg-hover transition-colors">
                          <span className="text-faint group-hover:text-cyan transition-colors"><Ic.doc /></span>
                          <span className="text-[12px] text-ash group-hover:text-ink transition-colors truncate flex-1 font-mono">
                            {r.name.replace(/report_|\.md/g, '')}
                          </span>
                          <span className="font-mono text-[10px] text-faint shrink-0">{(r.size / 1024).toFixed(1)} KB</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {paramsTab === 'purge' && (
                <div className="space-y-3 animate-fadeIn">
                  <div className="border-b border-line pb-2.5">
                    <span className="eyebrow">memory & session purges</span>
                    <p className="text-[12px] text-ash mt-1">Surgical reset of the memory modules without touching mission history or forged tools.</p>
                  </div>
                  <FreshSessionPanel
                    onPurge={() => { reset(); setMission(''); setWorkspace(null); setReading(null); }} />
                </div>
              )}
            </div>

            {/* Footer du tiroir */}
            <div className="px-5 py-3 border-t border-line flex items-center justify-between text-[10px] text-faint uppercase tracking-[.14em] shrink-0 bg-paper/30 font-mono">
              <span>REDACTED · console</span>
              <span className="text-ok">system ready</span>
            </div>
          </aside>
        </div>
      )}

      {reading && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 md:p-8" onClick={() => setReading(null)}>
          <div className="w-full max-w-3xl max-h-[85vh] panel flex flex-col overflow-hidden animate-fadeIn" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b border-line flex items-center justify-between gap-3">
              <span className="font-mono text-[11px] uppercase tracking-[.16em] text-ash truncate">{reading.name}</span>
              <button onClick={() => setReading(null)} className="pill-cta btn-strike px-4 py-1.5 text-[11px] uppercase tracking-[.1em] shrink-0">fermer</button>
            </div>
            <pre className="flex-1 overflow-y-auto terminal-bg p-4 m-0 whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-[var(--term-ink)]">{reading.content ?? '⏳ chargement…'}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
