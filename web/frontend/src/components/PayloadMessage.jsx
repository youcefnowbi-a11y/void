import React, { useState, useMemo } from 'react';
import { t as _t } from '../i18n.js';
import MarkdownMessage from './MarkdownMessage';

function isHeavyPayload(text) {
  if (!text || typeof text !== 'string') return false;
  const trimmed = text.trim();
  if (trimmed.length < 120) return false;

  // Détection URL-encodé lourd (%7B%22, %20, %2F, etc.)
  const percentMatches = (trimmed.match(/%[0-9A-Fa-f]{2}/g) || []).length;
  if (percentMatches > 8) return true;

  // Détection JWT ou Cookie brut géant
  if (trimmed.startsWith('eyJ') && trimmed.includes('.') && trimmed.length > 150) return true;
  if ((trimmed.startsWith('__session=') || trimmed.includes('; __client=')) && trimmed.length > 150) return true;

  return false;
}

function tryDecodePayload(text) {
  try {
    let decoded = decodeURIComponent(text);
    // Tente un parsing JSON si c'est du JSON stringifié
    if (decoded.startsWith('{') && decoded.endsWith('}')) {
      try {
        const parsed = JSON.parse(decoded);
        return JSON.stringify(parsed, null, 2);
      } catch {
        return decoded;
      }
    }
    return decoded;
  } catch {
    return text;
  }
}

export default function PayloadMessage({ text }) {
  const isPayload = useMemo(() => isHeavyPayload(text), [text]);
  const [expanded, setExpanded] = useState(false);
  const [showDecoded, setShowDecoded] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!isPayload) {
    return <MarkdownMessage content={text} />;
  }

  const decodedText = useMemo(() => tryDecodePayload(text), [text]);
  const displayText = showDecoded ? decodedText : text;
  const byteLength = new Blob([text]).size;

  const handleCopy = () => {
    navigator.clipboard.writeText(displayText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="space-y-2">
      {/* Carte d'inspection compacte */}
      <div className="rounded-xl border border-line bg-wash/90 p-2.5 space-y-2 shadow-xs select-none">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 text-[11px] font-mono">
            <span className="w-5 h-5 rounded-full bg-voltlite text-cyan flex items-center justify-center">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </span>
            <span className="font-medium text-ink tracking-tight">{_t('payload_title')}</span>
            <span className="text-[9.5px] px-2 py-0.5 rounded-full bg-inset border border-line text-faint">
              {byteLength} octets
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setShowDecoded(!showDecoded)}
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showDecoded
                  ? 'border-volt/60 bg-voltlite text-cyan'
                  : 'border-line hover:border-line2 bg-paper text-ash hover:text-ink'
              }`}
              title={_t('payload_decode')}
            >
              {showDecoded ? _t('payload_raw') : _t('payload_decode_url')}
            </button>

            <button
              type="button"
              onClick={handleCopy}
              className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider border border-line hover:border-line2 bg-paper text-ash hover:text-ink transition-colors"
              title="Copier le payload"
            >
              {copied ? _t('copied') : _t('copy')}
            </button>

            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider border border-line hover:border-line2 bg-paper text-ash hover:text-ink transition-colors flex items-center gap-1"
            >
              <span>{expanded ? _t('payload_collapse') : _t('payload_expand')}</span>
              <span className="text-[9px]">{expanded ? '↑' : '↓'}</span>
            </button>
          </div>
        </div>

        {/* Aperçu ou vue dépliée */}
        <div className="rounded-lg border border-line/60 bg-[var(--termbg)] p-2.5 overflow-x-auto text-[11px] font-mono select-text text-[var(--term-ink)]">
          <pre className={`m-0 leading-relaxed font-mono whitespace-pre-wrap break-all ${
            expanded ? 'max-h-[360px] overflow-y-auto' : 'line-clamp-2'
          }`}>
            {displayText}
          </pre>
        </div>

        {!expanded && (
          <p className="text-[9.5px] font-mono text-faint text-right pr-1">
            Payload compressed to keep the room clear · click expand to inspect
          </p>
        )}
      </div>
    </div>
  );
}
