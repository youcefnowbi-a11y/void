import React, { useState } from 'react';
import { t as _t } from '../i18n.js';

export default function SessionSidebar({
  open = false,
  onClose,
  reports = [],
  onSelectReport,
  onNewSession,
  onOpenParams,
  wsStatus = 'idle',
  missionText = '',
}) {
  const [search, setSearch] = useState('');

  React.useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && open) onClose?.();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const filteredReports = reports.filter(r =>
    r.name?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-40 flex animate-fadeIn">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Volet latéral gauche */}
      <aside className="relative z-50 w-full sm:w-[360px] h-full bg-paper border-r border-line flex flex-col shadow-2xl overflow-hidden select-none">
        {/* Header */}
        <div className="px-4 py-3.5 border-b border-line flex items-center justify-between gap-2 bg-wash/60 shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-full border border-line bg-inset flex items-center justify-center">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-cyan">
                <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
              </svg>
            </span>
            <div>
              <h2 className="text-[13px] font-medium text-ink tracking-tight">Missions & Sessions</h2>
              <p className="text-[10px] text-faint uppercase tracking-wider font-mono">{_t('sidebar_title')}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 rounded-full border border-line text-mut hover:text-danger hover:border-danger/40 flex items-center justify-center transition-colors text-xs"
            title={_t('sidebar_close')}
          >
            ✕
          </button>
        </div>

        {/* Bouton Nouvelle Campagne */}
        <div className="p-3 border-b border-line bg-wash/20 shrink-0">
          <button
            type="button"
            onClick={() => {
              if (onNewSession) onNewSession();
              if (onClose) onClose();
            }}
            className="w-full pill-cta btn-strike py-2 px-4 flex items-center justify-center gap-2 text-[11px] uppercase tracking-wider shadow-sm"
          >
            <span>+</span>
            <span>Nouvelle Campagne</span>
          </button>
        </div>

        {/* Cible courante */}
        <div className="px-4 py-3 border-b border-line bg-wash/40 shrink-0 space-y-1.5">
          <span className="eyebrow">session active</span>
          <div className="flex items-center justify-between gap-2">
            <p className="text-[12px] font-mono text-ink truncate font-medium">
              {missionText || 'passive watch — no target'}
            </p>
            <span className={`w-2 h-2 rounded-full shrink-0 ${
              wsStatus === 'running' ? 'bg-volt animate-pulse' :
              wsStatus === 'complete' ? 'bg-gold' : 'bg-mut'
            }`} />
          </div>
        </div>

        {/* Recherche dans les rapports passés */}
        <div className="p-3 border-b border-line bg-wash/10 shrink-0">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={_t('sidebar_search')}
            className="w-full rounded-ui border border-line bg-inset px-2.5 py-1.5 text-[11.5px] font-mono text-ink placeholder:text-faint focus:outline-none focus:border-volt/60 transition-colors"
          />
        </div>

        {/* Liste des missions archivées */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          <span className="px-1 text-[10px] font-mono uppercase tracking-wider text-faint block mb-1">
            report archives ({filteredReports.length})
          </span>

          {filteredReports.length === 0 ? (
            <div className="text-center py-8 text-faint text-[12px] font-mono">
              Aucune archive correspondante
            </div>
          ) : (
            filteredReports.map((r, idx) => (
              <button
                key={r.name || idx}
                type="button"
                onClick={() => {
                  if (onSelectReport) onSelectReport(r);
                  if (onClose) onClose();
                }}
                className="w-full rounded-xl border border-line hover:border-line2 bg-wash/50 hover:bg-wash p-2.5 flex items-center justify-between gap-2 text-left transition-all group"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-cyan shrink-0">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span className="font-mono text-[11px] font-medium text-ink truncate">
                      {r.name}
                    </span>
                  </div>
                  <span className="text-[9.5px] text-faint font-mono mt-0.5 block">
                    {r.mtime || _t('sidebar_archived')}
                  </span>
                </div>
                {r.size !== undefined && (
                  <span className="font-mono text-[10px] text-mut shrink-0 group-hover:text-ink">
                    {(r.size / 1024).toFixed(1)}K
                  </span>
                )}
              </button>
            ))
          )}
        </div>

        {/* Footer avec accès aux paramètres */}
        <div className="p-3 border-t border-line bg-wash/50 shrink-0 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              if (onOpenParams) onOpenParams();
              if (onClose) onClose();
            }}
            className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-ash hover:text-ink transition-colors px-2 py-1 rounded-lg hover:bg-hover w-full"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            <span>{_t('sidebar_settings')}</span>
          </button>
        </div>
      </aside>
    </div>
  );
}
