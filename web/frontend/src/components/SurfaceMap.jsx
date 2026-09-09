import React, { useState, useMemo } from 'react';
import { t as _t } from '../i18n.js';

const TYPE_CONFIG = {
  domain: {
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
    ),
    label: 'Domaine', border: 'border-cyan/40', bg: 'bg-cyan/10', text: 'text-cyan'
  },
  endpoint: {
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
    ),
    label: 'Endpoint', border: 'border-volt/40', bg: 'bg-voltlite', text: 'text-volt'
  },
  port: {
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
        <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
        <line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>
      </svg>
    ),
    label: 'Port', border: 'border-warn/40', bg: 'bg-warntint', text: 'text-warn'
  },
  tech: {
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
      </svg>
    ),
    label: 'Techno', border: 'border-line2', bg: 'bg-inset', text: 'text-ash'
  },
  finding: {
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
    ),
    label: _t('surface_vuln'), border: 'border-danger/40', bg: 'bg-dangertint', text: 'text-danger'
  },
  default: {
    icon: (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
      </svg>
    ),
    label: 'Nœud', border: 'border-line', bg: 'bg-wash', text: 'text-mut'
  },
};

export default function SurfaceMap({ graph = { nodes: [], links: [] }, onSelectNode = null }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [copiedKey, setCopiedKey] = useState(null);

  const nodes = graph.nodes || [];

  const typeCounts = useMemo(() => {
    const counts = { all: nodes.length, domain: 0, endpoint: 0, port: 0, tech: 0, finding: 0 };
    nodes.forEach(n => {
      const k = (n.k || 'default').toLowerCase();
      if (counts[k] !== undefined) counts[k]++;
    });
    return counts;
  }, [nodes]);

  const filteredNodes = useMemo(() => {
    return nodes.filter(n => {
      const k = (n.k || 'default').toLowerCase();
      if (filter !== 'all' && k !== filter) return false;
      if (search) {
        const term = search.toLowerCase();
        return (n.v && n.v.toLowerCase().includes(term)) || (n.k && n.k.toLowerCase().includes(term));
      }
      return true;
    });
  }, [nodes, filter, search]);

  const handleCopy = (val, key) => {
    navigator.clipboard.writeText(val).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    });
  };

  if (nodes.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-6 panel select-none relative overflow-hidden">
        {/* Grille radar tactique d'arrière-plan */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
          <svg width="340" height="340" viewBox="0 0 340 340" fill="none" className="text-volt">
            <circle cx="170" cy="170" r="160" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
            <circle cx="170" cy="170" r="115" stroke="currentColor" strokeWidth="1" />
            <circle cx="170" cy="170" r="70" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" />
            <circle cx="170" cy="170" r="25" stroke="currentColor" strokeWidth="1" />
            <line x1="170" y1="5" x2="170" y2="335" stroke="currentColor" strokeWidth="0.8" strokeDasharray="3 3" />
            <line x1="5" y1="170" x2="335" y2="170" stroke="currentColor" strokeWidth="0.8" strokeDasharray="3 3" />
            <rect x="165" y="165" width="10" height="10" stroke="currentColor" strokeWidth="1" fill="none" />
          </svg>
        </div>

        <div className="relative z-10 flex flex-col items-center">
          <div className="w-12 h-12 rounded-full border border-line2 bg-wash/90 flex items-center justify-center text-cyan mb-3 shadow-xs relative">
            <span className="absolute inset-0 rounded-full bg-volt/10 animate-ping opacity-25" />
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
          </div>
          <span className="eyebrow mb-1">radar tactique</span>
          <h3 className="text-[14px] font-medium text-ink mb-1">Surface d'Attaque Dormante</h3>
          <p className="text-[12px] text-ash max-w-sm leading-relaxed mb-4">
            Domains, API routes, ports and technologies discovered by the agent will order themselves here in real time.</p>
          <div className="inline-flex items-center gap-2.5 px-3 py-1.5 rounded-full border border-line bg-inset font-mono text-[10.5px] text-faint shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-volt/60 animate-pulse" />
            <span>{_t('surface_empty_sub')}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col panel overflow-hidden">
      {/* En-tête avec compteurs et filtre de recherche */}
      <div className="px-4 py-3 border-b border-line bg-wash/40 shrink-0 space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-cyan">
              <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
            <span className="text-[12px] font-medium text-ink tracking-tight">{_t('surface_title')}</span>
          </div>
          <span className="font-mono text-[10px] text-faint uppercase tracking-wider">
            {filteredNodes.length} / {nodes.length} nœud{nodes.length > 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filtrer domaine, endpoint, port..."
              className="w-full rounded-ui border border-line bg-inset px-2.5 py-1.5 text-[11.5px] font-mono text-ink placeholder:text-faint focus:outline-none focus:border-volt/60 transition-colors"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-faint hover:text-ink text-xs"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Pilules de catégories */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pt-0.5">
          {[
            { id: 'all', label: 'Tous', count: typeCounts.all },
            { id: 'domain', label: 'Domaines', count: typeCounts.domain },
            { id: 'endpoint', label: 'Endpoints', count: typeCounts.endpoint },
            { id: 'port', label: 'Ports', count: typeCounts.port },
            { id: 'tech', label: 'Technos', count: typeCounts.tech },
            { id: 'finding', label: 'Failles', count: typeCounts.finding },
          ].map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => setFilter(t.id)}
              className={`px-2.5 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider shrink-0 transition-colors border ${
                filter === t.id
                  ? 'border-volt/60 bg-voltlite text-cyan font-medium'
                  : 'border-line hover:border-line2 bg-paper text-ash hover:text-ink'
              }`}
            >
              {t.label}
              {t.count > 0 && <span className="ml-1 opacity-70">({t.count})</span>}
            </button>
          ))}
        </div>
      </div>

      {/* Liste des nœuds de la surface */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {filteredNodes.map((n, idx) => {
          const cfg = TYPE_CONFIG[(n.k || 'default').toLowerCase()] || TYPE_CONFIG.default;
          const nodeKey = `${n.k || 'node'}-${n.v}-${idx}`;
          return (
            <div
              key={nodeKey}
              className={`rounded-xl border border-line hover:border-line2 bg-wash/60 hover:bg-wash p-2.5 flex items-center justify-between gap-3 transition-colors group select-text`}
            >
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <span className={`w-7 h-7 rounded-lg border ${cfg.border} ${cfg.bg} flex items-center justify-center text-xs shrink-0`}>
                  {cfg.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-[9.5px] uppercase font-mono tracking-wider font-semibold ${cfg.text}`}>
                      {cfg.label}
                    </span>
                    {n.method && (
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-inset border border-line text-faint uppercase font-bold">
                        {n.method}
                      </span>
                    )}
                    {n.status && (
                      <span className={`text-[9.5px] font-mono ${
                        String(n.status).startsWith('2') ? 'text-ok' :
                        String(n.status).startsWith('4') ? 'text-warn' : 'text-danger'
                      }`}>
                        HTTP {n.status}
                      </span>
                    )}
                  </div>
                  <p className="text-[12px] font-mono text-ink truncate leading-tight mt-0.5">
                    {n.v}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  onClick={() => handleCopy(n.v, nodeKey)}
                  className="px-2 py-0.5 rounded-full text-[9.5px] font-mono border border-line bg-paper text-ash hover:text-ink hover:border-line2 uppercase"
                  title="Copier la valeur"
                >
                  {copiedKey === nodeKey ? _t('copied') : _t('copy')}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
