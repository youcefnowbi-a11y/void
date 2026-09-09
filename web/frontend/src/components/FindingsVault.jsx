import React, { useState, useMemo } from 'react';
import { t as _t } from '../i18n.js';

const SEV_CONFIG = {
  critical: { label: _t('sev_critical'), border: 'border-danger', dot: 'bg-danger', tint: 'bg-dangertint', text: 'text-danger' },
  high:     { label: _t('sev_high'),     border: 'border-warn',   dot: 'bg-warn',   tint: 'bg-warntint',   text: 'text-warn' },
  medium:   { label: _t('sev_medium'),     border: 'border-warn/60',dot: 'bg-warn/70',tint: 'bg-hover',    text: 'text-warn' },
  low:      { label: _t('sev_low'),    border: 'border-ok/50',  dot: 'bg-ok',     tint: 'bg-oktint',     text: 'text-ok' },
  info:     { label: 'INFO',      border: 'border-line2',  dot: 'bg-mut',    tint: 'bg-hover',      text: 'text-mut' },
};

export default function FindingsVault({ findings = [] }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  const filteredFindings = useMemo(() => {
    return findings.filter(f => {
      const sev = (f.severity || 'info').toLowerCase();
      if (filter !== 'all' && sev !== filter) return false;
      if (search) {
        const term = search.toLowerCase();
        const text = `${f.title || ''} ${f.detail || ''} ${f.tool || ''} ${f.poc || ''}`.toLowerCase();
        return text.includes(term);
      }
      return true;
    });
  }, [findings, filter, search]);

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  };

  if (findings.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-6 panel select-none">
        <div className="w-12 h-12 rounded-full border border-line bg-wash/80 flex items-center justify-center text-ok mb-3 shadow-xs">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <span className="eyebrow mb-1">registre des failles</span>
        <h3 className="text-[14px] font-medium text-ink mb-1">{_t('vault_empty_title')}</h3>
        <p className="text-[12px] text-ash max-w-sm leading-relaxed mb-4">
          As soon as a breach, API leak or access-control flaw is proven, it appears here with its evidence.</p>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-inset font-mono text-[10.5px] text-faint">
          <span className="w-1.5 h-1.5 rounded-full bg-ok" />
          <span>{_t('vault_empty_sub')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col panel overflow-hidden">
      {/* Header & Filtres */}
      <div className="px-4 py-3 border-b border-line bg-wash/40 shrink-0 space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-danger">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <span className="text-[12px] font-medium text-ink tracking-tight">{_t('vault_title')}</span>
          </div>
          <span className="font-mono text-[10px] text-faint uppercase tracking-wider">
            {filteredFindings.length} / {findings.length} constat{findings.length > 1 ? 's' : ''}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={_t('vault_filter')}
            className="w-full rounded-ui border border-line bg-inset px-2.5 py-1.5 text-[11.5px] font-mono text-ink placeholder:text-faint focus:outline-none focus:border-volt/60 transition-colors"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          {['all', 'critical', 'high', 'medium', 'low', 'info'].map(sev => (
            <button
              key={sev}
              type="button"
              onClick={() => setFilter(sev)}
              className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider shrink-0 transition-colors border ${
                filter === sev
                  ? 'border-volt/60 bg-voltlite text-cyan font-medium'
                  : 'border-line hover:border-line2 bg-paper text-ash hover:text-ink'
              }`}
            >
              {sev === 'all' ? 'Toutes' : sev}
            </button>
          ))}
        </div>
      </div>

      {/* Liste des constatations */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredFindings.map((f, idx) => {
          const s = SEV_CONFIG[(f.severity || 'info').toLowerCase()] || SEV_CONFIG.info;
          const cardId = `finding-${idx}`;
          return (
            <div
              key={cardId}
              className={`rounded-xl border border-line ${s.tint} p-3.5 space-y-2 transition-all shadow-xs select-text`}
            >
              <div className="flex items-center justify-between gap-2 border-b border-line/60 pb-2">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${s.dot}`} />
                  <span className={`text-[10px] uppercase font-mono font-bold tracking-wider ${s.text}`}>
                    {s.label}
                  </span>
                  {f.tool && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-inset border border-line text-faint">
                      {f.tool}
                    </span>
                  )}
                </div>

                {f.poc && (
                  <button
                    type="button"
                    onClick={() => handleCopy(f.poc, cardId)}
                    className="px-2 py-0.5 rounded-full text-[9.5px] font-mono border border-line bg-paper text-ash hover:text-ink uppercase tracking-wider"
                  >
                    {copiedId === cardId ? _t('vault_poc_copied') : _t('vault_copy_poc')}
                  </button>
                )}
              </div>

              <p className="text-[12.5px] leading-relaxed text-ink font-medium">
                {f.title || f.summary || f.detail || _t('vault_unnamed')}
              </p>

              {f.detail && f.title && (
                <p className="text-[11.5px] leading-relaxed text-ash font-mono">
                  {f.detail}
                </p>
              )}

              {f.poc && (
                <div className="rounded-lg border border-line/80 bg-[var(--termbg)] p-2 overflow-x-auto text-[10.5px] font-mono text-[var(--term-ink)]">
                  <code>{f.poc}</code>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
