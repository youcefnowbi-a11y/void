# DIMENSION → VOIDFORGE — la révolution appliquée

> Source : `design/DESIGN.md` (extraction Refero du style Dimension) + `styles.refero.design/style/fbcf9cbb-7c6b-449d-862a-bce521a8ab1d`.
> Édition remplacée : OBSIDIAN (Plex Mono universel, violet plein, radii serrés).

## Ce qui a changé

### Tokens (`tailwind.config.js`, `src/index.css`)
| Token | Avant (OBSIDIAN) | Après (DIMENSION) |
|---|---|---|
| `mist` (canvas) | `#09090B` | `#0A0A0A` — void canvas |
| `paper` (surfaces) | `#101013` | `#161616` — graphite |
| `ink` (texte) | `#FAFAFA` | `#EDEDED` — bone, anti-éblouissement |
| `line` | `#1E1E23` | `rgba(255,255,255,.09)` — hairline lumière |
| `volt` | `#8B5CF6` **plein** | `#6B62F2` **washes/pulses seulement** |
| `gold` | `#C084FC` | `#EDB36B` — ambre crépusculaire (fin chaude de l'horizon) |
| nouveau | — | `snow #FFFFFF` — la White Pill CTA, seul remplissage plein |

### Typographie
- **DM Sans** = toute l'UI (body, labels, boutons) — remplace l'univers Plex Mono.
- **Geist** = eyebrows, titres, chiffres (`font-disp`) — précision technique.
- **IBM Plex Mono** = SEULlement l'opératif : terminal, logs, timestamps, chemins, hashes.
- Anti-convention Dimension conservée : titres en **weight 500**, jamais 700.

### Formes
- Panels `.panel`/`.panel-raised` : 10-12px → **24px**, ombres lourdes → hairlines.
- Tous les boutons → **pills 9999px** ; CTA principal = **pill blanche** (`bg-snow text-[#0A0A0A]`).
- Nouvelles surfaces : `.frosted` (verre dépoli, blur 10px), `.nav-float` (pill flottante), `.pill-cta`, `.pill-ghost`.

### Chromatique
- Violet `#6B62F2` **jamais en remplissage** : heartbeat (`.wash-violet`, alpha .565), pulses live, focus, hover.
- Signature gradient : `.horizon` (ambre → cobalt) réservé aux moments "complete"/héros.
- Signals opérationnels (danger/ok/warn) inchangés — la guerre reste lisible.

## PWA installable
- `public/manifest.webmanifest` — standalone, void canvas, icônes 192/512/maskable.
- `public/sw.js` — shell network-first + repli cache (l'app s'ouvre hors-ligne), assets SWR, **`/api` et `/ws` jamais interceptés**.
- `src/main.jsx` — registration PROD only.
- Icônes : marteau blanc + éclair crépusculaire violet (`public/icons/`, générées PIL).
- **Install** : ouvrir `http://localhost:8000` (le backend sert `dist/`) → bouton "Installer" de la barre d'adresse → la console s'ouvre en fenêtre dédiée, icône à la taskbar.
- Rebuild après modification du front : `node node_modules\vite\bin\vite.js build` (dans `web/frontend/`).
