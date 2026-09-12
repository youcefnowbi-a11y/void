import React, { useState, useMemo } from 'react';
import { t as _t } from '../i18n.js';

// Configuration des 4 phases de la Kill-Chain tactique
const STAGES = [
  {
    id: 'recon',
    label: '1. Reconnaissance',
    sub: _t('node_domains'),
    color: 'cyan',
    badge: 'border-cyan/40 bg-cyan/10 text-cyan',
    kinds: ['domain', 'ip', 'cidr', 'host', 'dns', 'nameserver'],
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
    )
  },
  {
    id: 'surface',
    label: _t('phase_surface'),
    sub: 'Routes, Ports & Technos',
    color: 'volt',
    badge: 'border-volt/40 bg-voltlite text-volt',
    kinds: ['endpoint', 'port', 'tech', 'service', 'header', 'route', 'api'],
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
    )
  },
  {
    id: 'secrets',
    label: '3. Secrets & Auth',
    sub: _t('node_identity'),
    color: 'warn',
    badge: 'border-warn/40 bg-warntint text-warn',
    kinds: ['key', 'identity', 'bucket', 'secret', 'credential', 'jwt', 'auth', 'env'],
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
    )
  },
  {
    id: 'exploit',
    label: '4. Exploitation & Failles',
    sub: 'Vecteurs & Preuves PoC',
    color: 'danger',
    badge: 'border-danger/40 bg-dangertint text-danger',
    kinds: ['finding', 'vuln', 'exfil', 'exploit', 'compromise', 'rce', 'sqli', 'bola'],
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
    )
  }
];

