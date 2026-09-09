import React, { useState, useEffect } from 'react';
import { t as _t } from '../i18n.js';
import axios from 'axios';
import { API_BASE } from '../api.js';

/* LE MASQUE — la personnalité de la forge. Inputs 10px, toggles en pills,
   la white pill grave le masque. */

const TOGGLES = {
  verbosity: ['terse', 'medium', 'detailed'],
  language: ['en', 'fr', 'mixed'],
  mission_focus: ['speed', 'thoroughness', 'stealth'],
};

const TONE_SUGGESTIONS = [
  'surgical and decisive',
  'calm and clinical',
  'aggressive and relentless',
  'cold professional with dry humor',
  'veteran operator mentoring a junior analyst',
];

const EMPTY = {
  name: '', archetype: '', tone: '', verbosity: 'medium',
  language: 'en', mission_focus: 'thoroughness',
  catchphrases: '', extra_directives: '',
};

export default function PersonaPanel() {
  const [form, setForm] = useState(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null); // {ok, text}
  const [rendered, setRendered] = useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const load = async () => {
    try {
      const r = await axios.get(`${API_BASE}/persona`);
      const p = r.data.persona || {};
      setForm({
        name: p.name || '',
        archetype: p.archetype || '',
        tone: p.tone || '',
        verbosity: p.verbosity || 'medium',
        language: p.language || 'en',
        mission_focus: p.mission_focus || 'thoroughness',
        catchphrases: Array.isArray(p.catchphrases) ? p.catchphrases.join(', ') : (p.catchphrases || ''),
        extra_directives: p.extra_directives || '',
      });
      setRendered(r.data.rendered || '');
      setLoaded(true);
    } catch (e) {
      setMsg({ ok: false, text: `✗ masque illisible : ${e.response?.data?.detail || e.message}` });
    }
  };

  useEffect(() => { load(); }, []);

  const save = async (e) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setMsg({ ok: null, text: '⏳ gravure du masque...' });
    try {
      const r = await axios.post(`${API_BASE}/persona`, {
        persona: {
          ...form,
          catchphrases: form.catchphrases.split(',').map(s => s.trim()).filter(Boolean),
        },
      });
      setMsg({ ok: true, text: r.data.message || _t('persona_saved') });
      setRendered(r.data.rendered || '');
    } catch (e2) {
      setMsg({ ok: false, text: `✗ ${e2.response?.data?.detail || e2.message}` });
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const r = await axios.post(`${API_BASE}/persona/reset`);
      const p = r.data.persona || {};
      setForm({
        name: p.name || '', archetype: p.archetype || '', tone: p.tone || '',
        verbosity: p.verbosity || 'medium', language: p.language || 'en',
        mission_focus: p.mission_focus || 'thoroughness',
        catchphrases: (p.catchphrases || []).join(', '), extra_directives: p.extra_directives || '',
      });
      setRendered(r.data.rendered || '');
      setMsg({ ok: true, text: _t('persona_restored') });
    } catch (e2) {
      setMsg({ ok: false, text: `✗ ${e2.response?.data?.detail || e2.message}` });
    } finally {
      setSaving(false);
    }
  };

  const focusHint = {
    speed: _t('persona_speed'),
    thoroughness: _t('persona_thorough'),
    stealth: 'volume minimal, sources passives d\'abord',
  }[form.mission_focus] || '';

  const inputCls = "w-full rounded-ui border border-line bg-inset px-3 py-2 text-[12px] text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint";
  const labelCls = "text-[10px] uppercase tracking-[.14em] text-mut font-mono";

  return (
    <form onSubmit={save} className="space-y-3.5">
      {/* identité */}
      <div className="grid grid-cols-[88px_1fr] gap-x-3 gap-y-2.5 items-center">
        <label htmlFor="pe-name" className={labelCls}>nom</label>
        <input id="pe-name" value={form.name}
          onChange={(e) => set('name', e.target.value)}
          placeholder="REDACTED"
          className={inputCls} />

        <label htmlFor="pe-arch" className={labelCls}>{_t('persona_archetype')}</label>
        <input id="pe-arch" value={form.archetype}
          onChange={(e) => set('archetype', e.target.value)}
          placeholder="elite autonomous offensive-security operator"
          className={inputCls} />

        <label htmlFor="pe-tone" className={labelCls}>ton</label>
        <input id="pe-tone" value={form.tone} list="tone-suggestions"
          onChange={(e) => set('tone', e.target.value)}
          placeholder="surgical and decisive"
          className={inputCls} />
        <datalist id="tone-suggestions">
          {TONE_SUGGESTIONS.map(t => <option key={t} value={t} />)}
        </datalist>
      </div>

      {/* interrupteurs — le segment actif est la white pill */}
      {Object.entries(TOGGLES).map(([key, options]) => (
        <div key={key} className="grid grid-cols-[88px_1fr] gap-x-3 items-center">
          <span className={labelCls}>
            {key === 'mission_focus' ? 'doctrine' : key === 'verbosity' ? 'verbeux' : 'langue'}
          </span>
          <div className="flex rounded-full border border-line bg-insetstrong p-0.5 w-fit">
            {options.map((o) => (
              <button key={o} type="button" onClick={() => set(key, o)}
                className={`px-2.5 py-1 rounded-full text-[10px] uppercase tracking-[.08em] transition-all
                  ${form[key] === o ? 'pill-solid font-medium' : 'text-mut hover:text-ink'}`}>
                {o}
              </button>
            ))}
          </div>
        </div>
      ))}
      {focusHint && (
        <p className="text-[11px] text-faint -mt-1 ml-[100px]">↳ {focusHint}</p>
      )}

      {/* phrases signature */}
      <div className="grid grid-cols-[88px_1fr] gap-x-3 items-center">
        <label htmlFor="pe-catch" className={labelCls}>signature</label>
        <input id="pe-catch" value={form.catchphrases}
          onChange={(e) => set('catchphrases', e.target.value)}
          placeholder="Mapping the attack surface., Nothing hides from the void."
          className={inputCls} />
      </div>

      {/* directives libres */}
      <div className="grid grid-cols-[88px_1fr] gap-x-3 items-start">
        <label htmlFor="pe-extra" className={`${labelCls} pt-2`}>directives</label>
        <div>
          <textarea id="pe-extra" value={form.extra_directives} rows={6}
            onChange={(e) => set('extra_directives', e.target.value)}
            placeholder={_t('persona_doctrine_ph')}
            className="w-full rounded-ui border border-line bg-inset px-3 py-2 text-[12px] leading-relaxed resize-y text-ink focus:outline-none focus:border-volt/60 transition-colors max-h-[220px] placeholder:text-faint" />
          <div className="mt-1 flex items-center justify-between text-[10.5px]">
            <span className={form.extra_directives.length > 2000 ? 'text-danger font-mono font-medium' : 'text-faint font-mono'}>
              {form.extra_directives.length.toLocaleString()} / 2,000 characters
              {form.extra_directives.length > 2000 && ' (over limit: truncated to 2,000 by the backend)'}
            </span>
            <span className="text-[10px] text-faint italic">max 2 000 car.</span>
          </div>
        </div>
      </div>

      {/* aperçu du prompt réellement injecté */}
      {rendered && (
        <details className="pt-1">
          <summary className="text-[10px] uppercase tracking-[.14em] text-mut cursor-pointer hover:text-ink select-none transition-colors">
            preview of the injected prompt
          </summary>
          <pre className="mt-2 max-h-48 overflow-y-auto terminal-bg rounded-ui border border-line p-2.5 whitespace-pre-wrap break-words font-mono text-[11px]">
            {rendered}
          </pre>
        </details>
      )}

      {/* statut + actions (barre sticky en bas) */}
      <div className="sticky bottom-0 -mx-2 px-3 py-2.5 bg-paper/95 backdrop-blur-md border-t border-line/60 flex items-center justify-between gap-3 z-20 shadow-xs">
        <span className={`text-[11px] break-words flex-1 ${
          msg?.ok === true ? 'text-ok' :
          msg?.ok === false ? 'text-danger' :
          loaded ? 'text-mut' : 'text-warn animate-pulse'
        }`}>
          {msg ? msg.text : loaded ? _t('persona_active') : _t('persona_loading')}
        </span>
        <div className="flex gap-2 shrink-0">
          <button type="button" onClick={reset} disabled={saving}
            className="pill-ghost btn-strike px-3.5 py-1.5 text-[11px] uppercase tracking-[.1em]">
            default
          </button>
          <button type="submit" disabled={saving}
            className="pill-cta btn-strike px-4 py-1.5 text-[11px] uppercase tracking-[.1em]">
            {saving ? '...' : 'graver'}
          </button>
        </div>
      </div>
    </form>
  );
}
