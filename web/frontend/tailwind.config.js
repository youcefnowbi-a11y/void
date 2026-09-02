/** @type {import('tailwindcss').Config} */
// ═══════════════════════════════════════════════════════════════════
// VOIDFORGE — DIMENSION. Les tokens vivent en variables CSS :
// deux thèmes (crépuscule par défaut, aurore en clair) sortent du
// même système. Source : design/DESIGN.md + design/ref/.
// ═══════════════════════════════════════════════════════════════════
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // surfaces — canaux RGB thémables (alpha via <alpha-value>)
        mist:   'rgb(var(--mist) / <alpha-value>)',   // void canvas — niveau 0
        paper:  'rgb(var(--paper) / <alpha-value>)',  // graphite — niveau 1
        wash:   'rgb(var(--wash) / <alpha-value>)',   // inset — niveau 1.5
        snow:   '#FFFFFF',                            // le seul plein, toujours blanc

        // texte — bone en premier, jamais blanc pur sur sombre
        ink:    'rgb(var(--ink) / <alpha-value>)',
        ash:    'rgb(var(--ash) / <alpha-value>)',
        smoke:  'rgb(var(--smoke) / <alpha-value>)',
        slate:  'rgb(var(--slate) / <alpha-value>)',
        mut:    'rgb(var(--mut) / <alpha-value>)',
        faint:  'rgb(var(--faint) / <alpha-value>)',

        // hairlines — jamais d'ombre pour la définition
        line:   'var(--line)',
        line2:  'var(--line2)',
        frost:  'var(--frost)',
        inset:  'var(--inset)',
        insetstrong: 'var(--inset-strong)',
        hover:  'var(--hover)',

        // le seul accent chromatique — washes et lueurs, JAMAIS de plein
        volt:   'rgb(var(--volt) / <alpha-value>)',
        voltsoft: 'var(--volt-soft)',
        voltlite: 'var(--voltlite)',
        cyan:   'rgb(var(--cyan) / <alpha-value>)',
        cyantint: 'var(--cyantint)',

        // signaux opérationnels — la sémantique prime (console de guerre)
        danger: 'rgb(var(--danger) / <alpha-value>)', dangertint: 'var(--dangertint)',
        warn:   'rgb(var(--warn) / <alpha-value>)',   warntint:   'var(--warntint)',
        ok:     'rgb(var(--ok) / <alpha-value>)',     oktint:     'var(--oktint)',
        info:   'rgb(var(--info) / <alpha-value>)',   infotint:   'var(--infotint)',
        gold:   'rgb(var(--gold) / <alpha-value>)',   goldtint:   'var(--goldtint)',
      },
      fontFamily: {
        sans: ['"DM Sans"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        disp: ['"Geist"', '"DM Sans"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      borderRadius: {
        ui:    '10px',    // inputs, ghost buttons internes
        card:  '24px',    // cards, panels
        large: '40px',    // grandes surfaces
        panel: '42px',    // le rayon signature des panels
      },
      boxShadow: {
        // la SEULE élévation du système — extraite de la nav flottante Dimension
        nav: 'rgba(255,255,255,0.02) 0px 3px 4.5px, rgba(0,0,0,0.04) 0px 10px 8px, rgba(0,0,0,0.1) 0px 4px 3px',
      },
    },
  },
  plugins: [],
}
