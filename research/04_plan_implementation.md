# 04 — PLAN D'IMPLÉMENTATION : trois moteurs dans VOIDFORGE

*Architecture d'intégration. Les dossiers 1-3 (chercheurs) apportent le SOTA ;
ce document verrouille comment chaque moteur s'insère dans l'arsenal, AVANT
que la première ligne de moteur ne s'écrive.*

---

## 0. Le contrat commun (non négociable)

Chaque moteur expose ses outils via `tools.register()` avec le contrat verdict
existant (`tools/_exploit_lib.verdict`) :

```python
verdict(tool_name, exploitable, summary, evidence=[...])
# exploitable ∈ True | False | "partial"
# evidence  : chaîne JSON — toujours le PoC ou la trace, LAW OF THE REPORT
```

Conséquences automatiques (déjà câblées dans l'agent, zéro code nouveau) :
ledger via l'event tap unifié (même les appels dans batch), Living Graph,
rapport de puissance 4-voies, auto-append `proof_section()`. Les trois moteurs
sont classés **STRIKE** dans la loi d'équilibre 40/15/20/25 — ils consomment
du budget strike et produisent des findings FORTE.

---

## 1. `auth_state_engine` (dossier_3 → moteur)

**Fichier cible : `tools/auth_state_engine.py`** — pure Python stdlib +
`tools/_transport` (fetch durci) + `tools/_exploit_lib` (paced_send, verdict).

### Outils

| Outil | Signature | Ce qu'il fait |
|---|---|---|
| `auth_flow_map` | `(base_url, flow="oauth2"\|"oidc"\|"saml"\|"magic_link"\|"mfa", max_steps=12)` | Instrumente le flux avec une matrice de sessions (attaquant × victime — 2 identités), trace toutes les requêtes/redirs/tokens, **infère l'automate** : chaque requête = transition, chaque état observable = message d'erreur/cookie/redirect. Rend l'automate en JSON. |
| `auth_property_check` | `(trace_json, properties="no_skip,no_replay,binding,entropy")` | Évalue les 4 monitors LTL sur la trace inférée : no-skip (étape N+1 sans preuve N), no-replay (codes réutilisables), binding (issuer/audience/subject croisés — mix-up), entropy (H(state) ≥ 128, H(code) ≥ 160 — `L·log₂|charset|`). Chaque violation = finding avec le chemin PoC exact. |
| `auth_race_probe` | `(url_single_use, n_streams=20, protocol="h1"\|"h2")` | Fenêtre de course sur les endpoints à usage unique : N streams parallèles avec le même code/token (single-packet style : une connexion, requêtes alignées sur le même flush TCP). P(réussite) empirique sur 5 séries. |

### Détails de conception

- La matrice de sessions est LA clé : `pool = {A1: Session(), A2: Session(), V1: Session()}` —
  les propriétés de binding se testent en croisant les tokens entre identités.
- L'inférence L* complète (AALpy) est optionnelle en v1 : la v1 infère la
  machine à partir des traces observées (transition map empirique) — suffisant
  pour les 4 propriétés, 200-400 requêtes par flux.
- Les monitors s'écrivent comme des **runtime monitors** (fonctions pures sur
  la trace JSON) — testables unitairement sans cible.

## 2. `binary_fuzzer` (dossier_2 → moteur)

**Fichier cible : `tools/binary_fuzzer.py`** — la réalité Windows dicte trois
stratégies, l'outil choisit automatiquement.

### Outils

