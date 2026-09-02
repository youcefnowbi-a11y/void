import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { API_BASE } from '../api.js';

/**
 * Mission stream — WebSocket with auto-reconnect + HTTP fallback.
 * Captures: console logs, tool states, findings, campaign stats and
 * the Living Graph snapshots that feed THE THEATER (tactical map).
 */
export function useMissionSocket() {
  const [logs, setLogs] = useState([]);
  const [tools, setTools] = useState({});
  const [findings, setFindings] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], links: [] });
  const [stats, setStats] = useState({ rounds: 0, toolsFired: 0, findings: 0, startedAt: null });
  const [status, setStatus] = useState('idle'); // idle | running | complete | error
  const [missionId, setMissionId] = useState(null);
  const [missionText, setMissionText] = useState('');
  const [connected, setConnected] = useState(false);
  // ── CHAT → PLAN → STRIKE : la salle de guerre et le plan en attente ──
  const [pendingPlan, setPendingPlan] = useState(null); // {missionId, plan}
  const [chatLog, setChatLog] = useState([]);           // [{role, text, time}]
  const [chatBusy, setChatBusy] = useState(false);
  const [chatStreaming, setChatStreaming] = useState(''); // live delta draft
  const streamRef = useRef('');

  const wsRef = useRef(null);
  const reconnectDelayRef = useRef(1000);
  const reconnectTimerRef = useRef(null);
  const batchRef = useRef([]);
  const timerRef = useRef(null);
  const graphRef = useRef({ nodes: [], links: [] });

  const flushBatch = useCallback(() => {
    if (batchRef.current.length === 0) return;
    const batch = [...batchRef.current];
    batchRef.current = [];
    setLogs(prev => {
      const next = [...prev, ...batch];
      return next.length > 900 ? next.slice(-900) : next;
    });
  }, []);

  const push = useCallback((entry) => {
    batchRef.current.push({ ...entry, ts: entry.ts || new Date().toISOString() });
    if (!timerRef.current) {
      timerRef.current = setTimeout(() => { timerRef.current = null; flushBatch(); }, 60);
    }
  }, [flushBatch]);

  const applyGraph = useCallback((g) => {
    if (!g || !Array.isArray(g.nodes)) return;
    const prevKeys = new Set(graphRef.current.nodes.map(n => n.k + n.v));
    const nodes = g.nodes.map(n => ({ ...n, born: prevKeys.has(n.k + n.v) ? false : Date.now() }));
    const nodeSet = new Set(nodes.map(n => n.k + n.v));
    const links = (g.links || []).filter(l => nodeSet.has(l.s) && nodeSet.has(l.d));
    graphRef.current = { nodes, links };
    setGraph({ nodes, links });
  }, []);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/mission`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectDelayRef.current = 1000;  // reconnexion réussie — backoff reset
      };

      ws.onmessage = (event) => {
        try {
          const ev = JSON.parse(event.data);
          if (ev.type === 'pong') return;
          if (!ev.timestamp) ev.timestamp = new Date().toISOString();

          if (ev.graph) applyGraph(ev.graph);

          switch (ev.type) {
            case 'mission_start':
              setStatus('running');
              setMissionId(ev.mission_id || null);
              setMissionText(ev.mission || '');
              setStats({ rounds: 0, toolsFired: 0, findings: 0, startedAt: ev.timestamp });
              setGraph({ nodes: [], links: [] });
              graphRef.current = { nodes: [], links: [] };
              push({ type: 'system', text: `▶ Ordre engagé — mode ${ev.mode || 'Auto'}`, ts: ev.timestamp });
              flushBatch();
              break;

            case 'plan':
              push({ type: 'plan', text: `Plan tactique : ${(ev.steps || []).map(s => s.tool).join(' → ')}`, ts: ev.timestamp });
              break;

            case 'tool_start':
              setTools(prev => ({ ...prev, [ev.tool]: { status: 'running', startedAt: ev.timestamp } }));
              setStats(s => ({ ...s, toolsFired: s.toolsFired + 1 }));
              push({ type: 'tool', tool: ev.tool, text: `⚙ ${ev.tool} — ${ev.args ? JSON.stringify(ev.args).substring(0, 90) : ''}`, ts: ev.timestamp });
              break;

            case 'tool_result': {
              setTools(prev => ({ ...prev, [ev.tool]: { status: 'done', duration: ev.duration } }));
              let verdict = null;
              try {
                const r = typeof ev.result === 'string' ? JSON.parse(ev.result) : ev.result;
                if (r && typeof r === 'object' && 'exploitable' in r) {
                  verdict = r.exploitable;
                  const sev = verdict === true ? 'CONFIRMED' : verdict === 'partial' ? 'PARTIAL' : 'NEGATIVE';
                  if (verdict !== false && verdict !== null) {
                    setFindings(prev => [{
                      tool: ev.tool, severity: sev,
                      summary: r.summary || JSON.stringify(r).substring(0, 160),
                      ts: ev.timestamp, raw: r,
                    }, ...prev].slice(0, 80));
                    setStats(s => ({ ...s, findings: s.findings + 1 }));
                    push({ type: 'finding', text: `🎯 [${sev}] ${ev.tool} — ${r.summary || ''}`, ts: ev.timestamp });
                  } else {
                    push({ type: 'ok', text: `○ ${ev.tool} — négatif (${ev.duration}s)`, ts: ev.timestamp });
                  }
                } else {
                  push({ type: 'ok', text: `✓ ${ev.tool} — terminé (${ev.duration}s)`, ts: ev.timestamp });
                }
              } catch {
                push({ type: 'ok', text: `✓ ${ev.tool} — terminé (${ev.duration}s)`, ts: ev.timestamp });
              }
              setTools(prev => ({ ...prev, [ev.tool]: { status: 'done', duration: ev.duration, verdict } }));
              break;
            }

            case 'tool_error':
              setTools(prev => ({ ...prev, [ev.tool]: { status: 'error' } }));
              push({ type: 'error', tool: ev.tool, text: `✗ ${ev.tool} — ${ev.error || 'échec'}`, ts: ev.timestamp });
              break;

            case 'tool_heal':
              push({ type: 'heal', text: `🩹 auto-correction : ${ev.field || ev.tool || ''} ${ev.detail || ''}`, ts: ev.timestamp });
              break;

            case 'agent_thinking':
              setStats(s => ({ ...s, rounds: s.rounds + 1 }));
              push({ type: 'think', text: (ev.reasoning ? '🧠 ' : '') + (ev.content || ''), ts: ev.timestamp });
              break;

            case 'ops':
              push({ type: 'ops', text: `💬 ${ev.mode === 'continuation' ? '[continuation] ' : '[live] '}${ev.text || ''}`, ts: ev.timestamp });
              break;

            case 'chat':
              // la conversation vit UNIQUEMENT dans les bulles de la ligne
              // sécurisée (panneau gauche) — jamais dupliquée en console
              break;

            case 'chat_stream':
              // les mots de la stratège arrivent PENDANT qu'elle écrit
              if (ev.reset) {
                streamRef.current = '';
                setChatStreaming('');
              } else {
                streamRef.current += (ev.text || '');
                setChatStreaming(streamRef.current);
              }
              break;

            case 'plan_ready':
              setPendingPlan({ missionId: ev.mission_id || null, plan: ev.plan || '' });
              push({ type: 'plan', text: '🗺 PLAN D\'ATTAQUE PRÊT — approbation de l\'opérateur requise', ts: ev.timestamp });
              flushBatch();
              break;

            case 'round':
              push({
                type: 'round',
                text: `ROUND ${ev.round}/${ev.total}${(ev.tools || []).length ? ' · ' + ev.tools.join(', ') : ' · réflexion…'}`,
                ts: ev.timestamp,
              });
              break;

            case 'system':
              push({ type: 'system', text: ev.text || '', ts: ev.timestamp });
              break;

            case 'chat_event':
              // the strategist speaking INTO the war room (plan delivered, etc.)
              setChatLog(prev => [...prev, { role: 'strategist', text: ev.text || '' }]);
              break;

            case 'mission_complete':
              setStatus('complete');
              push({ type: 'system', text: `✦ Mission terminée — ${ev.rounds || '?'} rounds · ${ev.tools_used || '?'} frappes`, ts: ev.timestamp });
              flushBatch();
              break;

            case 'mission_error':
              setStatus('error');
              push({ type: 'error', text: `✗ ${ev.error || 'Erreur de mission'}`, ts: ev.timestamp });
              flushBatch();
              break;

            default:
              break;
          }
        } catch { /* ignore malformed frames */ }
      };

      ws.onclose = () => {
        setConnected(false);
        // backoff exponentiel plafonné (U7) : 1s → 30s max
        reconnectDelayRef.current = Math.min((reconnectDelayRef.current || 1000) * 2, 30000);
        reconnectTimerRef.current = setTimeout(connectWebSocket, reconnectDelayRef.current);
      };
      ws.onerror = () => ws.close && ws.close();
    } catch (err) {
      console.error('[VOIDFORGE] WS error', err);
    }
  }, [applyGraph, flushBatch, push]);

  useEffect(() => {
    connectWebSocket();
    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 25000);
    return () => {
      clearInterval(ping);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── resync au montage (U3) : si une campagne tourne, le HUD la retrouve ──
  useEffect(() => {
    axios.get(`${API_BASE}/mission/status`).then(r => {
      const d = r.data || {};
      if (d.running && d.mission_id) {
        setStatus('running');
        setMissionId(d.mission_id);
        setMissionText(d.mission_text || '');
        setStats(s => ({ ...s, startedAt: d.started_at || new Date().toISOString() }));
      }
    }).catch(() => {});
  }, []);

  const startMission = useCallback(async (mission, mode = 'Auto', extra = {}) => {
    const { intel_mode = 'last', docs = [], autonomy = false } = extra;
    setStatus('running');
    setMissionText(mission);
    setFindings([]);
    setTools({});
    setGraph({ nodes: [], links: [] });
    graphRef.current = { nodes: [], links: [] };
    setStats({ rounds: 0, toolsFired: 0, findings: 0, startedAt: new Date().toISOString() });
    push({ type: 'system', text: `Transmis au commandement : ${mission.substring(0, 120)}` });
    flushBatch();
    try {
      const res = await axios.post(`${API_BASE}/mission`, { mission, mode, intel_mode, docs, autonomy });
      if (res.data.status !== 'accepted') {
        setStatus('error');
        push({ type: 'error', text: `Refusé : ${res.data.output || 'échec'}` });
        flushBatch();
      }
    } catch (err) {
      setStatus('error');
      push({ type: 'error', text: `Échec de transmission : ${err.response?.data?.detail || err.message}` });
      flushBatch();
    }
  }, [flushBatch, push]);

  const sendOperatorMessage = useCallback(async (missionId, message) => {
    try {
      const res = await axios.post(`${API_BASE}/mission/message`, {
        mission_id: missionId || null, message,
      });
      return res.data; // {status: 'queued'} live | {status: 'continued'} new mission
    } catch (err) {
      return { status: 'error', error: err.response?.data?.detail || err.message };
    }
  }, []);

  // ── la conversation survit au reload : le backend sert le log complet ──
  useEffect(() => {
    axios.get(`${API_BASE}/chat/log`).then(r => {
      const log = r.data?.log;
      if (Array.isArray(log) && log.length) setChatLog(log);
    }).catch(() => {});
    axios.get(`${API_BASE}/mission/pending`).then(r => {
      if (r.data?.pending && r.data.plan) {
        setPendingPlan({ missionId: null, plan: r.data.plan, target: r.data.target });
      }
    }).catch(() => {});
  }, []);

  // ── salle de guerre : la seule ligne de conversation (bulles à gauche) ──
  const sendChatMessage = useCallback(async (message) => {
    const msg = (message || '').trim();
    if (!msg || chatBusy) return { status: 'error', error: 'chat occupé ou vide' };
    setChatLog(p => [...p, { role: 'user', text: msg }]);
    streamRef.current = '';
    setChatStreaming('');
    setChatBusy(true);
    try {
      const res = await axios.post(`${API_BASE}/chat`, { message: msg });
      setChatLog(p => [...p, { role: 'strategist', text: res.data.answer, time: res.data.elapsed }]);
      streamRef.current = '';
      setChatStreaming('');
      return { status: 'ok' };
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      streamRef.current = '';
      setChatStreaming('');
      // U6 : l'échec est VISIBLE dans la conversation, pas seulement en console
      setChatLog(p => [...p, { role: 'strategist', text: `⚠ échec du canal : ${detail}` }]);
      push({ type: 'error', text: `✗ salle de guerre : ${detail}` });
      flushBatch();
      return { status: 'error', error: detail };
    } finally {
      setChatBusy(false);
    }
  }, [chatBusy, push, flushBatch]);

  const clearChat = useCallback(async () => {
    setChatLog([]);
    try { await axios.post(`${API_BASE}/chat/clear`); } catch { /* silencieux */ }
  }, []);

  // ── verdict du commandant sur le plan : approuver (édité ou non) / rejeter ──
  const approvePlan = useCallback(async (approved, planDoc, strikeMode) => {
    try {
      const res = await axios.post(`${API_BASE}/mission/approve-plan`, {
        approved, plan_doc: planDoc || '', strike_mode: strikeMode || '',
      });
      setPendingPlan(null);
      if (res.data.status === 'strike_launched') setStatus('running');
      return res.data;
    } catch (err) {
      return { status: 'error', error: err.response?.data?.detail || err.message };
    }
  }, []);

  const reset = useCallback(() => {
    /* LE PONT UNIQUE : plus jamais de wipe. La console est un journal de
       campagne — les sessions s'y succèdent derrière un séparateur. Seul
       clearConsole() (geste explicite de l'opérateur) efface. */
    push({ type: 'separator', text: '── session close — le journal continue ──' });
    flushBatch();
    setStatus('idle');
    setTools({});
    setFindings([]);
    setGraph({ nodes: [], links: [] });
    graphRef.current = { nodes: [], links: [] };
    setMissionId(null);
    setMissionText('');
    setStats({ rounds: 0, toolsFired: 0, findings: 0, startedAt: null });
  }, [push, flushBatch]);

  const clearConsole = useCallback(() => {
    setLogs([]);
  }, []);

  const abortMission = useCallback(async (id) => {
    if (!id) return { status: 'error', error: 'aucune mission vivante' };
    push({ type: 'system', text: '⏹ rupture demandée — transmission du signal…' });
    flushBatch();
    try {
      const res = await axios.post(`${API_BASE}/mission/abort`, { mission_id: id, message: '__ABORT__' });
      return res.data;
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      push({ type: 'error', text: `✗ rupture impossible : ${detail}` });
      flushBatch();
      return { status: 'error', error: detail };
    }
  }, [push, flushBatch]);

  return { logs, tools, findings, graph, stats, status, missionId, missionText, connected,
           startMission, reset, clearConsole, abortMission, sendOperatorMessage,
           pendingPlan, sendChatMessage, clearChat, chatLog, chatBusy, chatStreaming, approvePlan };
}
