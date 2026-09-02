import React, { useState, useEffect } from 'react';
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
      setMsg({ ok: true, text: r.data.message || '✓ personnalité gravée' });
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
      setMsg({ ok: true, text: '✓ masque par défaut restauré' });
    } catch (e2) {
      setMsg({ ok: false, text: `✗ ${e2.response?.data?.detail || e2.message}` });
    } finally {
      setSaving(false);
    }
  };

  const focusHint = {
    speed: 'chaînes rapides, stop aux rendements décroissants',
    thoroughness: 'épuise chaque vecteur, recoupe chaque finding',
    stealth: 'volume minimal, sources passives d\'abord',
  }[form.mission_focus] || '';

  const inputCls = "w-full rounded-ui border border-line bg-inset px-3 py-2 text-[12.5px] text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint";
  const labelCls = "text-[9.5px] uppercase tracking-[.16em] text-mut";

  return (
    <form onSubmit={save} className="space-y-3.5">
      {/* identité */}
      <div className="grid grid-cols-[88px_1fr] gap-x-3 gap-y-2.5 items-center">
        <label htmlFor="pe-name" className={labelCls}>nom</label>
        <input id="pe-name" value={form.name}
          onChange={(e) => set('name', e.target.value)}
          placeholder="VOIDFORGE"
          className={inputCls} />

        <label htmlFor="pe-arch" className={labelCls}>archétype</label>
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
        <p className="text-[10.5px] text-faint -mt-1 ml-[100px]">↳ {focusHint}</p>
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
          <textarea id="pe-extra" value={form.extra_directives} rows={16}
            onChange={(e) => set('extra_directives', e.target.value)}
            placeholder={'Doctrine libre — priorités, habitudes, rituels.\nex : Prioritize Supabase exposures. Always check GraphQL before REST.'}
            className="w-full rounded-ui border border-line bg-inset px-3 py-2 text-[12.5px] leading-relaxed resize-y text-ink focus:outline-none focus:border-volt/60 transition-colors max-h-[340px] placeholder:text-faint" />
          <p className="mt-1.5 text-[10px] text-faint">
            {form.extra_directives.length.toLocaleString()} caractères chargés — {form.extra_directives.length > 4000
              ? 'ta directive longue est bien là, intégralement (la fenêtre défile).'
              : 'directive courte chargée.'}
          </p>
        </div>
      </div>

      {/* statut + actions */}
      <div className="flex items-center justify-between pt-1 gap-3">
        <span className={`text-[10.5px] break-words flex-1 ${
          msg?.ok === true ? 'text-ok' :
          msg?.ok === false ? 'text-danger' :
          loaded ? 'text-mut' : 'text-warn animate-pulse'
        }`}>
          {msg ? msg.text : loaded ? 'masque actif — appliqué à la prochaine mission (CLI + dashboard)' : 'chargement du masque...'}
        </span>
        <div className="flex gap-2 shrink-0">
          <button type="button" onClick={reset} disabled={saving}
            className="pill-ghost btn-strike px-3.5 py-1.5 text-[10.5px] uppercase tracking-[.1em]">
            défaut
          </button>
          <button type="submit" disabled={saving}
            className="pill-cta btn-strike px-4 py-1.5 text-[10.5px] uppercase tracking-[.1em]">
            {saving ? '...' : 'graver'}
          </button>
        </div>
      </div>

      {/* aperçu du prompt réellement injecté */}
      {rendered && (
        <details className="pt-1">
          <summary className="text-[10px] uppercase tracking-[.14em] text-mut cursor-pointer hover:text-ink select-none transition-colors">
            aperçu du prompt injecté
          </summary>
          <pre className="mt-2 max-h-52 overflow-y-auto terminal-bg rounded-ui border border-line p-2.5 whitespace-pre-wrap break-words">
            {rendered}
          </pre>
        </details>
      )}
    </form>
  );
}
