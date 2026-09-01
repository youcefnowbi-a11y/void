# VOIDFORGE — LOGIC AUDIT (lentille fraîche)

**Objectif** : « est-ce que le code fait ce qu'il prétend ? » — conditions inversées, branches mortes, trous d'état, dérive docstring/réalité, contrats inter-modules, pertes silencieuses.
**Périmètre exclu** : tout ce que docs/CODE_REVIEW.md a déjà trouvé (vérifié non re-flaggé). Couche d'acceptation (chat/framing normalize) exclue par ordre permanent.
**Référence git** : baseline `ecc2464` (état vert 122/122) — chaque finding ancré `file:line` est valide contre cette référence.
**Statut** : 🔄 en cours — lanes ENI-cerveau + A livrées et contre-vérifiées ; lanes B/C/D attendues.

---

## LANE ENI — cerveau (MCTS / bandit / planner) — 9 findings

### E1 [LOGIC-HIGH] planner.py — branche JWT: `has_specific=True` sans rien ajouter → plan vide
- **Où** : core/planner.py:83-87
- **Fait** : kw `jwt|forge` sans token `eyJ…` dans la mission → rien ajouté MAIS `has_specific = True` → la chaîne de recon par défaut (126-132) est supprimée → `plan_` vide → mission offline sans aucun outil. Idem si kw présent et token présent ça va, mais « jwt analysis of site.com » (sans token) = mission fantôme.
- **Fix** : `has_specific = True` seulement si `tok_m` (ou ajouter `jwt_analyst` au PLAN_TOOLS offline en fallback).
- **Confiance** : 95 %

### E2 [LOGIC-MED-HIGH] planner.py:13 — TLDs hardcodés, `.fr` absent → cible invisible
- **Fait** : `extract_target` ne reconnaît que `com|net|org|me|io|site|shop|store|xyz|tv|cc`. « audit test.fr » → cible None → ni chaîne recon ni MCTS (`attack_graph.extract_state` importe le même parser) → plan vide.
- **Fix** : élargir la liste (fr, dev, app, co, biz, eu, de, uk, ca, au, us, info, online, shop… déjà là) ou accepter 2+ labels avec TLD alpha.
- **Confiance** : 90 %

### E3 [LOGIC-MED] attack_graph.py — composite `ref|key` fuit dans les args réels via plan_smart
- **Où** : attack_graph.py:393-403 (`supabase_exfil` targets `f"{r}|{k}"`), plan_smart enchaîne les steps imaginés
- **Fait** : `successor()` crée des facts `("table", "ref|key")` / `("data", "ref|key")` → un step suivant `data_dump_paginated` reçoit `{"table": "ref|key"}`. Ça ne marche que parce que les 2 outils re-splitent `|` eux-mêmes — contrat accidentel entre couches, aucun autre consommateur de `table` ne le tolère.
- **Fix** : args builder de `data_dump_paginated`/`realtime_tap` doit strip la partie ref, ou successor() doit produire des facts de valeur propre.
- **Confiance** : 85 %

