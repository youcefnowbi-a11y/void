# PLAN — Intégration complète reverse-skill → VOIDFORGE

**Source** : `research/reverse-skill` (33,7 k⭐, MIT, 586 fichiers) — cloné, déjà greffé wave 1 (14 skills).
**Principe directeur** : rien n'entre dans l'arsenal sans route testée. Chaque phase finit par des tests + un artefact vérifié.

---

## PHASE 1 — Skill grafts wave 2 : les micro-skills CTF qui ferment nos gaps (priorité HAUTE, ~45 min)

Wave 1 a pris 9/35 micro-skills. Wave 2 prend ceux qui matchent l'arsenal ou un gap noté :

| Skill | Pourquoi |
|---|---|
| `template-render-path` | SSTI — on a `vf_template_scan`, aucun playbook |
| `windows-pivot`, `linux-credential-pivot` | post-exploit OS, on a `shell_session` mais pas de doctrine pivot |
| `lsass-ticket-material` | vol de tickets Windows — pair avec `dpapi_chain` |
| `identity-windows`, `mailbox-abuse`, `relay-coercion-chain` | compléments AD (bloc Kerberos/ADCS) |
| `k8s-control-plane`, `container-runtime`, `cloud-metadata-path` | le trou cloud/notre éval « manque cloud » |
| `websocket-runtime`, `pcap-protocol`, `custom-protocol-replay` | surface protocolaire |
| `forensic-timeline`, `malware-config`, `stego-media`, `zip-archive`, `file-parser-chain` | CTF-général, charge à la demande |

**Tiers** : ajouter un champ `tier:` dans l'en-tête de CHAQUE skill (core / domain / library). `core` = auto-match au démarrage de mission ; `library` = seulement via `skill_list`/`skill_load`. **Évite la dilution du routing** quand on passe de 25 à ~60 skills.
**Fichiers** : `_graft_skills.py` (recréer), `skills/*.md`, `core/skills.py` (lire `tier:`).

**Upgrade routing (leur mécanique master-route, `skills/config/routing.json` + `master-route.ps1`)** :
1. **`not_when:` (exclusions)** — leur motif anti-collision (`jailbreak` iOS ≠ `jailbreak` LLM) : un second header `not_when:` par skill, consulté par `select_for()` ; un skill exclué ne peut jamais être injecté même si `when:` matche. Avec ~60 skills, indispensable.
2. **PRIMARY + secondaries** — eux injectent 1 PRIMARY complet + les autres en **pointeurs** (`route-scope.md` : confidence + "MUST open next"). Nous : `select_block()` garde le PRIMARY à 6 000 chars, et liste les secondaires en une ligne ("related: x, y — skill_load") au lieu de 3 playbooks plein format. Contexte 14 k mieux dépensé.
3. **Confidence** : 1 hit = high, plusieurs = medium, 0 = fallback web_access_master (déjà notre cas) — ajouter le champ dans le bloc injecté pour que le modèle sache combien il peut faire confiance au match.
**Acceptance** : `skill_list` → ~60 skills, auto-match ne remontera que les `core` (~15), load non vide sur chacun.

## PHASE 2 — Ingestion payloads & dictionnaires (priorité HAUTE, ~1 h)

Le dossier `src-hunter/references/` (93 fichiers) n'est greffé qu'à 20 % :

