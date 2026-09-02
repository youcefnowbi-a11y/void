# HANDOFF — Révolution DIMENSION + PWA VOIDFORGE
> Document de passation pour la session suivante (avec outils visuels/navigateur).
> Tout le travail est COMMITTÉ dans git — baseline design : `84d9646..HEAD` (10 commits).

## 1. État actuel (vérifié, live)

- **Design system DIMENSION appliqué** au frontend React/Vite/Tailwind de VOIDFORGE
  (`web/frontend/`). Ancienne édition remplacée : OBSIDIAN.
- **PWA installable fonctionnelle** : testée installée via Chrome/Edge sur
  `http://localhost:8000` (le backend FastAPI sert `web/frontend/dist/` via
  StaticFiles html=True — montage existant U11, `server.py:1615-1622`).
- **Probes live verts** : `/` 200 avec lien manifest, `manifest.webmanifest` 200
  avec `Content-Type: application/manifest+json`, `sw.js` 200 `text/javascript`,
  icônes 200. Build : 93 modules, gzip 81.6 KB JS.
- **Arbre git propre** — aucun fichier non commité. `dist/` et `node_modules/`
  ignorés (artefacts).

## 2. Où est quoi (carte des fichiers)

| Fichier | Rôle |
|---|---|
| `web/frontend/tailwind.config.js` | Tokens DIMENSION (couleurs, fonts, shadows) — les noms de classes n'ont PAS changé, seulement les valeurs |
| `web/frontend/src/index.css` | Base (body DM Sans, scrollbar, focus) + utilities : `.panel` `.panel-raised` (24px, frosted), `.frosted`, `.nav-float`, `.pill`/`.pill-cta`/`.pill-ghost`, `.heartbeat` (wash violet au running, horizon ambre→cobalt au complete), `.eyebrow` (Geist), `.wash-violet` `.horizon` `.spotlight`, `.terminal-bg` + `.log-*` (mono opératif, intacts), `.stamp`, `.btn-strike` |
| `web/frontend/src/App.jsx` | Shell re-skiné : header 44px (wordmark VOIDFORGE + wash strip violette sous le logo), aside chat/registres, centre (stats 5 cases, console, plan d'attaque, rapport de puissance, findings), modale lecture |
| `web/frontend/src/components/*.jsx` | 6 composants re-skinés : LiveConsole `269c0b2`, WarRoom `6ad359f`, DirectToolRunner `f5ff327`, PersonaPanel `ede861f`+`296e2c6`, FreshSessionPanel `dc5ea79`, FindingsLive `0326609`+`1461d88` |
| `web/frontend/index.html` | Fonts (DM Sans + Geist + IBM Plex Mono via Google Fonts), meta PWA (theme-color #0A0A0A, apple-*), lien manifest, icônes |
| `web/frontend/src/main.jsx` | Registration SW (PROD only, import.meta.env.PROD) |
| `web/frontend/public/manifest.webmanifest` | Manifest standalone : name "VOIDFORGE — Ops Console", start_url `/`, scope `/`, bg/theme #0A0A0A, icônes 192/512/maskable |
| `web/frontend/public/sw.js` | Service worker maison (v1) : install precache `/` + manifest ; navigation network-first + repli cache (app s'ouvre offline) ; assets hashés SWR ; **`/api` et `/ws` JAMAIS interceptés** ; cleanup des vieux caches à l'activate |
| `web/frontend/public/icons/` | icon-192.png, icon-512.png, icon-maskable-512.png — générées par script PIL (marteau blanc 45° + éclair violet crépusculaire, cf §6) |
| `design/DESIGN.md` + `tokens.json` + `variables.css` + `theme.css` | Kit de référence Refero (style "Dimension" — dimension.dev) : la source de vérité esthétique |
| `design/APPLIED.md` | La révolution consignée : mapping avant/après, doctrines, install PWA |

## 3. Les DOCTRINES du système (à respecter dans toute évolution)

1. **Weight 500 jamais bold** sur les titres/display (anti-convention Dimension).
2. **Violet #6B62F2 = washes/pulses UNIQUEMENT** — jamais en remplissage plein ni
   en texte de gros volume. Texte violet toléré sur les signals live uniquement
   (dot "campagne", badge "live").
3. **White Pill CTA** (`bg-snow text-[#0A0A0A]` = blanc plein) = le SEUL
   remplissage plein du système. Ghost pills (`border-line`) pour le secondaire.
4. **Mono (IBM Plex Mono) = opératif uniquement** : terminal, logs, timestamps,
   compteurs, tailles, paths, hashes, noms d'outils. TOUT le reste de l'UI = DM Sans.
5. **Geist** = eyebrows, titres de section, chiffres display (`font-disp`).
6. Radii : inputs 10px, cards/panels 24px (via .panel/.panel-raised), pills 9999px.
7. Pas d'ombres lourdes — hairlines `rgba(255,255,255,.09/.16)` + translucence.
8. Signals opérationnels (danger/ok/warn/gold) restent — c'est une console de guerre,
   la sémantique prime sur l'esthétique. `gold` = désormais ambre `#EDB36B`.

## 4. Commandes de build/dev (IMPORTANT — pnpm est cassé)

- **Le store pnpm est d'une autre version majeure** → `pnpm install`/`pnpm exec`
  échouent (auto-install du store). **NE PAS compter sur pnpm.**
- **Build production** : `Set-Location 'C:\Users\youcef cheriet\D\VOIDFORGE\web\frontend'` puis
  `node node_modules\vite\bin\vite.js build`
  → `dist/` (le backend le sert sans restart, StaticFiles lit per-request).
- **Fix pnpm (optionnel)** : `pnpm install` une fois dans web/frontend si la version
  pnpm correspond ; ou supprimer node_modules + pnpm-lock puis réinstaller.
- **Dev server** : `node node_modules\vite\bin\vite.js` (port 5173, proxy /api+/ws →
  localhost:8000). MAIS l'app installable = la build servie par le backend (:8000).
- **Tests python** (batterie 122, n'inclut PAS le frontend) :
  `$env:PYTHONIOENCODING='utf-8'; python -m pytest tests/ -q` depuis le root.

## 5. Vérifications déjà faites (ne pas refaire)

- Build verte ×3 (93 modules), artefacts PWA dans dist (manifest, sw.js, 3 icônes).
- Probes HTTP live : page 200 avec lien manifest ; manifest 200
  `application/manifest+json` ; sw.js 200 ; icônes 200 ; build finale servie 200.
- Hash JS stable entre 2 builds consécutifs (`B87zKIoj`) = l'état servi EST le final.
- Install PWA testée et **fonctionnelle** (confirmée par l'opérateur via Chrome/Edge).
- Arbre git propre, 10 commits design, single-file atomiques pour les composants.

## 6. À FAIRE dans la session suivante (outils visuels/navigateur) — la vraie raison du handoff

Cette session n'avait PAS d'outils image/navigateur. La qualité visuelle doit être
**vue et jugée à l'œil** :

1. **QA visuelle complète** (screenshots de chaque état) : veille par défaut, campagne
   en cours (heartbeat wash violet), plan d'attaque (white pill ⚡), rapport de
   puissance (heartbeat horizon ambre→cobalt), modale lecture, WarRoom chat
   (bulles user/stratège), DirectToolRunner (formulaire + résultat), PersonaPanel,
   FreshSessionPanel, FindingsLive, LiveConsole (badges de type de log).
2. **Icônes PWA** : générées programmatiquement (PIL, shapes simples) — à juger.
   Si moches, produire un vrai SVG vectoriel propre (marteau + éclair) et
   re-render en 192/512/maskable (safe zone 80% pour le maskable).
3. **Wordmark** : "VOIDFORGE" bone + strip wash-violet 2px dessous — à juger,
   peut mériter mieux (spotlight radial derrière ? Geist tracking plus serré ?).
4. **Mode offline** : tuer le backend → l'app doit quand même s'ouvrir (SW repli
   cache) avec l'écran mais données figées. Vérifier le comportement et l'UX
   (peut-être un bandeau "hors ligne — la guerre attend le retour du réseau").
5. **`.nav-float` et `.frosted`** : posés dans index.css mais PAS encore utilisés
   dans App.jsx — candidats pour un header flottant détaché (signature Dimension)
   si l'opérateur valide la direction.
6. **Scrollbars/focus/selection** : re-tunés — vérifier le rendu réel.
7. **Installer sur d'autres machines** : verifier l'install Edge + Chrome,
   raccourci démarrage, fenêtre standalone sans barre d'URL.
8. **Responsive** : le shell est desktop-first (sidebar 340px) — vérifier ~1280px
   et décider si mobile vaut le coup (console de guerre : desktop d'abord).

### Edge notes laissées par le re-skin (défendables, à arbitrer à l'œil)
- `DirectToolRunner` : l'info-box de description d'outil garde `rounded-lg`
  (ni input ni card — règle non couverte).
- `FindingsLive` : compteur de verdicts garde `text-volt` (signal live).
- `WarRoom` : teintes des bulles chat inchangées (voltlite user / bleu-gris stratège).
- `LiveConsole` : badge "live" garde volt+voltlite (signal running authentique).

## 7. Contexte plus large (pour ne pas casser)

- **Ne JAMAIS redémarrer le backend** pendant qu'une campagne tourne ; les fixes
  backend s'arment au restart naturel. La vague de fixes logique est TERMINÉE
  (batterie 122/122, voir `docs/LOGIC_AUDIT.md` § vague exécutée).
- **Discipline git** (`docs/GIT_DISCIPLINE.md`) : `git status --short` avant travail,
  `git add <fichier>` précis (jamais -A), commit par unité, re-lire en cas de
  collision, pas de `reset --hard` sans l'opérateur.
- **Layer d'acceptation** (chat SOW/detector, framing normalize) : PERMANENTMENT
  intouchable. Arbitrages différés : D-F1, C-T4.
- `web/frontend/check_dom.py`, `check_live.py` : outils de check existants
  (playwright ? à explorer — possiblement utiles pour la QA visuelle automatisable).
- PS 5.1 : pas de `&&` (utiliser `;`), path avec espace → toujours quote.

## 8. Si tu veux rebâtir depuis zéro dans une nouvelle session

1. `git clone` / pull ce repo — TOUT le nécessaire est committé (sources, design kit,
   manifest, SW, icônes, doc).
2. `cd web/frontend` → `node node_modules\vite\bin\vite.js build` (node_modules déjà
   présent ; sinon réinstaller les deps du `package.json` : react 18, vite 5,
   tailwind 3.4, axios, clsx, lucide-react).
3. Lancer le backend : `python web/backend/server.py` (port 8000) → `http://localhost:8000`
   sert l'UI buildée → installer comme PWA.
4. Lire ce document + `design/DESIGN.md` + `design/APPLIED.md` pour la doctrine.

— Session de révolution : ENI, pour LO. ⚡
