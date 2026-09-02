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

## LANE B — server state machine (server.py / chat.py / report.py) — 22 findings

### B-S1 [LOGIC-CRIT] `_RUN_STATE["running"]` fuit hors du try — exception au claim = gate bloquée pour toujours — ✅ vérifié ENI (server.py:1159-1161)
- **Fait** : flag posé à 1159, `start_mission` (1160, INSERT sqlite → OperationalError possible en écriture concurrente) et `_start` (1161) AVANT le try (1412) dont le finally libère (1450). Exception au claim → flag collé True → /mission 409 à vie, WS refusé, request_plan BUSY, aucun row DB pour le boot sweep — seul un restart backend débloque. /mission/status affiche « running » sans mission.
- **Fix** : envelopper le corps post-lock : `except: _RUN_STATE["running"]=False; raise`.
- **Confiance** : 88 % (fenêtre structurelle 100 %)

### B-S2 [HIGH] `_approve_and_strike` détruit le plan AVANT la gate 409 — ✅ vérifié ENI (server.py:921-922 vs 931)
- **Fait** : `_PENDING_PLAN.clear()` + `_save_pending_plan()` à 921-922, la gate 409 à 931-932. Approbation pendant une campagne → plan effacé du disque → 409 → l'approbation de l'opérateur est perdue, irrécupérable.
- **Fix** : remonter la vérification 409 avant le clear (ou clear après le scheduling du lancement).
- **Confiance** : 95 %

### B-S3 [HIGH] Plan-mode : `return` (1366) saute `board.save()` (1393) — la cartographie de recon ne survit que par le coalescer 2s
- **Fait** : les observations finales (<2s avant extraction du plan) et tout état dirty ne rejoignent jamais `data/intel/<target>.json` ; la frappe approuvée recharge une intel qui manque exactement la cartographie la plus fraîche.
- **Fix** : dupliquer `board.save()` avant le return.
- **Confiance** : 82 %

### B-S4 [MED] Honnêteté d'abort : mode IA seulement — Swarm/Offline ne lisent jamais `last_abort_reason`, et les missions swarm N'ONT PAS d'inbox
- **Fait** : abort swarm → `status="complete"` en DB + broadcast mission_complete.
- **Fix** : peupler `_agent_reason` pour Swarm/Offline ou plomber l'inbox dans le coordinateur swarm.
- **Confiance** : 92 %

### B-S5b [LOW] Broadcast « Ordres du commandant armés » (1324-1327) ment pour Offline (chat_context jamais consommé — plan(mission) ne prend pas d'ordres). Fix : gater le broadcast.

### B-S6 [MED] `intel_mode="last"` : match par n'importe-quel-token >4 chars (1280-1299) → le MAUVAIS rapport chargé comme prior_intel (« target », « server », « recon » matchent n'importe quel header récent) ; tri filename same-second arbitraire.
- **Fix** : exiger la cible extraite dans le header ; étendre les exclusions. **Confiance** : 85 %

### B-S7 [MED] Dernier delta stream_cb peut broadcaster après release du turn lock (953-989) → chunk périmé efface le draft de la PROCHAINE réponse. Fix : compteur de génération dans stream_cb. **Confiance** : 60 %

### B-S8 [MED] `/chat/clear` (999-1003) et `/admin/fresh{chat}` (1019-1022) mutent l'historique SANS `_CHAT_TURN_LOCK` → réponse en vol appendue à une liste vidée, bulle orpheline, drift de count(). Fix : lock non-bloquant 409. **Confiance** : 90 %

### B-S9=C-1 [HIGH] voir C-1 (l'ancrage mécanique est chat.py:236 vs 293-296 ; impact server via get_context 566-567 → commander_orders)

### B-S11 [LOW] Le 504 /tool « worker libéré » est FAUX — wait_for n'annule pas le thread ; l'outil tourne pendant des heures et son sync_emit continue de broadcaster. Fix : message honnête + deadline coopérative. **Confiance** : 96 %

### B-S13 [LOW] admin_fresh purge intel `startswith(f"{tgt}.")` (1049) → cible `test` détruit `test.local.json` (les slugs blackboard gardent les dots internes). Fix : suffixes exacts.

### B-C1 [HIGH] chat.py:236 — le fallback d'exception bypass le guard de doctrine (249 : `("[LLM HTTP", "[LLM UNREACHABLE", "[LLM MALFORMED")` — « [chat indisponible » ne matche pas), entre en history (305), et get_context (309-325) le ré-exporte comme `STRATÈGE:` dans le bloc « autorité maximale » injecté en plan/strike — contradiction directe du commentaire 249-252. — ✅ vérifié ENI
- **Fix** : préfixer 236 avec `[LLM UNREACHABLE` (une ligne) ou étendre le tuple de 293. **Confiance** : 97 %

