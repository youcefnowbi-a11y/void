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

---

# SESSION 2 — prod wiring + nav flottante + icônes (FAIT)

## 1. La découverte majeure : le mode prod n'était JAMAIS branché

Les probes §5 de la session 1 ne couvraient que le statique. En prod (`:8000`),
l'app appelait `/api/*` — un alias **dev-only** du proxy Vite — → **404 sur chaque
endpoint**, et le WS était refusé (allowlist origines = `:5173` seulement) → **403**.
La console prod tournait à vide depuis le début (install PWA OK, données jamais OK).

## 2. Fixes

- `web/frontend/src/api.js` — `API_BASE = DEV ? '/api' : ''` (importé partout :
  App, useMissionSocket, PersonaPanel, DirectToolRunner, FreshSessionPanel).
- `server.py` — allowlist WS += `http://localhost:8000` + `http://127.0.0.1:8000`.
- Commits `deef43e` + `e19d643`.

## 3. Design — la révolution continue (commits `7e2a629`, `6fa804d`, `ff2a135`)

- **Nav flottante** : la barre 44px pleine largeur → pill `.nav-float` détachée
  (16px des bords, blur 14px, `shadow-nav` = l'élévation exacte extraite de
  Dimension). Spotlight violet d'ambiance derrière (opacity 0.13). Wordmark
  deux tons (VOID bone / FORGE ash), tracking -0.03em. 💬/⚙ emoji → SVG géométriques.
- **Discipline monochrome** : tous les emojis colorés purgés (⚡👤💬🧹📦🎯🧠🗺🩹)
  — glyphes géo monochromes (◇ ▸ ■ ✚ ») + typographie pure, terminal inclus.
  ✓✗⚠✦○⚙ restent (glyphes mono légitimes).
- **Icônes PWA refaites** : `design/icons-src/voidforge.svg` (marteau blanc 45° +
  éclair violet crépusculaire sur void, dusk radial) — rendu headless Edge
  (`render.html`/`render-maskable.html`, 512 master → 192 bicubique, maskable à
  80% safe zone). Pilée et vérifiée pixel par pixel. **Ne PAS régénérer via PIL.**

## 4. État vérifié (live)

- 0 erreurs console, WS connecté (dot vert "flux live"), emoji-free.
- `/`, `sw.js`, `manifest`, 3 icônes : tous 200. Build : 94 modules, 81.9 KB gz.

## 5. Piège process à connaître (important)

Le runtime de session **récolte les arbres de processus** : un backend lancé via
`Start-Process` depuis un appel pwsh peut mourir silencieusement plus tard
(plusieurs morts mystères élucidées ainsi). Le backend actuel a été lancé par
l'opérateur lui-même (`python -m uvicorn web.backend.server:app` depuis le root).
**Ne pas le redémarrer** ; si un jour il faut le relancer, prévenir l'opérateur
et/ou utiliser WMI `Win32_Process.Create` (hors de l'arbre récolté).

## 6. Reste à faire (session 3)

1. QA visuelle à l'œil de LO sur les screenshots `qa-01`→`qa-05` (radicale :
   la nav flottante change la silhouette du shell).
2. States live (campagne lancée) : heartbeat violet, horizon complet, plan
   d'attaque, rapport de puissance — non capturés (pas de campagne de test tirée).
3. Mode offline (handoff §6.4) — toujours non testé (ne pas tuer le backend !).
4. Responsive ~1280px (handoff §6.8) — non traité.

— Session 2 : le fil est vivant, la forge a sa signature. ⚡

---

# SESSION 3 — RECONSTRUCTION TOTALE (l'opérateur a tranché)

> Verdict LO sur le re-skin incrémental : « je demande Dimension et tu me donnes ÇA ? »
> Ordre : tout effacer, reconstruire de zéro sur le kit de référence (déposé dans
> `design/ref/` par l'opérateur — identique à `design/DESIGN.md`). Livrable : **PWA
> installée, façon app Codex** (fenêtre standalone, pas de chrome navigateur).

## Ce qui a été rasé et réécrit (commits `275b60e` → `5a31729`)

- **`tailwind.config.js`** — tokens Dimension complets : frost `rgba(212,212,212,.08)`,
  smoke/slate/ash/bone, radii `ui 10 / card 24 / large 40 / panel 42`, la SEULE
  ombre = `shadow-nav` (élévation extraite).
- **`src/index.css`** — réécrit : `.display` (DM Sans 500, -0.035em), `.panel-frost`
  (verre dépoli blur 12), `.nav-float`, pills CTA/ghost avec états disabled, les
  trois gradients (wash / horizon / spotlight), terminal mono intact.
- **`App.jsx`** — nouveau shell : **héros de veille** (le moment signature :
  eyebrow + display 34px + horizon ambre→cobalt + barre d'ordre frosted + white
  pill « frapper » — l'ordre part dans la ligne sécurisée), nav flottante h-12,
  registres SANS numéros (les chiffres décoraient, ils n'informaient pas),
  stats Geist 22px, modale panel.
- **Les 6 composants** — re-dressés : WarRoom frosted **achromatique** (les bulles
  bleues #0E1E38/#60A5FA/#93C5FD ont violé la discipline — mortes), console en
  panel + pills, forms 10px + white pills, purge ghost-danger, checkbox volt.
- **PWA** — title `VOIDFORGE`, fonts épurées aux weights réels (plus de 700),
  `launch_handler: focus-existing`, `display_override`, SW `vf-shell-v2`.

## Doctrines Nouvelles (au-dessus des 8 existantes)

9. **Pas de numéros décoratifs** — les marqueurs 01/02/03 encodent une séquence
   réelle ou n'existent pas.
10. **Achromatique intégral hors signaux** — aucun bleu non-signal, aucun emoji
    coloré ; les bulles de chat se distinguent par l'alignement + la translucence.
11. **Le héros de veille EST la thèse** — au repos, l'app montre le crépuscule et
    la barre d'ordre, pas un dashboard vide.

## État vérifié (live, probes + computed styles)

- Build verte (94 modules), 0 erreurs console, WS live, hero frost/horizon/display
  vérifiés au computed style. Screens : `rebuild-01/02/03`.
- Backend : lancé par l'opérateur (`web.backend.server:app` depuis le root) — NE
  PAS redémarrer.

## Reste (session 4)

1. QA à l'œil de LO sur `rebuild-01`→`03` — le héros plaît-il ? l'échelle 14px ?
2. States live (campagne) : heartbeat, plan, horizon complet — à capturer.
3. Offline test + responsive 1280 — toujours en attente.

— Session 3 : rasée, reforgée, fidèle. ⚡
