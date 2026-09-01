# VOIDFORGE — Rapport de session fix

**Session** : exécution de la vague corrective complète issue de `docs/CODE_REVIEW.md` (~108 findings).
**Mandat** : toutes les corrections techniques — la couche d'acceptation (framing normalize, chat system, détecteur) est **exclue par ordre de l'opérateur** (non actionnée, permanent).
**Contrainte respectée** : aucun backend redémarré — tout s'arme au prochain restart naturel. Aucun outil retiré, aucun seuil durci côté produit.

---

## Verdict final

| Mesure | Résultat |
|---|---|
| Batterie pytest complète (repo calme) | **122 passed, 0 failed, 0 error** — exit 0 |
| Suites script-style ré-ancrées | test_mathcore **24/24** · test_attack_graph **16/16** · test_healer **PASS** (live nuclei désormais opt-in `VF_LIVE_NET=1`) |
| Compile | core/ + tools/ + web/backend — **0 fichier cassé** |
| Gates comportementaux | IP nue hors-scope **bloquée**, in-scope **passe**, privé/local **passe** · Pacer 5 workers burst interdit (0.09s) · backprop smoke OK |

## Ce qui a été corrigé

### Vague 1 — ENI direct (les 5 verrous + 2 bonus)
| Fix | Fichier | Effet |
|---|---|---|
| F-1/R3-27 ROE fail-closed | tools/__init__.py | `do_not_exploit` bloque TOUT sauf `safe` (24 outils active/careful ne passaient plus avant) |
| R3-13 bare-IP scope | tools/__init__.py | les IPs nues traversent enfin G13 (la regex exigeait un TLD) |
| R3-15/R3-38 forge danger | tools/forge.py | label inconnu → `active` (jamais `safe`), vocab `safe/careful/active/loud/strike` + défaut `active` |
| R2-1 backprop per-edge | core/attack_graph.py | chaque nœud ancré sur l'arête qui l'a créé (v_in + γ·suite), racine = total complet, plus de double-compte |
| R2-2 Pacer consume-loop | core/mathcore.py | wait() garantit consume-ou-dort : un burst de waiters ne glisse plus sur un seul refill |
| R1-3 reset_vault | core/agent.py | nouveau coffre [CRED-n] par mission — zéro démasquage cross-campagne |
| R5-2 wordlist containment | tools/fuzz_engine.py | realpath — plus de `..\..\..\.ssh\id_rsa` dans le corpus |