1. **by-category intranet** (11 fichiers, ~250 Ko) : adcs/exchange/sharepoint攻击, 信息收集, 免杀与规避, 凭证窃取, 域渗透攻击, 权限提升/维持, 横向移动 → greffer en 3 skills (`intranet_recon`, `intranet_creds`, `intranet_lateral`) — tier `domain`.
2. **Dictionnaires** : `chinese-srcfingerprints.md` (14,8 Ko) + `default-credentials-cn.md` (10 Ko) → **nouvel outil `cn_fingerprint`** (fingerprint de stack chinoises + default creds par vendor) OU extension de `payload_library` avec `vclass="cn_default"`. Décision à l'implémentation selon le format du corpus.
3. **methodology/** (5 fichiers) : attack-priority, bypass-toolkit, evidence-discipline → 1 skill `src_hunter_method` (tier core — c'est du doctrine pure).

**Acceptance** : `payload_library(op="get", vclass=...)` renvoie les nouvelles classes ; smoke local sur chaque nouvelle skill.

## PHASE 3 — Toolchain bootstrap (priorité HAUTE, ~1 h 30)

La mécanique n°1 du repo qu'on n'a pas : **« 缺工具时调用 bootstrap，不要猜路径 »** (outil absent → bootstrap, ne jamais deviner le chemin).

**Leur format de référence, à adopter tel quel** (`skills/scripts/bootstrap-manifest.json`, 352 lignes) :
- chaque **capacité** : `name`, `bootstrapKind` (`pip-package` épinglé, `winget-package`, `npm-global`, `git-clone`, `github-release-zip` avec `assetRegex` + **sha256 de l'asset**, `remote-http-mcp`, `manual`), `verifyCommand`, `canAutoInstall`, `installDir`, `docsUrl`
- le générateur (`refresh-tool-index.ps1`) produit `tool-index.md` **gitignored par machine** : table 8 colonnes (Tool | Skill | Purpose | Available | Path | Version | Source | Script refs) + vue « Capability Status » avec statut MCP enregistré et service en ligne (double vérification : TCP probe + handshake HTTP `tools/list`)

- **Nouvel outil `env_bootstrap`** : lit NOTRE `tools/bootstrap_manifest.json` (même schema), vérifie chaque binaire externe requis (nmap, nuclei, httpx, sqlmap, subfinder, ffuf, hashcat, impacket…), renvoie la table 8 colonnes + `install_cmd` par absent. Mode `install=True` optionnel (danger=active, jamais auto, sha256 vérifié pour les releases GitHub).
- **Brancher `arsenal_selftest`** : en mode `live_local`, section `external_deps` qui liste les outils à binaire requis avec leur statut — l'agente sait AVANT de frapper si `nmap_scan` peut tourner.
- **Générer `tool-index.md`** depuis le registre + le manifest : contrat identique au leur, auto-synchronisé de NOTRE registre (le tien est vivant, le leur est manuel).

**Acceptance** : `env_bootstrap()` dry-run OK sur cette machine ; selftest affiche external_deps ; test de régression (dry mode).

## PHASE 4 — Field journal : la base auto-évolutive (priorité MOYENNE, ~2 h)

Leur mécanique : `field-journal/precedent-*.md` — chaque campagne écrit un précédent, chaque mission relit les précédents de sa classe de cible.

- **`memory/journal/`** : un precedent par mission (`precedent_<date>_<classe>.md` : classe de cible, chaîne d'outils qui a marché, murs rencontrés, payload gagnant).
- **Écriture** : `report_write` (ou nouvel outil `journal_write`) append le precedent en fin de mission — alimenté par `trajectory_insight` (notre MCTS a déjà les stats de chaînes gagnantes → le journal les matérialise en prose lisible par l'agente).
- **Lecture** : au démarrage de mission, auto-match par classe de cible injecte le precedent pertinent (même mécanique que les skills, répertoire séparé).
- **Boucle complète** : MCTS apprend → insight → journal → prompt de la mission suivante. C'est LE trait qui rapproche VOIDFORGE d'un agent qui mûrit.

**Acceptance** : mission fictive → journal_write → relance → precedent injecté dans le contexte ; test round-trip.

## PHASE 5 — burp-mcp-full : le pont traffic (priorité BASSE, ~3 h, stretch)

14 fichiers dans `burp-mcp-full/`. Un pont Burp Suite → agent donnerait à `har_passive_scan`/`replay_mutate` un flux live au lieu de fichiers HAR statiques.
**Décision reportée** : ne se justifie que si LO bosse avec Burp en parallèle de l'agente. Évaluer le protocole MCP du dossier avant d'engager.

## PHASE 6 — Repo vendored + hygiene (priorité MOYENNE, ~20 min)

- **Garder** `research/reverse-skill` (les skills greffés pointent vers ses références ; src_hunter référence ses 93 fichiers). Ajouter au `.gitignore` si pas déjà vendored.
- **Supprimer** `.github/`, `examples/`, `reports/` du clone pour alléger (~28 fichiers, le clone reste shallow).
- **Crédit** : ligne dans README + en-tête des skills greffés (déjà fait : « Grafted from the reverse-skill pack (MIT) »).

## PHASE 7 — Batterie de tests (transversal, +30 min à la fin)

- `test_skills_wave2.py` : compte registre, tier parsing, load non vide des nouveaux, auto-match ne remonte QUE les core.
- `test_env_bootstrap.py` : dry-run, détection winget présent/absent, pas d'install réelle en test.
- `test_journal.py` : round-trip écriture/lecture/match par classe.
- `test_payloads_cn.py` : classes ajoutées à payload_library / cn_fingerprint smoke.
- Rerun battery complète (20 suites actuelles + 4 = **24 suites**).

## PHASE 8 — Arming + campagne de validation

- Tout arme au **prochain restart naturel** du backend `pwsh-19` (jamais interrompre une campagne vivante).
- **Campagne Juice Shop autorisée** : mesurer (a) hits de skills wave-2 dans les prompts, (b) diversité d'outils (baseline avant : 7-8 ; objectif : 25-35), (c) le journal produit un precedent lisible et réutilisé.

## PHASE 9 — (adopté) Ce que leur chaîne de consommation nous apprend — lecture AGENTS.md/CLAUDE.md/master-route/bootstrap

**Leur chaîne complète** (comment LEUR agent consomme tools + skills) :
`CLAUDE.md` (=notre DOCTRINE) → `master-route.ps1` matche regex sur le texte de mission via `routing.json` (SSOT, ~25 routes R1-R25 avec `must`/`mustAll`/`exclude` + scoring par hits + priorité tie-break + fallback R0) → `case-init.ps1` écrit `work/<case>/scope.md` (fields: auth.status, network_profile, preset offline-sample) → `case-guard` BLOQUE toute action tant que `auth.status=granted` n'est pas prouvé → le skill PRIMARY s'ouvre, lit `tool-index.md` (généré par machine, jamais deviné) → `bootstrap-manifest.json` fournit l'install exact (pip épinglé/winget/zip+sha256/manual) → evidence appendée par campagne (`append-evidence.ps1`) → cohérence testée (`verify-routing-coherence` : routes↔priorité↔docs).

**Mapping vers VOIDFORGE** (ce qui existe déjà ✅ / à porter 📦) :

| Leur pièce | Chez nous | Verdict |
|---|---|---|
| CLAUDE.md doctrine | `core/agent.py` DOCTRINE | ✅ plus riche |
| master-route.ps1 (regex→skill) | `core/skills.py select_for()` (when: scoring) | ✅ même mécanique, 30 lignes vs 8 k |
| routing.json SSOT | header `when:` par skill | ✅ (upgrade not_when/confidence → P1) |
| case-init + case-guard hard gate | `engagement.yaml` + scope_statement + G13 | ✅ équivalent, moins normatif |
| tool-index.md par machine | ❌ rien | 📦 **P3 env_bootstrap + manifest** |
| bootstrap-manifest (sha256, pins) | ❌ rien | 📦 **P3** |
| append-evidence par campagne | `report_write` + `evidence_pack` | ✅ (le journal P4 le liera aux missions) |
| verify-routing-coherence | `test_arsenal_integrity` + hygiene | ✅ |
| ROUTE (fichier route-scope.md) | hints runtime (zero-prompt) | ✅ **notre hints > leur fichier** |

**Ce qu'ils ont et qu'on NE veut PAS** : `scope.md` fichier par case (notre yaml central suffit, et le ROE gate G13 est runtime), le CLI-first (les CLIs entrent en concurrence avec les tools natifs), la lourdeur 35 k de `bootstrap-reverse.ps1` (on prend le manifest, pas le script), `RULES.md` 24 k de normes (notre doctrine tient en 60 lignes actives).

---

## ORDRE D'EXÉCUTION RECOMMANDÉ

```
P1 (skills wave 2 + routing upgrade)  →  P2 (payloads)  →  P3 (bootstrap)  →  P7 (tests partiels)
→  P4 (journal)  →  P6 (hygiene)  →  P7 (battery finale)  →  P8 (restart + Juice Shop)
P5 (burp) : séparé, sur décision de LO
P9 = lecture/analyse (déjà faite — mapping documenté ci-dessus)
```

**Total estimé** : ~6 h de travail effectif. Phases 1-3 = le cœur de valeur, faisables en une session.