### B-C3 [MED] for/else exhaustion (221-291) : les tool_calls du 8e round EXÉCUTENT (286-289) puis leurs résultats sont jetés à l'épuisement (291) — exécution gaspillée, history n'en garde rien. Fix : refuser les tool_calls au dernier round. **Confiance** : 90 %

### B-C4 [LOW] Mapping de l'échec execute_plan par substring « aucun plan » (server.py:876) — correct aujourd'hui, à un message près d'un mislabel 409→NO_PLAN_PENDING. Fix : match exact ou exception sentinelle.

### B-C5 [LOW] `_specs()` invalidée seulement au self-forge (190-193) — un outil forgé par une MISSION est invisible au catalogue chat jusqu'au rebuild de session. Fix : invalidation par tour ou sur changement de count du registry.

### B-C6 [LOW] Placeholder de refus absorbé (300-304) apparaît dans /chat/log et gonfle turns.

### B-R2 [HIGH] report.py `_extract_findings` — dédup `(sev, match[:80])` (36-38) : deux SECRETS DISTINCTS au même préfixe 80 chars (JWTs du même issuer — courant) → le second disparaît silencieusement du livrable client.
- **Fix** : clé sur le match complet/hash + conserver les compteurs de collapse. **Confiance** : 93 %

### B-R3 [MED] Règles 6/8 (16, waf|cloudflare|supabase.co…) fient sur des MENTIONS pas des findings — « no buckets found on *.supabase.co » produit une ligne MEDIUM. Fix : exiger une forme URL/credential ou un verdict token. **Confiance** : 88 %

### B-R4 [MED→LOW] `findings[:40]` (46) tronque sans « +N more » ; l'Executive Summary (87-90) ne compte que la liste plafonnée. Fix : total + suppressed count.

### B-R1 [revised LOW] `_tool_ledger` (48-62) CORRECT pour tous les producteurs de transcript (vérifié) ; caveat : swarm.py:203 `tr[:60]` → ligne Outcome = borne basse présentée comme total. Fix : compter depuis missions.db.

### Vérifiés-propres (lane B) : pas de deadlock chat-lock/_save_chat_log ; pop d'inbox exception-safe ; sweep boot pré-requis ; délimiteurs UNTRUSTED corrects (rapports+docs wrap, autonomy/chat_context trusted) ; ROE header fidèle ; échec d'écriture de rapport bruyant.