| Outil | Signature | Stratégie |
|---|---|---|
| `binary_fuzz_run` | `(target_path\|target_cmd, corpus_dir, mode="auto"\|"native"\|"unicorn"\|"network", minutes=10)` | `native` : cible compilée avec coverage (libFuzzer/-fsanitize=fuzzer) exécutée via WSL si dispo, sinon exécutable autonome + triage externe. `unicorn` : émulation de la fonction de parsing pure (harness synthétisé, coverage via hooks de blocs — indépendant de l'OS hôte). `network` : fuzzing étatique d'un service qui écoute (AFLnet-style : replay des séquences + mutations sur le dernier message). Ordonnancement : UCB1 + power schedule (formules dossier_2 §2.2-2.3), implémentées en Python pur. |
| `crash_triage_rank` | `(crash_dir)` | Dédup par stack-hash, symbolisation si dispo, **grade d'exploitabilité** : RIP contrôlable > write-what-where > deref contrôlé > data-only. Rend le tableau rangé. |
| `heap_window_analyze` | `(binary_path, alloc_trace)` | Modélise la fenêtre UAF : distribution des size-classes, P(réutilisation contrôlée) — informe le grooming. (v2 — après les premières campagnes natives.) |

### Réalités Windows (décision en attente du dossier_2)

- `unicorn` (pip installable, pur) = voie royale sans WSL pour les parsers purs.
- WSL2 (si présent) = libFuzzer/AFL++ complets avec coverage true.
- `network` = aucune dépendance binaire : le fuzzing étatique réseau marche
  partout où Python tourne.

## 3. `framework_hunter` (dossier_1 → moteur)

**Fichiers cibles : `tools/framework_hunter.py`** (+ optionnellement un helper
Node pour l'AST JS).

### Outils

| Outil | Signature | Ce qu'il fait |
|---|---|---|
| `framework_map` | `(repo_path\|package_name, framework="next"\|"django"\|"express"\|"laravel"\|"spring")` | Extrait l'automate du pipeline de requêtes (middleware/filters/middleware-MRO) + inventaire des sinks dangereux par framework (dictionnaire embarqué, enrichi par le dossier_1). Rend le lifecycle en JSON avec les stages obligatoires marqués. |
| `taint_flow_scan` | `(repo_path, framework="auto")` | Point fixe de Kleene sur le PDG : sources = entrées requête (params/headers/cookies), sinks = exec/eval/deserialize/redirect/render. Python : `ast` natif. JS : parse via `node -e` + acorn si node dispo (il l'est — le frontend). Rend les chemins risque `e^(−Σσ)`. |
| `middleware_skip_probe` | `(base_url, pipeline_json)` | Le monitor no-skip EN LIVE : pour chaque stage obligatoire du pipeline, construit les candidats de contournement (headers de récursion, méthodes exotiques, encodages de path, suffixes de route) et vérifie si le handler répond sans que le stage ait filtré. La classe CVE-2025-29927. |
| `diff_version_probe` | `(pkg_name, vuln_version, fixed_version, probe_paths)` | Différentiel : deux environnements isolés (venv/npm prefix), même entrée x envoyée aux deux, violation d'invariant ou divergence = candidat. Patch-diffing guidé : les entrées qui atteignent les fonctions modifiées sont priorisées. |

## 4. Doctrine + skills

- Nouvelle skill `deep_0day_hunter` (SKILL LAYER) : charge la doctrine des
  trois moteurs (quand les utiliser, l'ordre : map → taint/monitor → probe →
  verdict), les limites de budget (chaque campagne de moteur = budget strike
  dédié), et les gabarits de rapport.
- `config/provider.yaml` : rien à changer. `max_tool_rounds` 40 suffisent pour
  des campagnes ciblées ; les moteurs longs (fuzz 10 min+) s'exécutent DANS un
  seul appel d'outil (le timeout subprocess 30 min de la config s'applique).

## 5. Ordre de bataille (après livraison des dossiers)

| # | Livraison | Effort | Pourquoi d'abord |
|---|---|---|---|
| 1 | `auth_state_engine` v1 (map + property_check, race en bonus) | ~2 sessions | 100% Python stdlib, zéro dépendance, valeur offensive immédiate sur madleets & co |
| 2 | `framework_hunter` v1 (framework_map + middleware_skip_probe) | ~2 sessions | La classe stage-skip est validée formellement (fondations §3.3) et hyper fréquente |
| 3 | `taint_flow_scan` + `diff_version_probe` | ~2 sessions | Dépend du dictionnaire de sinks du dossier_1 |
| 4 | `binary_fuzzer` v1 (mode unicorn + network, triage) | ~3 sessions | La plus lourde — attend les choix d'instrumentation du dossier_2 |
| 5 | Skill `deep_0day_hunter` + campagne de validation (cible lab volontairement vulnérable) | 1 session | Preuve de bout en bout : un 0day de lab trouvé, tracé, rapporté |

## 6. Critères d'acceptation (par moteur)

- Chaque outil renvoie un verdict() contract-conforme avec PoC en evidence.
- Un run complet sur cible-lab (flux OAuth volontairement vulnérable / parser
  avec overflow planté / middleware skippable) produit UN finding FORTE avec
  la preuve complète dans le workspace de mission.
- Aucun crash de l'agent quand la cible n'existe pas : verdict "partial" avec
  la raison, jamais d'exception qui tue le run (heuristique healer + L-6 batch).
