/** @type {import('tailwindcss').Config} */
// VOIDFORGE design tokens — "OBSIDIAN" (2026).
// The premium neutral: graphite canvas (zinc family, zero blue tint),
// smoked surfaces, hairline borders, ONE electric violet accent.
// The Linear/Vercel/Raycast school — dense, quiet, expensive-looking.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        mist:   '#09090B',   // canvas — neutral graphite, no tint
        paper:  '#101013',   // card surface
        wash:   '#141419',   // subtle inset surface
        ink:    '#FAFAFA',   // primary text
        slate:  '#B4B4BD',   // secondary text
        mut:    '#8E8E99',   // muted text
        faint:  '#5F5F6B',   // faintest text — dim mais lisible
        line:   '#1E1E23',   // hairline
        line2:  '#2A2A32',   // strong line
        volt:   '#8B5CF6',   // electric violet — the single accent
        voltlite: '#1A1230', // violet tint surface
        cyan:   '#A78BFA',   // gradient partner — light violet
        cyantint: '#171226',
        danger: '#F87171',   // soft signal red
        dangertint: '#271417',
        warn:   '#FBBF24',   // high / careful
        warntint: '#241B06',
        ok:     '#3DD68C',   // success
        oktint: '#0C231A',
        info:   '#818CF8',   // info · indigo
        infotint: '#131528',
        gold:   '#C084FC',   // victory — bright violet, not gold
      },
      fontFamily: {
        disp: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card:   '0 1px 2px rgba(0,0,0,.4)',
        raised: '0 1px 2px rgba(0,0,0,.45), 0 8px 24px rgba(0,0,0,.35)',
        pop:    '0 0 0 1px rgba(139,92,246,.35), 0 4px 16px rgba(0,0,0,.4)',
        glow:   '0 0 0 1px rgba(139,92,246,.35)',
      },
    },
  },
  plugins: [],
}