### Clusters A-D (sous-agents, 54 fixes)
- **A — transport/llm/tokenize/skills/framing/healer (16)** : Retry-After ≤30s + parsing HTTP-date + budget wall-clock 300s partagé sur toute la chaîne fetch ; install_resolver atomique (TOCTOU→récursion morte) ; cache DNS AF_INET-only ; 303/302-POST sans body ; crédentials strippées sur redirect cross-host ; ROE gate après cache-hit ; eviction cache réponses ; chat() finally-close ; tool-name overwrite ; params schema fallback ; masking JSON-safe (structure préservée, roundtrip exact) ; TLD cn/ru/hk/tw/jp/kr/in/br/mx/au/ca/nl/se/ch ; CJK lookarounds ; role tool byte-identical ; healer get()-défensif.
- **B — server.py (13)** : Origin 403 (POST/PUT/DELETE/PATCH) ; /mission/message sans inbox = **404, plus jamais de campagne fantôme** ; rate limiter réel (append avant check) ; broadcast wait_for 5s ; écritures atomiques tmp+os.replace + ⚠ visible ; purge intel exact-slug ; /tool cap 20k + flag ; noms réservés Windows refusés ; `_contained()` realpath partout ; plan_dir slug-discipline ; 409 survit ; bind guard non-loopback sans token = refuse.
- **C — tools pattern-sweep (16)** : nday_runner **honnête** (exécution locale assumée) + double confirmation `execute=True` **ET** `confirm="YES"` ; deobfuscate max_index=300 (le no-op `i<0` mort) + try/finally harness ; deploy_watch snapshots confinés ; har defensive ; composite/ws_tap/spa_crawl/data_exfil résilients ; nmap cible validée ; fetch_local 64MB cap ; wall_breaker leg-failed findings + cache TTL/cap/atomique ; skill_loader validation+cap ; selftest mode gate ; **cn_fingerprint dédoublonné — 9 produits légitimes restaurés** que l'ancien filtre cachait.
- **D — core (9)** : bandit_save atomique ; playbooks/blackboard retry 3×+WARN ; **placeholders `<… from intel>` morts** (gates endpoint + dérivation réelle d'URL) ; events.jsonl rotation 5MB + save coalesced 2s ; trajectory rotation 30MB + tail-2000 ; `_slug("..")`→target ; planner tiers scout→strike ; state.py dup supprimé (forme curated vérifiée contre server.py:348) ; INTENTS mort supprimé.

### Vague résiduelle — ENI (21 fixes, rattrapage de mon découpage de specs)
| Fix | Effet |
|---|---|
| R3-32 coerce | booléens réversibles — `execute="confirm"` ne s'inverse plus silencieusement en False |
| R3-11 scope/ROE fail-safe | dernier-état-bon : yaml corrompu en cours de mission ≠ ingouvernable |
| R3-12 re-scope | args re-vérifiés avant CHAQUE run de la boucle heal — le swap d'URL du healer ne saute plus G13 |
| R3-19/R3-33 discover | échecs d'import traqués + annoncés dans UNKNOWN_TOOL |
| R3-24/R3-34 emitter | thread-local seul — plus d'events cross-mission ; batch capture/repasse le sien |
| F-3 sys.path | dédup — plus de path qui gonfle à chaque appel |
| R2-9 pacers | éviction LRU des dormants >1h — le process long-vécu ne fuit plus |
| R5-14 seeds corpus | guard de forme — un dict en vals[0] ne crashe plus le fuzzer |
| R3-14/R3-29 forge desc | json.dumps-échappé dans le docstring — plus d'exécution module-level via un desc |
| R3-17 forge salvage | def indenté détecté ; salvage qui aplatit le control flow REFUSÉ |
| R4-18 /tool deadline | 1800s dur — un nmap sur host mort ne lie plus un worker à vie (504 lisible) |
| R4-13/15 races | garde lue-seule sur /mission, approve-strike ET WS start_mission — le perdant reçoit son 409 au lieu d'un 200 fantôme ; le check-and-set atomique reste LE seul claim (dans _run_mission_streaming) |
| R4-16 chat | lock non-bloquant un-turn-à-la-ffois (jamais d'acquire bloquant dans la boucle asyncio) |
| R4-2 injection deux-hop | blocs `═══ UNTRUSTED ═══` autour de prior_intel (rapport précédent + docs) — les données cible ne sont plus des directives au niveau stratège ; le canal chat du commandant reste TRUSTED |

## Réconciliation des tests (aucun affaiblissement)
- **test_mathcore** : ré-ancré au contrat Vegas réel (inc = 0.05/rtt borné [0.2, 2.0], pénalité 403 moitié) — l'ancien `+0.2` fixe était périmé.
- **test_attack_graph** : « chains emerge » vérifie la famille chaînée (probe→exploit) au lieu d'une liste figée d'outils.
- **test_healer** : scan nuclei live = opt-in `VF_LIVE_NET=1` ; le parse strip le suffixe `→ NEXT:` des chain hints (feature plateforme, pas un bug).
- **test_tokenize** : marqueur structurel suivi (gate passe par `_load_scope_cached`, appel `= _scope_check(args`).

## Différé par design (record)
R3-18 (marker auto-import forge — design) · R4-5 (WS strict Origin + token hors query — coordination frontend) · R4-9 (abort coopératif — TODO en place) · R5-1 (sandbox réel — décision VM/container) · F-2 (scope port-level — le modèle est host-level) · R1-8 (budget agent —hors périmètre).

## Reste du master-plan (backlog)
Sessions 2-4 : bootstrap_manifest · env_bootstrap · forge dedupe/quarantine + siwx v2-v8 archival (au restart naturel) · field journal · war-room panel · cli_ingestion doctrine · campagne Juice Shop · metrics.