### E4 [LOGIC-MED] attack_graph.py:214 — `sqli_union_dump` (strike) gate plus large que le probe
- **Fait** : pre `has("endpoint") or has("vuln")` — l'union dump (4.5 yield) est légale dès le premier endpoint, SANS confirmation vuln ; `sqli_blind_extract` (220) exige `has("vuln")` (strict). La doctrine probe→confirme→strike est contournée par le value model : MCTS peut sauter direct au dump.
- **Fix** : pre `s.has("vuln")` comme blind_extract (l'endpoint seul ne justifie pas un strike SQLi).
- **Confiance** : 80 %

### E5 [LOGIC-MED] mathcore.py:431-435 — clé de corrélation `(detail)[:40]` sur-discount
- **Fait** : `fuse_findings_from_db` corrèle sur les 40 premiers chars du détail : deux findings DISTINCTS au préfixe identique se discountent mutuellement (ex: même endpoint, ids différents) ; et formats de détail hétérogènes entre tools → même finding réel jamais corrélé → compté deux fois plein poids. La postériorité dépend de l'ordre d'insertion.
- **Fix** : clé = hash du champ value normalisé (URL/chemin canonique) plutôt que préfixe de détail ; ou corrélation sur (tool_class, normalized_target).
- **Confiance** : 75 %

### E6 [LOGIC-LOW] attack_graph.py:261 — `upload_webshell` pre à moitié morte
- **Fait** : `has("endpoint","upload") or has("endpoint")` — 2e clause subsume la 1ère ; le ciblage upload ne vit que dans targets (avec fallback tous endpoints).
- **Fix** : `pre: s.has("endpoint", "upload")` strict si on veut l'intention, sinon documenter la préférence.
- **Confiance** : 100 %

### E7 [LOGIC-LOW] attack_graph.py:558 — `root_prior` vestigial (dead fallback)
- **Fait** : calculé via `available(root_state)` (coût complet) à chaque search(), consommé seulement si un enfant a N=0 — n'arrive jamais (le backprop per-edge N+=1 sur chaque feuille créée). Branche morte.
- **Fix** : supprimer ou garder en garde défensive documentée.
- **Confiance** : 95 %

### E8 [LOGIC-LOW] mathcore.py:50 — `_DEFAULT_P` mort ; L210 bonus inf mort
- **Fait** : `_DEFAULT_P` jamais lu (surprisal utilise son propre défaut 0.02) ; le `float("inf")` de `_ucb1_tuned` (n≤0) est inatteignable — `_stats` retourne None pour n=0 → branche unseen. Code mort double.
- **Confiance** : 100 %

### E9 [LOGIC-LOW] planner.py:150 — conditionnel mort + liste d'exclusions française incomplète
- **Fait** : `{"keyword": x} if tool == "nvd_search" else {"keyword": x}` branches identiques ; exclusions sans « trouve/analyse/scan/cherche-moi » → « trouve les CVE wordpress » → keyword="trouve".
- **Confiance** : 100 %

---

## LANE A — campaign loop (agent/swarm/healer/workspace) — 20 findings

### A1 [LOGIC-HIGH] Offline brain exécute le registry complet, bypass plan_mode + filtres spécialistes — ✅ vérifié ENI (agent.py:1295)
- **Où** : core/agent.py:1270-1317
- **Fait** : LLM mort au round 0 → `plan_smart`/`plan` émettent des strikes → `reg.execute()` direct, sans passer par `self.tools` ni vérifier `plan_mode`. Mission plan-mode + provider down = strikes exécutés sans plan approuvé.
- **Fix** : filtrer les steps par le name-set de `self.tools` (drop + log), ou hard-no-op offline brain si `plan_mode`.
- **Confiance** : 95 %

### A2 [LOGIC-HIGH] `batch_execute` bypass TOUS les tools_filter — clôture plan-mode = prompt-only — ✅ vérifié ENI (batch.py:64)
- **Où** : tools/batch.py:62-66 vs core/agent.py:797-858
- **Fait** : batch est dans PLAN_TOOLS et tous les toolsets spécialistes ; ses appels internes vont au registry nu (`_reg.execute`), qui ne connaît ni plan_mode ni le filtre de l'agent appelant. `batch_execute(calls=[{tool:"sqli_union_dump",…}])` en plan-mode → strike à plein privilège.
- **Fix** : thread-local `allowed_tools` posé par `execute()` de l'agent, consulté par le dispatch interne de batch (miroir du pattern `_thread_state.current_event`).
- **Confiance** : 95 %

### A3 [LOGIC-HIGH] Wall-reflex insère `user` entre `tool_calls` et `tool` → 400 provider → mort de mission — ✅ vérifié ENI (agent.py:1506 vs 1516)
- **Où** : core/agent.py:1485-1512
- **Fait** : 2 outputs « wallish » (403/waf/blocked/rate limit — regex très large) → `msgs.append(user wall-intel)` AVANT l'append du tool result → ordre `[assistant(tool_calls), user, tool…]` invalide chez les providers stricts (OpenAI/DeepSeek/GLM) → 400 → retry ×2 sur la même history empoisonnée → 3 échecs consécutifs → `llm_dead` sur mission saine. Secondaire : l'appel wall_breaker auto (1498) n'a pas d'on_event → invisible ledger/bandit.
- **Fix** : collecter le bloc wall et l'injecter APRÈS tous les tool results du round.
- **Confiance** : 75 % (violation d'ordre certaine, le 400 dépend du provider)

### A4 [LOGIC-MED] Markers de rapport final en substring → mission terminée sur un écho
- **Où** : core/agent.py:930-938, 1342, 1348-1351, 1533-1537
- **Fait** : `_is_final_summary` = substring (« RAPPORT DE MISSION », « EXECUTIVE SUMMARY », « ## VERDICT », « # 🎯 ») ; le nudge lui-même contient la phrase → une réponse textuelle « Understood — writing my RAPPORT DE MISSION FINAL now » termine la mission et l'écho devient le rapport final sauvé.
- **Fix** : marker ET structure (titre en début de ligne / ≥2 sections requises), jamais sur une phrase d'intention.
- **Confiance** : 70 %

### A5 [LOGIC-MED] Réponses textuelles sans outil : zéro compteur d'escalade → boucle payante infinie
- **Où** : core/agent.py:1341-1354, 865-867, config/provider.yaml:6-7
- **Fait** : contenu vide/null sans tool_calls → nudge → continue, n'incrémente RIEN (`consecutive_llm_fails` intact) ; `max_tool_rounds: 0` = 10**9 ; wall-clock off. Provider qui renvoie du content null (content-filter, reasoning-only) = loop API payant sans fin.
- **Fix** : compteur no-tool non-final (≥5 → hard « stop and report » ; ≥10 → abort `stalled`).
- **Confiance** : chemin 100 %, déclencheur réel ~60 %

### A6 [LOGIC-MED] PlannedSwarm — collision de noms de chaînes → transcript écrasé, travail perdu — ✅ vérifié ENI (swarm.py:269→300)
- **Fait** : pas de dédup : 2 chaînes « recon » → la 2e écrase la 1ère dans `self.transcripts` ; une chaîne nommée « verifier » est écrasée par le vrai verifier (323). Findings perdus sans signal.
- **Fix** : `name if name not in self.transcripts else f"{name}-{i+1}"`.
- **Confiance** : 95 %

### A7 [LOGIC-MED] PlannedSwarm ne re-dérive jamais la cible « unknown » → intel cross-mission contaminée
- **Où** : core/swarm.py:251-266 vs 127-129, 104-112 ; server.py:1374
- **Fait** : TLD hors whitelist (.fr, .shop…) → `_target_from_mission` → « unknown » → le run() parent re-dérive, PAS PlannedSwarm → tout fuse dans `intel/unknown.json` partagé, workspace réel ailleurs = split-brain.
- **Fix** : 2 lignes en tête de `PlannedSwarm.run` (re-dérive + Blackboard cible).
- **Confiance** : 90 %

### A8 [LOGIC-MED] Fallback mort : `or spec["tools"]` inatteignable — chaîne sans `tools` = arsenal 2 outils — ✅ vérifié ENI (swarm.py:278)
- **Fait** : la meta-pair est appendue inconditionnellement → liste jamais vide → or mort. Chaîne sans tools → `batch_execute` + `arsenal_selftest` seulement (aveugle, et aggrave A2).
- **Fix** : `(requested or spec["tools"]) + meta pair`.
- **Confiance** : 95 %

### H1 [LOGIC-MED] healer — l'apprentissage est de la fiction write-only
- **Où** : core/healer.py:1-3, 47-63
- **Fait** : `learn_flag_migration` zéro caller prod ; `get_learned_fix` zéro caller ; seul `learn_generic` écrit des notes que personne ne lit (12 dans le fichier live). DEP_MISSING/AUTH_EXPIRED/BROWSER_MISSING : aucune branche de heal. « never blocks twice on the same wound » non implémenté.
- **Fix** : brancher `get_learned_fix` dans heal_attempt (conseil stocké injecté dans l'erreur), ou réécrire la docstring.
- **Confiance** : 97 %

### H2 [LOGIC-MED] Exit heal-exhausted : ni event terminal ni apprentissage — trou de ledger corroboré prod — ✅ vérifié ENI (tools/__init__.py:410-418)
- **Fait** : le `continue` du 3e heal consomme la tentative → sortie par 418 « exhausted » sans `tool_error` ni `learn_generic` → pending jamais fermé, ligne absente du power report, LiveConsole en suspens. Observé : report_20260901_191141.md:314 (graphql_introspect).
- **Fix** : avant le return 418 : émettre tool_error (HEAL_EXHAUSTED) + learn_generic.
- **Confiance** : 95 %

### H3 [LOGIC-MED] learned_fixes.json — « lock » ne couvre pas read-modify-write, écriture non atomique, corruption = wipe silencieux
- **Où** : core/healer.py:8, 10-22, 52-63
- **Fait** : load hors lock → mutate → save (lock sur l'écriture seule) → update perdu entre 2 learners concurrents ; `open("w")` en place (pas tmp+os.replace) → un _load au moment de la troncature lit `[]` sans erreur loggée ; crash mid-write = état appris détruit.
- **Fix** : wrap load+mutate+save dans `_FIXES_LOCK` + écriture atomique (pattern blackboard).
- **Confiance** : 90 %

### H4 [LOGIC-MED] FILE_EXPECTED heal peut re-viser le mauvais ressources
- **Où** : core/healer.py:41, 94-112
- **Fait** : premier arg http(s) = souvent un paramètre non-fichier (url_template avec `{INJ}`) → téléchargé en .js, tous les args égaux réécrits → verdicts de traversal contre une copie locale = fiction sans signal.
- **Fix** : swap restreint aux args de type file-path selon le schéma + skip des valeurs avec `{`/`}`.
- **Confiance** : 80 %

### H5 [LOGIC-MED] `learn_generic` non gardé dans execute() peut tuer la mission et sauter le closure — ✅ vérifié ENI (tools/__init__.py:411)
- **Fait** : PermissionError (fichier ouvert dans l'éditeur — le commentaire invite à l'édition manuelle) → propage → agent loop sans try → run() meurt sans power report ni mission_complete.
- **Fix** : try/except autour de 411.
- **Confiance** : 85 %

### M1 [LOGIC-MED] `write_report` slugifie le titre mais pas `kind` — segment de path contrôlé par le modèle
- **Où** : core/mission_workspace.py:256-260, caller tools/workspace_tools.py:15-31
- **Fait** : `kind="../exfil"` remonte l'arborescence — le sibling du paramètre slugifié a été oublié (même classe que R5-5, instance nouvelle).
- **Fix** : `kind = _slug(kind) or "progress"`.
- **Confiance** : 95 %

### M2 [LOGIC-MED] Workspace pens thread-local → mortes dans batch, là où la doctrine pousse à écrire
- **Où** : core/mission_workspace.py:365-374, tools/batch.py:68, agent.py:644-653/512
- **Fait** : `set_active` sur le thread mission seulement ; tools internes batch (pool 5 workers) → `get_active()` None → report_write/evidence_pack en erreur, `operator_message` droppe SILENCIEUSEMENT en rapportant `delivered: true`.
- **Fix** : propager le ws actif via le même canal thread-local que les events (capture au 355, restore dans les workers batch).
- **Confiance** : 95 %

### M3 [LOGIC-LOW→MED] `extract_target` workspace : premier token dotted gagne (v1.2.3, config.yaml) → dossier poubelle
- **Où** : core/mission_workspace.py:50-52, 377-379
- **Fix** : TLD-whitelist ou helper `looks_like_domain` partagé (swarm.py:108).
- **Confiance** : 85 %

### A7b [LOGIC-LOW] Abort/timeout ne produisent jamais le rapport partiel promis (doctrine 453-454).
### Minors (lane A, vérifiés) : A-LOW1 pending key par tool name (batch 5 workers overwrite), A-LOW2 offline brain logge les erreurs hors ledger, A-LOW3 « ROUND 5/1000000000 », M-LOW1 dead-list markdown malformé, M-LOW2 exploitable non-bool passe l'identité, M-LOW3 workspace « reuse » fantôme (untitled_<ts> ×6), S-LOW1 chaînes dropées silencieusement > max_subagents, H-LOW1 TIMEOUT sans knob = 2 échecs identiques garantis, H-LOW2 NETWORK branch aliasing.

### Verdicts santé logique (lane A)
- core/agent.py — **6/10** (mécanique solide, clôtures « peintes »)
- core/swarm.py — **6/10** (rien ne crashe, des choses se perdent silencieusement)
- core/healer.py — **4/10** (il soigne un peu, il ne se souvient de rien)
- core/mission_workspace.py — **6/10** (le concept marche, les bords fuient)

---

## LANE B — server state machine — ⏳ en attente de re-naissance
## LANE C — tool execution logic — ⏳ en attente de re-naissance
## LANE D — memory/pipeline — 🔄 en vol

---

## Contre-vérifications ENI (ancres recoupées par lecture directe)
A1 ✓ · A2 ✓ · A3 ✓ · A6 ✓ · A8 ✓ · H2 ✓ · H5 ✓ — **7/7 confirmées**.
