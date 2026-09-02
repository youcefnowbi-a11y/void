import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = '/api';

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

  return (
    <form onSubmit={save} className="p-1 space-y-3">
      {/* identité */}
      <div className="grid grid-cols-[90px_1fr] gap-x-3 gap-y-2.5 items-center">
        <label htmlFor="pe-name" className="text-[10px] uppercase tracking-widest text-mut">nom</label>
        <input id="pe-name" value={form.name}
          onChange={(e) => set('name', e.target.value)}
          placeholder="VOIDFORGE"
          className="rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors" />

        <label htmlFor="pe-arch" className="text-[10px] uppercase tracking-widest text-mut">archétype</label>
        <input id="pe-arch" value={form.archetype}
          onChange={(e) => set('archetype', e.target.value)}
          placeholder="elite autonomous offensive-security operator"
          className="rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors" />

        <label htmlFor="pe-tone" className="text-[10px] uppercase tracking-widest text-mut">ton</label>
        <input id="pe-tone" value={form.tone} list="tone-suggestions"
          onChange={(e) => set('tone', e.target.value)}
          placeholder="surgical and decisive"
          className="rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors" />
        <datalist id="tone-suggestions">
          {TONE_SUGGESTIONS.map(t => <option key={t} value={t} />)}
        </datalist>
      </div>

      {/* interrupteurs */}
      {Object.entries(TOGGLES).map(([key, options]) => (
        <div key={key} className="grid grid-cols-[90px_1fr] gap-x-3 items-center">
          <span className="text-[10px] uppercase tracking-widest text-mut">
            {key === 'mission_focus' ? 'doctrine' : key === 'verbosity' ? 'verbeux' : 'langue'}
          </span>
          <div className="flex rounded-full border border-line bg-wash p-0.5 w-fit">
            {options.map((o) => (
              <button key={o} type="button" onClick={() => set(key, o)}
                className={`px-2.5 py-1 rounded-full text-[10px] uppercase tracking-wider transition-all
                  ${form[key] === o ? 'bg-snow text-[#0A0A0A] font-semibold' : 'text-mut hover:text-ink'}`}>
                {o}
              </button>
            ))}
          </div>
        </div>
      ))}
      {focusHint && (
        <p className="text-[10px] text-mut -mt-1 ml-[102px]">↳ {focusHint}</p>
      )}

      {/* phrases signature */}
      <div className="grid grid-cols-[90px_1fr] gap-x-3 items-center">
        <label htmlFor="pe-catch" className="text-[10px] uppercase tracking-widest text-mut">signature</label>
        <input id="pe-catch" value={form.catchphrases}
          onChange={(e) => set('catchphrases', e.target.value)}
          placeholder="Mapping the attack surface., Nothing hides from the void."
          className="rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors" />
      </div>

      {/* directives libres */}
      <div className="grid grid-cols-[90px_1fr] gap-x-3 items-start">
        <label htmlFor="pe-extra" className="text-[10px] uppercase tracking-widest text-mut pt-1.5">directives</label>
        <div>
          <textarea id="pe-extra" value={form.extra_directives} rows={16}
            onChange={(e) => set('extra_directives', e.target.value)}
            placeholder={'Doctrine libre — priorités, habitudes, rituels.\nex : Prioritize Supabase exposures. Always check GraphQL before REST.'}
            className="w-full rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] leading-relaxed resize-y text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors max-h-[340px]" />
          <p className="mt-1 text-[9.5px] text-faint">
            {form.extra_directives.length.toLocaleString()} caractères chargés — {form.extra_directives.length > 4000
              ? 'ta directive longue est bien là, intégralement (la fenêtre défile).'
              : 'directive courte chargée.'}
          </p>
        </div>
      </div>

      {/* statut + actions */}
      <div className="flex items-center justify-between pt-1 gap-3">
        <span className={`text-[10px] break-words flex-1 ${
          msg?.ok === true ? 'text-ok font-semibold' :
          msg?.ok === false ? 'text-danger font-semibold' :
          loaded ? 'text-mut' : 'text-warn animate-pulse'
        }`}>
          {msg ? msg.text : loaded ? 'masque actif — appliqué à la prochaine mission (CLI + dashboard)' : 'chargement du masque...'}
        </span>
        <div className="flex gap-2 shrink-0">
          <button type="button" onClick={reset} disabled={saving}
            className="btn-strike rounded-full border border-line2 bg-paper text-ink font-disp font-semibold uppercase tracking-[.14em] text-[11px] px-3.5 py-1.5 disabled:opacity-50">
            défaut
          </button>
          <button type="submit" disabled={saving}
            className={`btn-strike rounded-full bg-snow text-[#0A0A0A] font-disp font-semibold uppercase tracking-[.14em] text-[11.5px] px-4 py-1.5 transition-all ${
              saving ? 'opacity-50 cursor-wait' : ''
            }`}>
            {saving ? '...' : 'graver'}
          </button>
        </div>
      </div>

      {/* aperçu du prompt réellement injecté */}
      {rendered && (
        <details className="pt-1">
          <summary className="text-[10px] uppercase tracking-widest text-mut cursor-pointer hover:text-volt select-none">
            aperçu du prompt injecté
          </summary>
          <pre className="mt-2 max-h-52 overflow-y-auto terminal-bg rounded-lg border border-line p-2.5 whitespace-pre-wrap break-words text-slate">
            {rendered}
          </pre>
        </details>
      )}
    </form>
  );
}