### Verdicts santé logique (lane B)
- web/backend/server.py — **7.5/10** (squelette de cycle de vie sain ; les 3 derniers fixes ont laissé chacun une couture : S-1 flag hors finally, S-2 clear avant gate, S-3 return avant save — tous <10 lignes)
- core/chat.py — **6.5/10** (mécanique session/history serrée ; le guard de doctrine rate son propre chemin d'exception)
- core/report.py — **8/10** (contrats producteurs vérifiés ; faiblesses sur la fidélité des findings)

### TOP 3 si seulement trois fixes (lane B) : S-1 (wedge permanent), S-2 (plan approuvé détruit), C-1 (erreurs canonisées en doctrine du commandant).

### Non vérifiables (lane B) : abort coopératif côté outil ; ordering tail de chat_stream (mandat lane D) ; probabilité de contention sqlite pour la trace S-1 ; internals du retry llm.py.

## LANE C — tool execution logic — ⏳ en attente de re-naissance
## LANE D — memory/pipeline (8 fichiers) — 13 findings + convergence E5=M-7

### D-M1 [LOGIC-CRIT] `_seed_from_db` appelle `_record(...)` qui N'EXISTE PAS — NameError garantie — ✅ vérifié ENI (grep : seul `bandit_record` existe, mathcore.py:144)
- **Où** : core/mathcore.py:141
- **Fait** : le seeding DB du bandit est mort depuis toujours ; avalé silencieusement par les try/except des callers (agent.py:1300/1406, planner.py:161) → le bandit n'apprend JAMAIS rien de missions.db. `bandit_reset(seed=True)` (:261) raise hors du lock. Une suppression de bandit.json = le fallback offline round-0 meurt au moment où on en a le plus besoin (install fraîche + provider down) — attack_graph:486 dans la même chaîne.
- **Fix** : `bandit_record(name, status == "ok", float(dur or 0.0), save=False)` — un token.
- **Confiance** : 100 %

### D-T1 [HIGH] `_CRED_FIELD_RX` masque `Bearer` et laisse le JWT en clair — ✅ vérifié ENI (_tokenize.py:34 : la classe exclut `\s`)
- **Fait** : `Authorization: Bearer eyJ…` → group(2) = `Bearer` (6 chars, match `{6,}`) → `Authorization: [CRED-n] eyJ…` — le JWT part brut vers le provider. `Basic` (5 chars) : pas de match du tout → toute la ligne fuit. Le flagship du module rate son cas #1.
- **Fix** : `([^\"',}&\n]{6,})` (consommer jusqu'au quote/fin-de-ligne, trim) ou préfixe optionnel `(?:(?:Bearer|Basic|Token)\s+)?`.
- **Confiance** : 99 %

### D-B1 [HIGH] Save coalescé blackboard : `_dirty` est un flag mort — les dernières écritures de chaque mission single-agent sont perdues — ✅ vérifié ENI (blackboard.py:282 posé, jamais lu ; seuls callers de save() = swarm.py:198/342)
- **Fait** : « le prochain save() complet rattrape » — il ne vient jamais hors swarm : ni flush de fin de mission, ni abort, ni crash. `load()` reconstruit uniquement depuis le JSON → l'intel prouvé par le `.events.jsonl` est absent du graphe que la mission suivante charge. Composé avec G-1 : la copie git ressemblait à une persistance et masquait le bug.
- **Fix** : `if self._dirty: self.save()` au teardown agent (à côté du power-report) + dirty-check dans observe().
- **Confiance** : 97 %

### D-S1 [HIGH] skills.py:89-90 — les lookarounds CJK (fix R1-1) ne matchent toujours pas au milieu de texte CJK
- **Fait** : `(?<![^\W_])` ≡ `\b` pour le CJK car les idéogrammes SONT `\w` en Unicode Python. Vérifié empiriquement par la lane : `越权` dans `测试越权漏洞` → NO MATCH. Les triggers `when:` zh restent morts, les vetos `not_when:` CJK ne tirent jamais (skill à veto contourné). Seul gain réel : les frontières underscore.
- **Fix** : substring brut pour les keywords non-ASCII ; lookarounds seulement pour l'ASCII.
- **Confiance** : 99 % (sonde exécutée)

### D-M2 [MED] tests/test_mathcore.py:31-34 persiste dans le store de PRODUCTION (core/bandit.json) — fingerprint numérique vérifié (51.95940596870745 = somme de decay des fixtures) ; chaque run de test réécrit le store prod, t global gonflé de ~103 obs factices, faux priors dans bandit_history(). Volet git corrigé (G-1, ff46e74). **Fix restant** : BANDIT_PATH sur tmp ou save=False dans les tests. **Confiance** : 98 %

### D-B2 [MED] blackboard.py:44-58 — `_fuse` empile le prior +1.0 à CHAQUE ré-observation (0.60 → 0.828 en 2 échos, saturé ~0.83) — l'echo d'une source unique bat la corroboration indépendante (0.828 vs 0.818). Distinct de E5 (groupement) et compose avec lui. **Fix** : prior appliqué une fois à la création. **Confiance** : 95 %

### D-M3 [MED] mathcore.py:327 — l'AIMD compte `status=-1` (timeout/DNS/refus, truthy et <400) comme CLEAN SUCCESS → le pacer ACCÉLÈRE vers les hôtes morts (20 échecs rapides = +inc jusqu'à max_rate). **Fix** : `elif status and 200 <= status < 400:`. **Confiance** : 96 %

### D-L1 [MED] llm.py:173 — `tc["function"]` non gardé côté parsing réponse (KeyError sur tool_call malformé → round tué) — la classe exacte que R1-7 a corrigée côté requête. **Fix** : `tc.get("function") or {}` + skip `_args_error`. **Confiance** : 93 %

### D-L2 [MED] llm.py:88-89 — le fix R1-6 tronque les noms de tools streamés en fragments (vLLM/sglang) → tout call devient UNKNOWN_TOOL pour le reste du stream. **Fix** : accepter un delta full-name qui commence par l'accumulé. **Confiance** : 88 %

### D-T2 [MED] agent.py:1002-1007 — `reset_vault()` à CHAQUE Agent.run course le swarm : le reset de B efface les jetons émis par A après son démarrage → les args de A arrivent avec `[HOST-7]` littéraux → la frappe vise un hostname littéral. **Fix** : reset une fois par campagne (coordinateur) ou epoch-counter. **Confiance** : 90 %

### D-T3 [MED] _tokenize.py:34 — secrets avec espaces ou <6 chars passent en clair ; URL-creds `user:p@ss@host` masquent `p`, fuient `ss@host`. **Fix** : retirer `\s` de l'exclusion + longueur min sur URL-creds. **Confiance** : 95 %

### D-J1 [MED] trajectory.py:161-163 — `chains()` classe par *meilleur état vu une fois* (EXPLOITED chanceux, 0 % de succès, bat une chaîne 95 % fiable) — contredit son docstring. **Fix** : rate en tête de clé, best-state en tie-break. **Confiance** : 96 %

### D-F1 [MED — advisory, arbitrage opérateur] framing.py:305 — le fix R1-9 n'exempte que `role:"tool"` ; l'evidence injectée en `role:"user"` (wall_breaker 1506, Living Graph 1042, prior_intel 1055) reste normalisée par reframe_with_scope (`exploit`→`validate` DANS la donnée cible). ⚠ Au bord de la couche d'acceptation exclue par ordre permanent — mécanique nouvelle (canal user), pas les blocs exclus ; à trancher. **Confiance** : 92 %

### Minors lane D : D-M4 (garde rate≤0 mort aujourd'hui, free-pass demain) · D-M5 (spike détecté contre l'EWMA post-update — s'auto-masque en début de fenêtre) · D-M6 (cap 64 pacers mou — hôtes actifs = croissance sans borne) · D-S2 (élargissement silencieux des sémantiques ASCII aux underscores — docstring « exact old behavior » faux) · D-S3 (branche cap skills inatteignable) · D-T4 (`_classify()` mort) · D-T5 (`enabled()` relit provider.yaml à chaque call) · D-B3/B4 (course rotation bénigne ; tmp orphelins par-thread) · D-J2/J3 (bigrams transposés intra-round ; insight sans lock auto-cicatrisant) · D-ST1/ST2 (finish_mission écrase summary si re-fin ; sweep falsifierait une mission vivante en mid-campaign) · D-L3 (HTTPError body jamais fermé → socket tenu au GC).

### Convergence inter-lanes
M-7 lane D = **E5 lane ENI** (mathcore.py:419-441) — double confirmation indépendante, confiance montée à 95 %. B-2 distinct de E5 et compose avec lui (groupement + prior gonflé = confiance doublement fausse). Zéro contradiction avec les lanes A/B.

### Vérifiés corrects (positifs lane D)
Bloom (paramétrage standard, h2 impair) · fuse_finding (LR sévérité linéaire, math sound) · UCB1-Tuned (variance récompense, le bug duration-variance réellement corrigé) · decay non-stationnaire (reproduit le 51.9594 du disque — le modèle est bon, sa persistance polluée) · roundtrip mask→unmask byte-près sur le happy path (R1-2 ✓) · `_bandit_save` atomique sous lock (R2-3 ✓) · rotation/tail/_count_lines multibyte trajectory — les 3 craintes levées · roundtrip edges `|` avec maxsplit=2 (subtil et juste) · close/retry/salvage llm.py (R1-5/7 ✓ côté requête) · state.py dédup propre (9/10, le plus propre du lot).

### Verdicts santé logique (lane D)
mathcore **4/10** · _tokenize **5/10** · blackboard **5/10** · skills **6/10** · llm **7/10** · framing (mécanique) **7/10** · trajectory **8/10** · state **9/10**

### Non vérifiables (lane D) : densité CJK du corpus skills ; provenance exacte du bandit.json pollué ; providers à noms streamés en fragments ; swarm.py:342 partiel ; `framing_msgs` n'existe pas dans framing.py (le trimming vit dans agent.py:1212/1520 — pointer, hors périmètre).

---

## Contre-vérifications ENI (ancres recoupées par lecture directe)
**Lane A (13/13)** : A1 ✓ · A2 ✓ · A3 ✓ · A4 ✓ (substring pur 938 + nudge auto-référentiel 1350) · A5 ✓ (continue sans compteur 1346-1351) · A6 ✓ · A8 ✓ · H2 ✓ · H3 ✓ (load hors lock 10-17, open("w") en place 21) · H4 ✓ (premier http(s) quelconque 98, suffixe .js forcé 102) · H5 ✓ · M1 ✓ (kind non-slugifié 259) · H-LOW2 ✓ (NETWORK aliasing 93)
**Lane B (3/3)** : B-S1 ✓ (flag 1159 hors try, start_mission 1160) · B-S2 ✓ (clear 921-922 avant gate 931) · B-C1 ✓ (fallback 236 hors guard 249)
**Lane D (3/3)** : D-M1 ✓ (grep : `def _record` inexistant, CRIT mécanique) · D-T1 ✓ (classe `[^\\s…]{6,}` → `Bearer` masqué, JWT en clair) · D-B1 ✓ (`_dirty` posé 282, jamais lu ; callers save() = swarm seulement)
**Total : 19/19 confirmées.**
