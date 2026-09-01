# VOIDFORGE — PLAN MAÎTRE D'UPGRADE
**Consolidé de la session : audit de route complet (103 tools), analyse reverse-skill (33,7 k⭐), comparatif CLI-first vs native-tools.**
Statut d'entrée : 103 tools (0 dérive structurelle), 6 bugs racine tués, 25 skills (14 greffés), 111/111 tests, backend `pwsh-19` en campagne — **tout ce qui suit arme au prochain restart naturel.**

---

## 🎁 ACQUIS DÉJÀ RÉALISÉ — WAVE 1 (fait en session, avant ce plan)

**Source** : repo `zhaoxuya520/reverse-skill` (33,7 k⭐, MIT) cloné dans `research/reverse-skill`. **14 packs greffés dans `skills/`, tous vérifiés vivants au registre** (25 skills total — l'agente les voit via `skill_list`, les charge à la demande). Chaque greffe porte un en-tête **VOIDFORGE TOOL MAP** : l'agente qui charge le skill voit immédiatement quels outils frappent avec. Contenu original zh/en préservé — glm le lit nativement.

| Skill greffé | Format | Map vers notre arsenal |
|---|---|---|
| `jwt_claim_confusion` | 4 Ko, 2 sources | `jwt_analyst` → `jwt_forge_replay` |
| `race_state_drift` | playbook + refs | `auth_state_audit` → `race_smash`/`h2_race_attack` |
| `request_smuggling_pack` | CL.TE/TE.CL/TE.TE | `waf_detect` → `smuggle_probe` |
| `graphql_rpc_drift` | introspection/batch/alias | `graphql_introspect` → `data_extract` |
| `oauth_oidc_chain` | state-machine/PKCE/magic-link | `auth_state_audit` + `redirect_cast` |
| `ssrf_metadata_pivot` | 169.254/IMDS/rebinding | `ssrf_probe` → `lfi_file_read` |
| `attack_chain_pack` | 19 Ko de compositions | toute la chaîne de frappe |
| `api_security_pack` | REST/GraphQL/JWT testing | `api_sweep`/`data_extract` |
| `llm_security_pack` | prompt-injection/agent-abuse | detector v4 (adjacent) |
| `kerberos_delegation` 🆕 | RBCD/S4U/SPN | **bouche le trou AD** |
| `adcs_abuse` 🆕 | ESC1-4/Certipy | **bouche le trou ADCS** |
| `dpapi_chain` 🆕 | masterkey/cookies Chrome | **bouche le trou Windows post-exploit** |
| `src_hunter` | 19 playbooks bug bounty | couche méthodo globale |
| `src_hunter_waf_bypass` | **176 Ko de payloads WAF** | alimente `payload_library`/`sqli_tamper_chain`/fuzz seeds |

Les 3 🆑 bouclent exactement les gaps notés par l'évaluation d'arsenal (« manque Kerberos/AD, cloud ») — le repo était le complément parfait.

**Aussi acquis en session** : stand de tir réutilisable `research/range_target.py` (failles simulées, 47/47 routes parcourues, 4 HIT confirmés) + `research/range_driver.py`.

### Mécaniques du repo : déjà chez nous vs candidats (position d'entrée du plan)

| Mécanique du repo | Chez nous | Position dans le plan |
|---|---|---|
| Skill routing par keywords (routing.json/master-route) | PHASE GUIDE + chain hints (runtime, zero-prompt) | déjà mieux ; upgrade `tier:`/`not_when:`/PRIMARY → **B2** |
| scope-contract avant action (case-guard) | engagement.yaml + SOW + G13 | déjà couvert |
| Toolchain bootstrap à la demande (manifest sha256) | absent | **C1-C3** (candidat #2 activé) |
| field-journal/precedents par campagne | trajectory_insight + MCTS | **D1** (candidat #3, mariage MCTS→journal) |
| tool-index.md par machine | absent | **C3** |
| burp-mcp-full (pont traffic) | HAR tools | **E2** (stretch, décision LO) |

---

## AXE A — ARSENAL : FIABILITÉ & COMPLÉTUDE
*(issu de l'audit de route — la leçon centrale : un tool cassé est pire qu'un tool absent, il enseigne à l'agente d'éviter la route)*

### A1. Redémarrage d'armement (~30 min, au premier idle campagne)
6 fixes sur disque attendent le restart : forge biforme, `_roe_limit` global, `verdict()` dict-evidence, `binary_fuzz_run` corpus optionnel, `auth_state_audit` schema enveloppé, `sqli_tamper_chain` NameError. Au restart : vérifier `/health`, lancer `arsenal_selftest(mode='live_local')`, confirmer 16/16.
**Acceptance** : selftest vert + un smoke forge (forme full-module) post-restart.

### A2. Campagne Juice Shop — marcher les ~26 routes restantes (~2 h, autorisée locale)
Les tools ciblés (supabase_*, tg_*, nuclei réels, web3…) n'ont pas encore couru sur cible vivante. Juice Shop les traverse dans l'ordre des benches. **Mesurer** : diversité d'outils par mission (baseline observée 7-8 → objectif 25-35), hits de chain hints, TOOL ERROR rate (doit rester < 5 %).
**Acceptance** : rapport de campagne avec le décompte d'outils distincts utilisés.

### A3. Tagging par phase (~1 h)
Champ `phase` (recon/surface/exploit/post-exploit/adapt) en **métadonnée registre** — jamais dans le schema LLM (validé sûr). Le PHASE GUIDE du DOCTRINE peut alors citer des outils réels par bench au lieu de génériques.
**Fichiers** : `tools/__init__.py` (registre), éventuellement `core/agent.py` (doctrine data-driven).

### A4. Hygiène des forges (~30 min)
- Dédupliquer `forged_siwx_idor_v2..v6` (garder la meilleure par verdict, archiver le reste dans `tools/forged_archive/`)
- Politique de namespace : un tool forgé qui échoue N fois en campagne → quarantine auto + entrée dans le rapport (`forged_diag_*` precedent)
- Test : le registre ne charge jamais un `.py` en quarantine

---

## AXE B — SKILLS & ROUTING (la couche doctrine)
*(issu de l'analyse reverse-skill : leur routing.json SSOT est SS bon, notre `select_for()` est 200× plus léger — on prend leurs 3 idées, pas leur poids)*

### B1. Wave 2 de greffes — 20 micro-skills CTF (~45 min)
Tiers ajoutés aux 14 wave-1 : `template_render_path` (SSTI→vf_template_scan), `windows_pivot`, `linux_credential_pivot`, `lsass_ticket_material`, `identity_windows`, `mailbox_abuse`, `relay_coercion_chain` (bloc AD), `k8s_control_plane`, `container_runtime`, `cloud_metadata_path` (trou cloud), `websocket_runtime`, `pcap_protocol`, `custom_protocol_replay` (protocoles), `forensic_timeline`, `malware_config`, `stego_media`, `zip_archive`, `file_parser_chain` (CTF-général).
**Acceptance** : ~45 skills au registre, load non vide sur chacun.

### B2. Upgrade du routing `core/skills.py` (~1 h 30) — le cœur de l'axe
1. **`tier:`** dans chaque header (`core`/`domain`/`library`) : seul `core` (~15) participe à l'auto-match de démarrage ; le reste via skill_list/skill_load. Anti-dilution quand on passe à 45+.
2. **`not_when:`** (leurs exclusions anti-collision : jailbreak iOS ≠ jailbreak LLM) : un skill exclu n'est JAMAIS injecté même si `when:` matche.
3. **Modèle PRIMARY + secondaries** (leur route-scope.md) : le meilleur match s'injecte plein format (6 000 chars), les suivants en une ligne pointeur « related: x, y → skill_load ». Le budget 14 k passe de 3 playbooks plats à 1 profond + carte.
4. **Confidence** dans le bloc injecté (1 hit=high, multi=medium, 0=fallback) — le modèle sait à quel point le match est fiable.
**Fichiers** : `core/skills.py`, headers des 25 skills existants, `test_skills_routing.py` (not_when, tiers, secondaries, confidence).

### B3. Ingestion payloads & dictionnaires (~1 h)
- `by-category/intranet/*` (11 fichiers ~250 Ko : adcs/exchange/凭证窃取/域渗透/横向移动/privesc/persist) → 3 skills (`intranet_recon`, `intranet_creds`, `intranet_lateral`), tier `domain`
- `chinese-srcfingerprints.md` + `default-credentials-cn.md` → **nouveau tool `cn_fingerprint`** (fingerprint stacks CN + default creds par vendor) ou `payload_library vclass="cn_default"` — selon format corpus à l'ouverture
- `methodology/*` (attack-priority, bypass-toolkit, evidence-discipline) → skill `src_hunter_method`, tier **core**
**Acceptance** : payload_library expose les nouvelles classes ; smoke sur cn_fingerprint.

---

## AXE C — BOOTSTRAP D'ENVIRONNEMENT (leur meilleure pièce, adoptée au format natif)
*(leur contrat : « 缺工具 → bootstrap, 禁止猜路径 » — et leur manifest sha256/pins est exactement ce qu'il nous faut)*

### C1. `tools/bootstrap_manifest.json` (~45 min)
Schema cloné du leur : par capacité → `name`, `bootstrapKind` (pip-package épinglé | winget-package | npm-global | git-clone | github-release-zip{assetRegex, sha256} | manual), `verifyCommand`, `canAutoInstall`, `installDir`, `docsUrl`. Capacités : nmap, nuclei, httpx, subfinder, ffuf, sqlmap, hashcat, impacket, seclists, masscan.
**Note architecture** : on garde le **manifest**, on rejette leur script monolithe de 35 Ko (bootstrap-reverse.ps1) — la logique d'install va dans un tool gouverné.

### C2. Tool `env_bootstrap` (~45 min)
- mode dry-run (défaut, danger=safe) : table 8 colonnes leur format (Tool | Skill | Purpose | Available | Path | Version | Install | canAutoInstall) — version par `verifyCommand`
- mode `install=True` (danger=active, jamais auto) : installe avec vérification sha256 pour les releases GitHub
**Fichiers** : `tools/env_bootstrap.py`, registre, `test_env_bootstrap.py` (dry mode only).

### C3. Intégration selftest + tool-index (~30 min)
- `arsenal_selftest` mode `live_local` : section `external_deps` — l'agente sait AVANT de frapper si `nmap_scan` peut tourner
- générateur `tool-index.md` (gitignored, par machine) synchronisé de NOTRE registre + manifest — les tools wrappés y entrent avec leur binaire requis
**Acceptance** : selftest affiche external_deps ; tool-index.md généré sur cette machine, nmap/nuclei statuts corrects.

---

## AXE D — MÉMOIRE & APPRENTISSAGE (la boucle qui mûrit)
*(leurs precedents = prose au démarrage ; le nôtre = MCTS → données structurées → journal → prompt)*

### D1. Field journal (~2 h)
- `memory/journal/precedent_<date>_<classe>.md` : classe de cible, chaîne d'outils gagnante, murs rencontrés, payload décisif
- **`journal_write`** (tool, appelé en fin de mission, alimenté par trajectory_insight) + auto-match au démarrage par classe de cible (même mécanique que skills, répertoire séparé, tier-like weighting : récent > ancien)
- Boucle complète : campagne → MCTS stats → insight → precedent → injection mission N+1
**Fichiers** : `tools/journal.py`, `core/agent.py` (injection au boot), `test_journal.py` (round-trip).

### D2. G9 — attack graph day-2 (~4-6 h, déjà spécifié)
Le graphe de compromission persistant entre missions : nœuds = assets compromis, arêtes = pivots prouvés. Se marie au journal (le precedent référence les nœuds).
### D3. LOCAL_BRAIN + LoRA (~taille libre, déjà spécifié)
Ollama abliterated en cerveau local ; export des transcripts de campagnes → paires d'entraînement → LoRA. C'est le bout ultime de la boucle D : l'apprentissage entre dans les poids, plus seulement dans le contexte.

---

## AXE E — COUVERTURE LONG-TAIL GOUVERNÉE (la leçon du comparatif CLI vs tools)
*(on ne donne pas le shell brut à l'agente — on ingère le pouvoir CLI PAR la forge et le manifest)*

### E1. Doctrine de forge CLI (~30 min)
Ajouter au DOCTRINE + un skill `cli_ingestion` : quand une capacité manque, l'agente forge un wrapper tool (schema, gates, verdict, hints) autour du binaire — jamais de composition shell libre. La CLI devient munition, jamais cockpit.
### E2. burp-mcp-full — pont traffic (~3 h, STRETCH sur décision LO)
Leurs 14 fichiers = pont Burp→agent. Ne se justifie que si LO pilote Burp en parallèle. Évaluer le protocole MCP avant d'engager ; alternative : tout passer par HAR (déjà couvert par har_dissect/har_passive_scan).

---

## AXE F — UI (léger)
### F1. Vue Skills & Journal dans le war-room (~1 h 30)
Panneau : liste des skills (tier, when, dernier hit en campagne) + les precedents du journal lisibles. Observabilité de la couche doctrine — utile pour diriger l'upgrade en continu.

---

## ORDRE D'EXÉCUTION

```
SESSION 1 (le cœur, ~4 h) :  A3 tagging → B2 routing upgrade → B1 wave 2 → B3 payloads
SESSION 2 (l'env, ~2 h)   :  C1 manifest → C2 env_bootstrap → C3 selftest/tool-index → A4 forges
SESSION 3 (la mémoire, ~3 h): D1 journal → F1 UI → E1 doctrine
RESTART NATUREL           :  A1 arming (tout entre en campagne)
SESSION 4 (validation, ~2 h): A2 Juice Shop → mesurer diversité/skills/journal → itérer
PLUS LOIN (sur décision)  :  D2 G9 attack graph, D3 LOCAL_BRAIN/LoRA, E2 burp-mcp
```

**Total** : ~12 h effectif réparties. Session 1 = le plus gros ratio valeur/heure : le routing upgrade (B2) multiplie la valeur de TOUTES les skills, existantes et futures.

### Métriques de succès (mesurées à la campagne Juice Shop, A2)
1. **Diversité d'outils** : 7-8 → **≥25** distincts par campagne
2. **TOOL ERROR rate** : < 5 % (l'audit a tué les mines ; toute remontée = regression)
3. **Skill hits** : ≥3 skills chargés par mission, 0 injection hors-tier
4. **Journal** : ≥1 precedent lisible et réinjecté à la mission suivante
5. **Zero devination** : 0 appel de binaire absent sans passage par env_bootstrap
