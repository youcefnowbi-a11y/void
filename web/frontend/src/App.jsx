import React, { useState, useEffect } from 'react';
import axios from 'axios';
import LiveConsole from './components/LiveConsole.jsx';
import WarRoom from './components/WarRoom.jsx';
// (audit m5): FindingsLive was imported but never rendered — dead module, removed.
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
  /* ── commercial license lock (dev build lifts it via TEST_MODE) ── */
  const [licenseLocked, setLicenseLocked] = useState(false);
  const [licenseKey, setLicenseKey] = useState('');
  const [licenseBusy, setLicenseBusy] = useState(false);
  const [licenseMsg, setLicenseMsg] = useState(null);

  const {
    logs, findings, graph, stats, tools,
    status: wsStatus, missionId, missionText, connected,
    reset, clearConsole, abortMission, sendOperatorMessage,
    pendingPlan, sendChatMessage, clearChat, chatLog, chatBusy, chatStreaming, approvePlan,
  } = useMissionSocket();
  const [editedPlan, setEditedPlan] = useState('');
  const [strikeMode, setStrikeMode] = useState('IA');
  const [activePlan, setActivePlan] = useState(pendingPlan);
  const [planExiting, setPlanExiting] = useState(false);

  /* ── panneaux & établi ── */
  const [consolePinned, setConsolePinned] = useState(null); // null = auto (l'activité décide)
  const hasConsoleActivity = logs.length > 0 || wsStatus !== 'idle';
  const consoleOpen = consolePinned !== null ? consolePinned : hasConsoleActivity;
  const [workbenchTab, setWorkbenchTab] = useState('console'); // 'console' | 'surface' | 'findings'
  const [consoleFullscreen, setConsoleFullscreen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);

  // Smooth exit transition for pendingPlan
  useEffect(() => {
    if (pendingPlan) {
      setActivePlan(pendingPlan);
      setPlanExiting(false);
    } else if (activePlan) {
      setPlanExiting(true);
      const timer = setTimeout(() => {
        setActivePlan(null);
        setPlanExiting(false);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [pendingPlan]);

  // Operational strike launch -> automatically open console and switch to console tab
  useEffect(() => {
    if (wsStatus === 'running') {
      setWorkbenchTab('console');
      setConsolePinned(true);
    }
  }, [wsStatus]);

  const handleApprovePlan = async (approved, plan, mode) => {
    if (approved) {
      setWorkbenchTab('console');
      setConsolePinned(true);
    }
    return await approvePlan(approved, plan, mode);
  };

  const handleSendChatMessage = async (msg) => {
    if (msg && msg.trim().startsWith('/')) {
      setWorkbenchTab('console');
      setConsolePinned(true);
    }
    return await sendChatMessage(msg);
  };

  const handleSendOperatorMessage = async (mid, msg) => {
    if (msg && msg.trim().startsWith('/')) {
      setWorkbenchTab('console');
      setConsolePinned(true);
    }
    return await sendOperatorMessage(mid, msg);
  };

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
    if (activePlan?.plan) setEditedPlan(activePlan.plan);
  }, [activePlan?.plan]);

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

  /* ── license lock check at boot (commercial build) ── */
  useEffect(() => {
    axios.get(`${API_BASE}/license/status`)
      .then(r => setLicenseLocked(!r.data?.licensed))
      .catch((err) => {
        // 403 with LICENSE_LOCKED = the /license/status itself is fine
        // (unlock trio) but something else — default to locked on any
        // strange failure so the activation screen shows.
        if (err?.response?.status === 403) setLicenseLocked(true);
      });
  }, []);

  const activateLicense = () => {
    if (!licenseKey.trim() || licenseBusy) return;
    setLicenseBusy(true); setLicenseMsg(null);
    axios.post(`${API_BASE}/license/activate`, { key: licenseKey.trim() })
      .then(() => {
        setLicenseMsg({ ok: true, text: '✓ unlocked — welcome to the war room' });
        setTimeout(() => setLicenseLocked(false), 900);
      })
      .catch((err) => {
        setLicenseMsg({ ok: false, text: err?.response?.data?.detail || 'activation failed' });
      })
      .finally(() => setLicenseBusy(false));
  };

  useEffect(() => {
    if (wsStatus === 'complete') {
      fetchReports();
      axios.get(`${API_BASE}/workspace`, { params: { mission: missionText } })
        .then(r => setWorkspace(r.data)).catch(() => {});
    }
  }, [wsStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && !e.defaultPrevented) {
        if (reading) {
          setReading(null);
        } else if (consoleFullscreen) {
          setConsoleFullscreen(false);
        } else if (showParams) {
          setShowParams(false);
        } else if (showSidebar) {
          setShowSidebar(false);
        } else if (consoleOpen) {
          setConsolePinned(false);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [reading, consoleFullscreen, showParams, showSidebar, consoleOpen]);

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
      // M1 FIX (audit): send back the fetched temperature/max_tool_rounds
      // or the backend resets them to defaults on every UI save.
      const r = await axios.post(`${API_BASE}/provider`, {
        base_url: provForm.base_url.trim(), api_key: cleanKey, model: provForm.model.trim(),
        chat_max_tokens: Number.isFinite(mt) ? mt : null,
        temperature: provider?.temperature ?? 0.3,
        max_tool_rounds: provider?.max_tool_rounds ?? 0,
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

      {/* ── commercial license gate — the activation veil ── */}
      {licenseLocked && (
        <div className="fixed inset-0 z-[999] bg-[#070708] flex items-center justify-center px-6">
          <div className="w-full max-w-sm">
            <div className="text-center mb-8">
              <div className="inline-block mb-5 px-3 py-1.5 border border-danger/40 bg-danger/10 rounded-full">
                <span className="text-[10px] font-mono uppercase tracking-[.25em] text-danger">license locked</span>
              </div>
              <h1 className="text-2xl font-semibold text-ink tracking-tight">REDACTED</h1>
              <p className="mt-3 text-[13px] text-mut leading-relaxed">
                Enter your activation key to unlock the autonomous campaign console.
              </p>
            </div>
            <div className="terminal-bg border border-line rounded-lg p-5">
              <label className="block text-[10px] font-mono uppercase tracking-[.2em] text-faint mb-2">
                activation key
              </label>
              <input
                value={licenseKey}
                onChange={(e) => setLicenseKey(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && activateLicense()}
                placeholder="RC-XXXX-XXXX-XXXX-XXXX"
                className="w-full bg-transparent border border-line/60 rounded px-3 py-2.5 font-mono text-[13px] text-ink placeholder:text-faint/50 focus:outline-none focus:border-cta/60"
                autoFocus
              />
              <button
                onClick={activateLicense}
                disabled={licenseBusy || !licenseKey.trim()}
                className="btn-strike w-full mt-4 px-4 py-2.5 rounded text-[11px] font-mono uppercase tracking-[.2em]"
              >
                {licenseBusy ? 'binding…' : 'activate'}
              </button>
              {licenseMsg && (
                <p className={`mt-3 text-[11px] font-mono ${licenseMsg.ok ? 'text-ok' : 'text-danger'}`}>
                  {licenseMsg.text}
                </p>
              )}
              <p className="mt-4 text-[10px] text-faint leading-relaxed">
                The key binds to this machine on first activation. Lost your key? Contact your vendor with the machine fingerprint shown in the launcher console.
              </p>
            </div>
          </div>
        </div>
      )}

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
              src="/redacted-white.png"
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
            {!consoleOpen && hasConsoleActivity && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-volt" title={_t('activity_live')} />
            )}
          </button>
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${connected ? 'bg-ok' : 'bg-danger animate-pulse'}`} title={connected ? 'live stream' : 'stream down'} />
        </header>
      </div>

      {/* ── corps : SALLE DE GUERRE (centre) · CONSOLE (droite) ── */}
      <div className="relative z-10 flex flex-1 min-h-0 gap-3 px-4 pb-16">

        {/* ══ CENTRE — LA SALLE DE GUERRE ══ */}
        <main className={`min-w-0 flex flex-col gap-3 min-h-0 transition-all duration-300 ease-[cubic-bezier(.22,1,.36,1)] ${
          consoleFullscreen
            ? 'hidden pointer-events-none'
            : consoleOpen
            ? 'flex-1 basis-0'
            : 'flex-1'
        }`}>
          {activePlan && (
            <div className={`panel overflow-hidden shrink-0 flex flex-col transition-all duration-300 ease-[cubic-bezier(.22,1,.36,1)] ${
              planExiting
                ? 'opacity-0 max-h-0 -translate-y-2 mb-0 py-0 border-transparent pointer-events-none'
                : 'opacity-100 max-h-[46%] translate-y-0 animate-fadeIn'
            }`}>
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
                  <button onClick={() => handleApprovePlan(false, '', '')}
                    className="pill-ghost btn-strike px-4 py-1.5 text-[11px] uppercase tracking-[.1em] hover:!border-danger hover:!text-danger">
                    rejeter
                  </button>
                  <button onClick={async () => {
                    // M5 FIX (audit): a 409 (campaign already running) used to
                    // be a silent dead button — surface the reason now.
                    const r = await handleApprovePlan(true, editedPlan, strikeMode);
                    if (r && r.status === 'error') {
                      setProvMsg({ ok: false, text: `✗ ${r.detail || _t('strike_blocked')}` });
                      setShowParams(true);
                    }
                  }}
                    disabled={!editedPlan.trim()}
                    className="pill-cta btn-strike px-5 py-1.5 text-[11px] uppercase tracking-[.1em]">
                    approuver — lancer la frappe
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="flex-1 min-h-0 relative">
            <WarRoom
              chatLog={chatLog}
              onSend={handleSendChatMessage}
              busy={chatBusy}
              wsStatus={wsStatus}
              missionId={missionId}
              onSendOperator={handleSendOperatorMessage}
              onClear={clearChat}
              streaming={chatStreaming}
              strikeMode={strikeMode}
              setStrikeMode={setStrikeMode}
              tools={tools}
              onFocusConsole={() => {
                setWorkbenchTab('console');
                setConsolePinned(true);
              }}
              rightRail={!consoleOpen ? (
                <div className="hidden lg:flex flex-col items-center justify-center gap-2.5 w-11 py-4 border-l border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.015)] shrink-0">
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
                      className="relative w-7 h-7 rounded-xl border border-transparent hover:border-line bg-transparent hover:bg-wash text-mut hover:text-ink transition-all flex items-center justify-center shrink-0 group"
                    >
                      <span className="transition-transform group-hover:scale-110">{icon}</span>
                      {tab === 'findings' && findings.length > 0 && (
                        <span className="absolute -top-1 -right-1 min-w-[13px] h-[13px] px-0.5 rounded-full bg-danger text-white text-[7.5px] font-bold flex items-center justify-center shadow-xs">
                          {findings.length > 99 ? '99+' : findings.length}
                        </span>
                      )}
                      {tab === 'console' && logs.length > 0 && (
                        <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-volt animate-pulse" />
                      )}
                    </button>
                  ))}
                </div>
              ) : null}
            />
          </div>
        </main>

        {/* ══ DROITE — LA CONSOLE DE CAMPAGNE (ÉQUILIBRE 50% / 50% OU 100% PLEIN ÉCRAN) ══ */}
        <aside
          aria-hidden={!consoleOpen}
          className={`min-h-0 flex flex-col transition-all duration-300 ease-[cubic-bezier(.22,1,.36,1)] ${
            !consoleOpen
              ? 'w-0 opacity-0 overflow-hidden pointer-events-none'
              : consoleFullscreen
              ? 'flex-1 basis-full opacity-100'
              : 'flex-1 basis-0 opacity-100'
          }`}
        >
          <div className="h-full min-h-0 panel-frost flex flex-col overflow-hidden">
            {/* En-tête intégré du workbench — Même niveau que WarRoom */}
            <div className="h-11 px-3 border-b border-line/50 flex items-center justify-between gap-3 shrink-0 select-none bg-wash/20">
              <div className="flex items-center gap-1">
                {[
                  { tab: 'console', label: _t('tab_console'), count: logs.length },
                  { tab: 'surface', label: _t('tab_surface'), count: graph.nodes?.length },
                  { tab: 'chain', label: _t('tab_chain'), count: (graph.nodes?.length || 0) + (findings.length || 0) },
                  { tab: 'dashboard', label: 'Dashboard' },
                  { tab: 'findings', label: _t('tab_findings'), count: findings.length, isDanger: true },
                ].map(({ tab, label, count, isDanger }) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setWorkbenchTab(tab)}
                    className={`relative px-3 py-1 rounded-full text-[10.5px] uppercase font-mono tracking-wider transition-all flex items-center gap-1.5 ${
                      workbenchTab === tab ? 'pill-solid font-medium shadow-xs' : 'text-mut hover:text-ink hover:bg-hover'
                    }`}
                  >
                    <span>{label}</span>
                    {count > 0 && (
                      <span className={`text-[9px] px-1.5 py-0.2 rounded-full font-bold ${
                        isDanger ? 'bg-danger text-white' : workbenchTab === tab ? 'bg-black/25 text-white' : 'bg-inset text-faint'
                      }`}>
                        {count > 99 ? '99+' : count}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              {/* Contrôles du volet latéral — Plein écran + Fermer */}
              <div className="flex items-center gap-1.5 shrink-0">
                {workbenchTab === 'console' && (
                  <button
                    type="button"
                    onClick={() => setConsoleFullscreen(!consoleFullscreen)}
                    title={consoleFullscreen ? (_t('console_restore') || "Restaurer (Esc)") : (_t('console_fullscreen') || "Console plein écran")}
                    className={`w-7 h-7 rounded-full border transition-all shadow-xs shrink-0 flex items-center justify-center group ${
                      consoleFullscreen
                        ? 'bg-voltlite text-cyan border-volt/40'
                        : 'border-line/60 bg-wash/60 hover:bg-hover text-mut hover:text-cyan'
                    }`}
                  >
                    {consoleFullscreen ? (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform group-hover:scale-110">
                        <polyline points="4 14 10 14 10 20" />
                        <polyline points="20 10 14 10 14 4" />
                        <line x1="14" y1="10" x2="21" y2="3" />
                        <line x1="3" y1="21" x2="10" y2="14" />
                      </svg>
                    ) : (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform group-hover:scale-110">
                        <polyline points="15 3 21 3 21 9" />
                        <polyline points="9 21 3 21 3 15" />
                        <line x1="21" y1="3" x2="14" y2="10" />
                        <line x1="3" y1="21" x2="10" y2="14" />
                      </svg>
                    )}
                  </button>
                )}

                {/* Bouton fermer le volet latéral — style Apple minimaliste */}
                <button
                  type="button"
                  onClick={() => { setConsolePinned(false); setConsoleFullscreen(false); }}
                  title="Fermer le volet (Esc)"
                  className="w-7 h-7 rounded-full border border-line/60 bg-wash/60 hover:bg-dangertint/40 hover:border-danger/40 text-mut hover:text-danger flex items-center justify-center transition-all shadow-xs shrink-0 group"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform group-hover:scale-110">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Corps de l'établi actif */}
            <div className="flex-1 min-h-0 overflow-hidden relative">
              {workbenchTab === 'console' && (
                <LiveConsole
                  logs={logs}
                  status={wsStatus}
                  onClear={clearConsole}
                  embedded={true}
                  chatBusy={chatBusy}
                  isExpanded={consoleFullscreen}
                  onToggleExpand={setConsoleFullscreen}
                />
              )}
              {workbenchTab === 'surface' && (
                <SurfaceMap graph={graph} />
              )}
              {workbenchTab === 'chain' && (
                <AttackGraph graph={graph} findings={findings} />
              )}
              {workbenchTab === 'dashboard' && (
                <div className="h-full p-4 overflow-y-auto"><Dashboard mission={missionText} /></div>
              )}
              {workbenchTab === 'findings' && (
                <FindingsVault findings={findings} />
              )}
            </div>

            {wsStatus === 'complete' && workspace?.exists && (
              <div className="border-t border-line/50 overflow-hidden shrink-0 animate-fadeIn flex flex-col bg-wash/30">
                <div aria-hidden className="horizon h-[2px] w-full shrink-0" />
                <div className="px-4 py-2 border-b border-line/50 flex items-center justify-between gap-2 shrink-0">
                  <span className="text-[12px] font-medium text-ink">rapport de puissance</span>
                  <span className="font-mono text-[10px] text-mut shrink-0">{workspace.findings?.length ?? 0}F · {workspace.extractions?.length ?? 0}X</span>
                </div>
                <pre className="terminal-bg p-3 m-0 whitespace-pre-wrap break-words text-[11.5px] max-h-[160px] overflow-y-auto">{workspace.power_report || '⏳'}</pre>
                <div className="px-4 py-2 border-t border-line/50 flex items-center justify-between gap-2 shrink-0">
                  <span className="text-[10px] font-mono text-faint truncate">missions/{workspace.target}/ · {workspace.ledger_lines} entrées</span>
                  {workspace.final_report && (
                    <button onClick={() => setReading({ name: _t('final_report'), content: workspace.final_report })}
                      className="pill-cta btn-strike px-3 py-1 text-[10px] uppercase tracking-[.1em] shrink-0">
                      final
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </aside>

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