export default function AttackGraph({ graph = { nodes: [], links: [] }, findings = [] }) {
  const [viewMode, setViewMode] = useState('pipeline'); // 'pipeline' | 'topology'
  const [search, setSearch] = useState('');
  const [selectedNode, setSelectedNode] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);
  const [zoom, setZoom] = useState(1);

  // Normalisation des nœuds + injection des failles comme nœuds d'exploitation
  const allNodes = useMemo(() => {
    const rawNodes = [...(graph.nodes || [])];
    const nodeMap = new Map();

    // 1. Ajouter les nœuds du Living Graph
    rawNodes.forEach(n => {
      const id = `${n.k}:${n.v}`;
      if (!nodeMap.has(id)) {
        nodeMap.set(id, {
          id,
          k: n.k || 'endpoint',
          v: n.v || '',
          c: typeof n.c === 'number' ? n.c : 0.7,
          s: n.s || 1,
          raw: n
        });
      }
    });

    // 2. Transformer les findings confirmés en nœuds de phase 4 (Exploitation)
    // C2b FIX (audit): socket findings carry {tool, severity
    // (critical|high|info), summary, ts, raw} — never title/poc. Read the
    // actual shape so the exploitation column shows real summaries.
    (findings || []).forEach((f, idx) => {
      const fid = `finding:${f.id || idx}:${f.summary || f.tool || 'vuln'}`;
      if (!nodeMap.has(fid)) {
        nodeMap.set(fid, {
          id: fid,
          k: 'finding',
          v: f.summary || f.raw?.summary || `${f.tool || 'find'} ${_t('vuln_confirmed')}`,
          c: f.severity === 'critical' ? 1.0 : f.severity === 'high' ? 0.9 : 0.75,
          s: f.tool ? 2 : 1,
          finding: f,
          severity: f.severity || 'high',
          raw: f
        });
      }
    });

    return Array.from(nodeMap.values());
  }, [graph.nodes, findings]);

  // Répartition par étape de la Kill-Chain
  const stagedNodes = useMemo(() => {
    const buckets = { recon: [], surface: [], secrets: [], exploit: [] };

    allNodes.forEach(node => {
      const kind = (node.k || '').toLowerCase();
      const val = (node.v || '').toLowerCase();

      if (STAGES[0].kinds.includes(kind) || (kind === 'asset' && !val.includes('/'))) {
        buckets.recon.push(node);
      } else if (STAGES[2].kinds.includes(kind) || kind.includes('key') || kind.includes('token') || kind.includes('jwt') || kind.includes('secret')) {
        buckets.secrets.push(node);
      } else if (STAGES[3].kinds.includes(kind) || node.finding || kind.includes('vuln')) {
        buckets.exploit.push(node);
      } else {
        buckets.surface.push(node);
      }
    });

    return buckets;
  }, [allNodes]);

  const filterNode = (node) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      (node.v && node.v.toLowerCase().includes(term)) ||
      (node.k && node.k.toLowerCase().includes(term)) ||
      (node.finding?.detail && node.finding.detail.toLowerCase().includes(term))
    );
  };

  const handleCopy = (text, key) => {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    });
  };

  const activeLinks = useMemo(() => {
    const rawLinks = graph.links || [];
    const validLinks = [];
    const nodeIds = new Set(allNodes.map(n => n.id));

    rawLinks.forEach(l => {
      if (nodeIds.has(l.s) && nodeIds.has(l.d)) {
        validLinks.push({ src: l.s, dst: l.d, rel: l.r || 'connecte' });
      }
    });

    if (validLinks.length === 0) {
      stagedNodes.recon.forEach(reconNode => {
        const domain = reconNode.v;
        stagedNodes.surface.forEach(surfNode => {
          if (surfNode.v.includes(domain)) {
            validLinks.push({ src: reconNode.id, dst: surfNode.id, rel: 'exposes' });
          }
        });
      });

      stagedNodes.exploit.forEach(expNode => {
        if (expNode.finding?.target || expNode.finding?.poc) {
          const t = (expNode.finding.target || expNode.finding.poc).toLowerCase();
          stagedNodes.surface.forEach(surfNode => {
            if (t.includes(surfNode.v.toLowerCase())) {
              validLinks.push({ src: surfNode.id, dst: expNode.id, rel: 'exploite' });
            }
          });
        }
      });
    }

    return validLinks;
  }, [graph.links, allNodes, stagedNodes]);

  if (allNodes.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-6 select-none relative overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
          <svg width="340" height="340" viewBox="0 0 340 340" fill="none" className="text-volt">
            <circle cx="170" cy="170" r="160" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
            <circle cx="170" cy="170" r="115" stroke="currentColor" strokeWidth="1" />
            <circle cx="170" cy="170" r="70" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" />
            <line x1="170" y1="5" x2="170" y2="335" stroke="currentColor" strokeWidth="0.8" strokeDasharray="3 3" />
            <line x1="5" y1="170" x2="335" y2="170" stroke="currentColor" strokeWidth="0.8" strokeDasharray="3 3" />
          </svg>
        </div>
        <div className="relative z-10 flex flex-col items-center">
          <div className="w-12 h-12 rounded-full border border-line2 bg-wash/90 flex items-center justify-center text-volt mb-3 shadow-xs relative">
            <span className="absolute inset-0 rounded-full bg-volt/20 animate-ping opacity-30" />
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <span className="eyebrow mb-1">vector kill-chain</span>
          <h3 className="text-[14px] font-medium text-ink mb-1">{_t('chain_empty_title')}</h3>
          <p className="text-[12px] text-ash max-w-sm leading-relaxed mb-4">
            As the agent begins reconnaissance, the attack chain assembles step by step from the target to the confirmed exploitation vectors.
          </p>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-inset font-mono text-[10.5px] text-faint">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse" />
            <span>{_t('chain_empty_sub')}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden select-none relative">
      {/* ── BARRE SUPÉRIEURE DE COMMANDE TACTIQUE ── */}
      <div className="px-4 py-2.5 border-b border-line bg-wash/40 shrink-0 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-volt animate-pulse" />
            <span className="text-[12px] font-medium text-ink tracking-wide">{_t('chain_title')}</span>
          </div>
          <span className="font-mono text-[10.5px] text-faint border-l border-line pl-2">
            {allNodes.length} actifs · {activeLinks.length} liaisons
          </span>
        </div>

        {/* Contrôles de Vue & Recherche */}
        <div className="flex items-center gap-2 flex-1 justify-end max-w-md">
          <div className="relative flex-1 max-w-[180px]">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrer l'arbre..."
              className="w-full h-7 pl-7 pr-2 text-[11px] rounded-full border border-line bg-inset text-ink placeholder:text-faint focus:outline-none focus:border-volt/50 transition-colors font-mono"
            />
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint pointer-events-none"
              width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-faint hover:text-ink text-[10px]"
              >
                ✕
              </button>
            )}
          </div>

          {/* Toggle Vue Pipeline vs Topologie */}
          <div className="flex items-center p-0.5 rounded-full border border-line bg-wash/80">
            <button
              type="button"
              onClick={() => setViewMode('pipeline')}
              title="Vue Kill-Chain par phases"
              className={`px-2.5 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider transition-all ${
                viewMode === 'pipeline'
                  ? 'pill-solid font-medium text-ink shadow-xs'
                  : 'text-mut hover:text-ink'
              }`}
            >
              Phases
            </button>
            <button
              type="button"
              onClick={() => setViewMode('topology')}
              title={_t('chain_tree_view')}
              className={`px-2.5 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider transition-all ${
                viewMode === 'topology'
                  ? 'pill-solid font-medium text-ink shadow-xs'
                  : 'text-mut hover:text-ink'
              }`}
            >
              Arbre
            </button>
          </div>

          {/* Contrôle de Zoom */}
          <div className="flex items-center gap-0.5 border border-line rounded-full bg-wash/60 px-1 py-0.5">
            <button
              type="button"
              onClick={() => setZoom(z => Math.max(0.7, z - 0.15))}
              className="w-5 h-5 flex items-center justify-center text-[11px] text-mut hover:text-ink transition-colors"
              title={_t('chain_zoom_out')}
            >
              −
            </button>
            <span className="font-mono text-[9.5px] text-faint px-1">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              onClick={() => setZoom(z => Math.min(1.4, z + 0.15))}
              className="w-5 h-5 flex items-center justify-center text-[11px] text-mut hover:text-ink transition-colors"
              title="Zoom avant"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              className="text-[9px] font-mono text-faint hover:text-ink px-1 border-l border-line"
              title={_t('chain_zoom_reset')}
            >
              1:1
            </button>
          </div>
        </div>
      </div>

      {/* ── ZONE CENTRALE DE LA CHAÎNE D'ATTAQUE ── */}
      <div className="flex-1 overflow-auto p-4 relative bg-canvas/40" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
        {viewMode === 'pipeline' ? (
          /* ── VUE 1 : PIPELINE KILL-CHAIN SEQUENTIEL EN 4 PHASES ── */
          <div className="flex gap-3.5 h-full min-h-[380px] overflow-x-auto pb-2 items-stretch scrollbar-thin">
            {STAGES.map((stage, sIdx) => {
              const nodes = (stagedNodes[stage.id] || []).filter(filterNode);
              const totalCount = (stagedNodes[stage.id] || []).length;

              return (
                <div
                  key={stage.id}
                  className="min-w-[240px] w-[260px] flex flex-col rounded-ui border border-line bg-wash/50 overflow-hidden shadow-xs hover:border-line2 transition-all shrink-0 relative"
                >
                  {/* Tête de colonne */}
                  <div className="p-3 border-b border-line bg-wash/80 flex items-center justify-between gap-2 shrink-0">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`w-6 h-6 rounded-full border flex items-center justify-center ${stage.badge}`}>
                        {stage.icon}
                      </span>
                      <div className="min-w-0">
                        <h4 className="text-[12px] font-semibold text-ink truncate leading-tight">{stage.label}</h4>
                        <p className="text-[10px] text-faint truncate leading-none mt-0.5">{stage.sub}</p>
                      </div>
                    </div>
                    <span className="font-mono text-[10.5px] px-2 py-0.5 rounded-full border border-line bg-inset text-ash font-medium">
                      {totalCount}
                    </span>
                  </div>

                  {/* Connecteur visuel Kill-Chain vers l'étape suivante */}
                  {sIdx < STAGES.length - 1 && (
                    <div className="hidden xl:flex absolute -right-3 top-5 z-20 w-6 h-6 rounded-full border border-line bg-wash items-center justify-center text-mut shadow-xs pointer-events-none">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    </div>
                  )}

                  {/* Liste des cartes d'actifs dans cette phase */}
                  <div className="flex-1 overflow-y-auto p-2.5 space-y-2 min-h-[220px]">
                    {nodes.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-4 text-faint">
                        <span className="text-[11px] font-mono">{_t('chain_waiting')}</span>
                      </div>
                    ) : (
                      nodes.map(node => {
                        const isSelected = selectedNode?.id === node.id;
                        const isFinding = Boolean(node.finding);

                        return (
                          <div
                            key={node.id}
                            onClick={() => setSelectedNode(node)}
                            className={`p-2.5 rounded-ui border cursor-pointer transition-all duration-150 ${
                              isSelected
                                ? 'border-volt/80 bg-voltlite/40 shadow-xs ring-1 ring-volt/40'
                                : isFinding
                                ? 'border-danger/40 bg-dangertint/30 hover:border-danger hover:bg-dangertint/50'
                                : 'border-line/70 bg-inset/70 hover:border-line2 hover:bg-wash'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-1.5 mb-1.5">
                              <span className={`font-mono text-[9px] uppercase px-1.5 py-0.5 rounded tracking-wider ${
                                isFinding ? 'bg-danger text-white font-bold' : 'bg-wash text-mut border border-line'
                              }`}>
                                {node.k}
                              </span>

                              <div className="flex items-center gap-1.5 text-[9.5px] font-mono text-faint">
                                <span>{Math.round(node.c * 100)}%</span>
                                <span className="w-1.5 h-1.5 rounded-full" style={{
                                  backgroundColor: node.c > 0.85 ? '#34d399' : node.c > 0.6 ? '#fbbf24' : '#94a3b8'
                                }} />
                              </div>
                            </div>

                            <p className="text-[11.5px] font-mono text-ink break-all line-clamp-2 leading-snug">
                              {node.v}
                            </p>

                            {node.finding?.detail && (
                              <p className="text-[10.5px] text-ash mt-1 line-clamp-1 italic">
                                {node.finding.detail}
                              </p>
                            )}

                            <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-line/40 text-[9.5px] font-mono text-faint">
                              <span>{node.s} source{node.s > 1 ? 's' : ''}</span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCopy(node.v, node.id);
                                }}
                                className="text-faint hover:text-ink px-1 rounded transition-colors"
                                title="Copy value"
                              >
                                {copiedKey === node.id ? _t('copied') : _t('copy')}
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* ── VUE 2 : ARBRE TOPOLOGIQUE & CONNEXIONS D'ESCALADE ── */
          <div className="h-full min-h-[420px] rounded-ui border border-line bg-wash/30 p-4 relative flex flex-col justify-between overflow-hidden">
            <div className="flex items-center justify-between pb-3 border-b border-line text-[11px] font-mono text-faint shrink-0">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-cyan" /> Cibles (Recon)</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-volt" /> Routes & Ports (Surface)</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-warn" /> Keys & Auth (Secrets)</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-danger" /> Failles Exploitation (Impact)</span>
              </div>
              <span>{activeLinks.length} escalation paths mapped</span>
            </div>

            <div className="flex-1 py-4 flex items-center justify-between gap-6 overflow-x-auto">
              {STAGES.map((stage) => {
                const nodes = (stagedNodes[stage.id] || []).filter(filterNode).slice(0, 10);
                const hasMore = (stagedNodes[stage.id] || []).length > 10;

                return (
                  <div key={stage.id} className="flex-1 min-w-[200px] flex flex-col items-center gap-3">
                    <div className={`px-3 py-1.5 rounded-full border text-[10.5px] font-mono font-medium flex items-center gap-1.5 ${stage.badge}`}>
                      {stage.icon}
                      <span>{stage.label}</span>
                    </div>

                    <div className="w-full space-y-2 flex flex-col items-center">
                      {nodes.map(n => {
                        const isSelected = selectedNode?.id === n.id;
                        return (
                          <div
                            key={n.id}
                            onClick={() => setSelectedNode(n)}
                            className={`w-full max-w-[230px] p-2 rounded-ui border text-left cursor-pointer transition-all duration-200 ${
                              isSelected
                                ? 'border-volt bg-voltlite shadow-md ring-1 ring-volt'
                                : 'border-line bg-inset/90 hover:border-line2 hover:scale-[1.02]'
                            }`}
                          >
                            <div className="flex items-center justify-between text-[9px] font-mono text-faint mb-1">
                              <span className="uppercase">{n.k}</span>
                              <span>{Math.round(n.c * 100)}%</span>
                            </div>
                            <p className="text-[11px] font-mono text-ink truncate" title={n.v}>
                              {n.v}
                            </p>
                          </div>
                        );
                      })}
                      {hasMore && (
                        <span className="text-[10px] font-mono text-faint">
                          + {(stagedNodes[stage.id] || []).length - 10} autres nœuds...
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="pt-3 border-t border-line text-[10.5px] font-mono text-faint flex items-center justify-between shrink-0">
              <span>Select an asset to unfold its vector and injection details.</span>
              <button
                type="button"
                onClick={() => setViewMode('pipeline')}
                className="text-volt hover:underline"
              >
                Switch to full column view →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── TIROIR D'INSPECTION TACTIQUE DU NŒUD SÉLECTIONNÉ ── */}
      {selectedNode && (
        <div className="border-t border-line bg-wash/95 p-4 shrink-0 shadow-lg animate-fadeIn relative">
          <button
            type="button"
            onClick={() => setSelectedNode(null)}
            className="absolute right-4 top-3 text-faint hover:text-ink text-[13px] font-mono"
            title="Close the panel"
          >
            ✕
          </button>

          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-volt/20 text-volt border border-volt/30">
                {selectedNode.k}
              </span>
              <span className="text-[13px] font-medium text-ink">
                Node & Vector Inspector
              </span>
              <span className="font-mono text-[10.5px] text-ash">
                · Confiance : {Math.round(selectedNode.c * 100)}% ({selectedNode.s} source{selectedNode.s > 1 ? 's' : ''})
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleCopy(selectedNode.v, 'inspect-copy')}
                className="pill-ghost btn-strike px-3 py-1 text-[11px] font-mono uppercase tracking-wider"
              >
                {copiedKey === 'inspect-copy' ? _t('copied') : 'Copy Value'}
              </button>

              {selectedNode.v.startsWith('http') && (
                <button
                  type="button"
                  onClick={() => handleCopy(`curl -ik -s "${selectedNode.v}"`, 'inspect-curl')}
                  className="pill-cta btn-strike px-3 py-1 text-[11px] font-mono uppercase tracking-wider"
                >
                  {copiedKey === 'inspect-curl' ? '✓ cURL copied' : 'Generate cURL'}
                </button>
              )}
            </div>
          </div>

          <pre className="terminal-bg p-2.5 rounded text-[11.5px] font-mono text-ink break-all max-h-[90px] overflow-y-auto mb-1 select-text">
            {selectedNode.v}
          </pre>

          {selectedNode.finding && (
            <div className="mt-2 p-2.5 rounded border border-danger/40 bg-dangertint text-[11.5px] space-y-1">
              <div className="flex items-center gap-2 text-danger font-semibold font-mono text-[11px] uppercase">
                <span>⚠️ Vulnerability Proof ({selectedNode.finding.severity || 'HIGH'})</span>
              </div>
              <p className="text-ink">{selectedNode.finding.detail || selectedNode.finding.poc}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
