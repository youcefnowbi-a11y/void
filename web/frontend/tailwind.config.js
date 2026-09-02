/** @type {import('tailwindcss').Config} */
// ═══════════════════════════════════════════════════════════════════
// VOIDFORGE — DIMENSION, reconstruit de zéro.
// void canvas #0A0A0A · graphite #161616 · verre dépoli · pills 9999px
// hairlines 1px · UN violet (#6B62F2) en wash seulement · weight 500.
// La source de vérité : design/DESIGN.md (extraction Refero de dimension.dev).
// ═══════════════════════════════════════════════════════════════════
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // surfaces — la pile Dimension
        mist:   '#0A0A0A',                 // void canvas — niveau 0
        paper:  '#161616',                 // graphite — niveau 1
        wash:   '#1D1D1F',                 // inset — un cran au-dessus du graphite
        frost:  'rgba(212,212,212,0.08)',  // frosted glass — niveau 2 (translucide)
        snow:   '#FFFFFF',                 // snow white — niveau 3, le seul plein

        // texte — bone en premier, jamais blanc pur
        ink:    '#EDEDED',                 // bone — texte primaire sur sombre
        ash:    '#C2C2C2',                 // texte secondaire
        smoke:  '#B2B2B2',                 // texte désactivé / idle
        slate:  '#686868',                 // tertiaire, timestamps
        mut:    '#8E8E99',                 // labels discrets
        faint:  '#5C5C66',                 // le plus faible lisible

        // hairlines — jamais d'ombre pour la définition
        line:   'rgba(255,255,255,0.09)',
        line2:  'rgba(255,255,255,0.16)',

        // le seul accent chromatique — washes et lueurs, JAMAIS de plein
        volt:   '#6B62F2',
        voltlite: 'rgba(107,98,242,0.12)',
        cyan:   '#A78BFA',
        cyantint: 'rgba(167,139,250,0.10)',

        // signaux opérationnels — la sémantique prime (console de guerre)
        danger: '#F87171', dangertint: 'rgba(248,113,113,0.10)',
        warn:   '#FBBF24', warntint:   'rgba(251,191,36,0.10)',
        ok:     '#3DD68C', oktint:     'rgba(61,214,140,0.10)',
        info:   '#818CF8', infotint:   'rgba(129,140,248,0.10)',
        gold:   '#EDB36B', goldtint:   'rgba(237,179,107,0.10)', // ambre crépusculaire
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
