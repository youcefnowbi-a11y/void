/** @type {import('tailwindcss').Config} */
// VOIDFORGE design tokens — "DIMENSION" (the dusk-lit revolution).
// Matte void canvas, frosted graphite surfaces, hairline borders, pill controls,
// ONE chromatic accent: dusk violet #6B62F2 — gradient washes only, never fills.
// The Linear/Vercel/Raycast/Dimension school — quiet, editorial, weight-500.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        mist:   '#0A0A0A',   // void canvas — the base dark plane
        paper:  '#161616',   // graphite — elevated panels, nav, modals
        wash:   '#1D1D1F',   // inset/hover surface, one step above graphite
        ink:    '#EDEDED',   // bone — primary text on dark (glare-safe)
        slate:  '#C2C2C2',   // ash — secondary text
        mut:    '#8E8E99',   // muted labels, tertiary metadata
        faint:  '#5C5C66',   // faintest text — dim mais lisible
        snow:   '#FFFFFF',   // snow white — the ONLY filled CTA
        line:   'rgba(255,255,255,0.09)',   // hairline on dark
        line2:  'rgba(255,255,255,0.16)',   // strong hairline
        volt:   '#6B62F2',   // dusk violet — washes & pulses only, never fills
        voltlite: 'rgba(107,98,242,0.12)',
        cyan:   '#A78BFA',   // gradient partner — light violet
        cyantint: 'rgba(167,139,250,0.10)',
        danger: '#F87171',   // soft signal red (operational)
        dangertint: 'rgba(248,113,113,0.10)',
        warn:   '#FBBF24',   // high / careful
        warntint: 'rgba(251,191,36,0.10)',
        ok:     '#3DD68C',   // success
        oktint: 'rgba(61,214,140,0.10)',
        info:   '#818CF8',   // info · indigo
        infotint: 'rgba(129,140,248,0.10)',
        gold:   '#EDB36B',   // dusk amber — victory / complete (horizon warm end)
        goldtint: 'rgba(237,179,107,0.10)',
      },
      fontFamily: {
        sans: ['"DM Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        disp: ['"Geist"', '"DM Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card:   '0 1px 2px rgba(0,0,0,.4)',
        raised: '0 1px 2px rgba(0,0,0,.45), 0 8px 24px rgba(0,0,0,.35)',
        pop:    '0 0 0 1px rgba(255,255,255,0.10), 0 4px 16px rgba(0,0,0,.4)',
        glow:   '0 0 0 1px rgba(107,98,242,0.35)',
      },
    },
  },
  plugins: [],
}
