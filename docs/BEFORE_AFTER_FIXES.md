# AVANT → APRÈS : ce que changent les corrections, scénario par scénario

*Complément narratif de `CODE_REVIEW.md` — chaque scénario = ce qui arrive AUJOURD'HUI vs ce qui arrivera APRÈS le fix. Aucun fix appliqué tant que l'opérateur ne dit pas « go ».*

---

## 🔴 VERROU 1 — ROE : de « advisory » à « réel » (F-1 + R3-15 + R3-13, ~1h)

### AVANT
```
engagement.yaml:  do_not_exploit: true   (l'opérateur croit : recon only)
```
| Action de l'agente | Résultat aujourd'hui |
|---|---|
| `httpx_sweep(target)` — danger="active" | **S'EXÉCUTE** — "active" n'est pas dans la blocklist `("loud","danger","strike")` |
| `sqli_tamper_chain(...)`, `fuzz_attack_surface(...)`, `lfi_file_read(...)` — "careful"/"active" | **S'EXÉCUTENT** — 24 outils offensifs passent à travers |
| forge : le LLM crée `forged_strike9(danger="safe")` | **S'ENREGISTRE en "safe"** et s'exécute — l'agente a frappé sans jamais toucher un outil bloqué |
| `ip_intel(ip_or_host="8.8.8.8")` | **Passe G13 sans validation** — la regex d'extraction exige un TLD alphabétique, une IP nue n'est jamais vue |

### APRÈS
```
TOOL ERROR [ROE_BLOCKED]: 'httpx_sweep' est en exploitation (danger="active"),
bloqué par do_not_exploit — enregistre le finding et continue le recon.
TOOL ERROR [ROE_BLOCKED]: 'forged_strike9' (forgé ≥ active) bloqué.
TOOL ERROR [SCOPE_BLOCKED]: la cible '8.8.8.8' est hors périmètre.
```

### IMPACT
- **Recon-only devient VRAI** : l'agente cartographie, énumère, enregistre des candidate-findings — et ne frappe pas. L'opérateur garde la décision de frappe.
- L'inversion fail-closed (tout sauf "safe" est bloqué) rend **impossible** le bug de vocabulaire : un tool futur avec un label inconnu sera bloqué, pas passé.
- **Aucune capacité n'est retirée** : en mission offensive normale (do_not_exploit: false), tout l'arsenal frappe comme avant. La garantie déclarée devient réelle, c'est tout.

---

## 🧠 VERROU 3 — Le cerveau cesse de tricher (R2-1 + R2-2, 2 patches <10 lignes)

### R2-1 backprop MCTS
**AVANT** — la valeur mesurée depuis la RACINE est ajoutée à chaque nœud :
```
Chaîne A: web_fingerprint(3.0) → sqli_union_dump(1.0)   → vraie valeur du nœud 2 : 1.0
Chaîne B: web_fingerprint(3.0) → sqli_probe(2.5)        → vraie valeur du nœud 2 : 2.5
```
mais les deux nœuds 2 reçoivent `W += G` avec G ≈ `3.0 + γ·suite` — **le nœud 2 de la chaîne A hérite du 3.0 de son ancêtre et paraît aussi bon que B**. Le planner sur-commite aux chaînes dont l'ouverture a brillé. `root.N += 1` double-compte en plus.

**APRÈS** — chaque nœud reçoit `son` retour escompté (G_node = v + γ·G_enfant) : le Q reflète la qualité propre de la suite. Le planner choisit des chaînes complètes de valeur.

**IMPACT** : moins de missions qui s'enlisent après un bon début ; les forks de décision (prober avant de dumper, pivoter plutôt qu'insister) deviennent réellement comparés. Le MCTS fait enfin ce que son docstring promet.

### R2-2 Pacer.wait()
**AVANT** — 5 workers de `batch_execute` sur un host réglé à 30 req/min, bucket vide :
```
t=0    5 threads → wait() → tous calculent le même need → dorment pareil
t=need 1 thread prend le token ; 4 trouvent _tokens < 1.0 → return SANS consommer
t=need les 4 autres PARTENT IMMÉDIATEMENT → burst 5× → 429 / ban / WAF trip
```
**APRÈS** — `while self._tokens < 1.0: sleep(...)` : chaque worker ne repart qu'après avoir DÉCRÉMENTÉ un token.

**IMPACT** : le bucket anti-throttle tient sous batch_execute et les race tools — exactement les moments pour lesquels il a été écrit. Côté cible : plus de clump visible ; côté ban : le pattern « burst puis AIMD punitif » disparaît.

---

## 🔐 VAULT & CONTAINMENT (R1-3, R5-2, R4-4, R5-5, R3-37)

### R1-3 — reset_vault() par mission
**AVANT** : mission A obtient `admin:S3cret!` → token `[CRED-7]`. La mission A finit. Mission B (le process tourne toujours) lit un output contenant `[CRED-7]` → l'outil unmask rend **`S3cret!`** — un secret de la mission précédente traverse dans la mission B.
**APRÈS** : vault vidé au `Agent.run` — un token inconnu reste un token.
**IMPACT** : zéro cross-mission bleed. Les secrets vivent le temps de leur mission, point.

### R5-2 — wordlist containment (fuzz_engine)
**AVANT** : `wordlist="../../../../Users/x/notes.txt"` → `normpath` COLLAPSE les `..` et ouvre le fichier → le contenu devient les munitions du fuzz → la fuite finit dans `reports/`.
**APRÈS** : `realpath` doit rester sous `data/wordlists/` sinon `TOOL ERROR [ARGS]`.
**IMPACT** : le paramètre cesse d'être un read-anywhere ; même fix appliqué aux 3 gaps fichiers (R4-4 drive-switch, R5-5 tg_osint) via un helper partagé.

### R3-37 — cn_fingerprint op=list
**AVANT** : `tongda_oa_2017` (id fini par `_7`) est invisible au browse — mais `op=creds tongda_oa_2017` fonctionne. L'agente ne peut PAS découvrir ce qu'elle peut utiliser.
**APRÈS** : les ids renommés par dédup sont trackés explicitement — tout produit reste browsable.
**IMPACT** : l'arsenal CN redevient complet sur EXACTEMENT les stacks qu'il cible ( TongDaOA, 致远, année-nommées — le cœur des cibles gouv/entreprise chinoises).

---

## ⏱️ TRANSPORT : survie et honnêteté (R3-25, R3-26, R3-31, R5-17, E-1, R3-22)

### R3-25 — Retry-After borné
**AVANT** : un middlebox répond `429 Retry-After: 999999` → `time.sleep(999999)` → **le tool call est garé 11,5 jours**. La mission devient un zombie silencieux ; l'opérateur doit tuer le process. **Un paquet suffit.**
**APRÈS** : `min(float(ra), 30.0)` + budget wall-clock sur fetch().
**IMPACT** : la mission ne peut plus être tuée par la cible en un paquet. Le pire cas devient 30s, jamais 11 jours.

### R3-26 — race du resolver
**AVANT** : premier fetch d'une mission batchée — 5 threads entrent ensemble dans `install_resolver()` ; le second sauve la fonction DÉJÀ patchée comme origine → **récursion infinie sur tout getaddrinfo → tout le transport meurt (DoH inclus) jusqu'au restart du backend.**
**APRÈS** : save+patch sous `_lock`.
**IMPACT** : le transport survit à sa propre mise en route concurrente. (Le patch est au boot du premier fetch de CHAQUE process — la course est certaine si batch est le premier appel.)

### R3-31 — crédentials sur redirect
**AVANT** : `in-scope.com` 302 vers `attacker.io` → fetch repart avec `Authorization: Bearer eyJ...` et le Cookie de campagne **vers l'attaquant**.
**APRÈS** : host différent → Authorization/Cookie/apikey strippées.
**IMPACT** : les tokens de campagne ne pivotent plus hors du périmètre via une simple redirection. (Se compose avec R3-16 : le host de destination sera aussi validé contre le scope.)

### R5-17 — la flotte monte dans le transport gouverné
**AVANT** : 12 modules (supabase_exfil, wayback_miner, sqli_test, waf_detect...) font du `urllib` nu — pas de pacing adaptatif, pas de proxy, pas de cache. 55 requêtes séquentielles à 0.15s fixe = signature de bot.
**APRÈS** : leurs helpers pointent sur `paced_send` → pacing adaptatif + proxy chain + cache pour tous.
**IMPACT** : plus de module indiscipliné qui fait bannir l'IP de l'opérateur pendant que le reste de la flotte se comporte bien. L'anonymat et le cache deviennent des propriétés de la plateforme, pas de 2/3 des modules.

---

## 🌐 FRONTIÈRE BROWSER & BACKEND (R4-1, R4-14, R4-12, R4-17, R4-20)

### R4-1 — middleware Origin
**AVANT** : l'opérateur ouvre un writeup contenant une page hostile. Cette page exécute :
```js
fetch('http://127.0.0.1:8000/tool', {method:'POST', mode:'no-cors',
  body: JSON.stringify({tool:'port_scan_sync', args:{...}})})
```
→ pas de preflight (Content-Type text/plain), CORS ne bloque pas l'ÉMISSION → **la requête exécute l'un des 104 tools, ou lance /mission, ou vide /admin/fresh**. Le token est vide par défaut : le middleware ne voit rien.
**APRÈS** : toute requête mutante avec un `Origin` non-allowlisté → 403 immédiat.
**IMPACT** : le browser de l'opérateur cesse d'être un canal de commande. La posture « localhost-only » devient du code, pas une convention.

### R4-14 — le chat ne lance plus de campagnes
**AVANT** : mission finie ; l'opérateur tape dans le war-room « ok continue sur les endpoints API, surveille les 403 » → inbox inexistante → **le message DEVIENT la chaîne mission** et une nouvelle offensive part, sans target gating, sans plan, sans confirmation.
**APRÈS** : `404 — mission no longer live` ; la continuation devient explicite.
**IMPACT** : un message d'ops ne déclenche plus une campagne. Le chat redevient du chat.

### R4-17 — la console ne gèle plus
**AVANT** : laptop en veille pendant une campagne → socket half-open → `await send_text` bloque **toutes** les broadcasts (tool_start/result, events de mission) → consoles mortes pour toute la plateforme pendant que l'agente frappe à l'aveugle.
**APRÈS** : `wait_for(send, 5s)` + drop des morts.
**IMPACT** : la visibilité temps réel survit aux tabs endormis. L'opérateur voit ce que l'agente fait, en campagne comme au repos.

### R4-20 — purge exacte
**AVANT** : `/admin/fresh(target="test.com")` efface aussi `attest.com.json`, `latest.com.json` — **intel de campagne irrécupérable**.
**APRÈS** : match exact slugifié.
**IMPACT** : purger un cible ne purge plus ses voisines de nom.

---

## 🧭 SELFTEST & PREUVES (R3-4, R3-1/2/3, R1-1, R1-8)

- **R3-4** : AVANT, une clé NVD expirée = rapport boot **vert** (un `{"error":...}` compte passed). APRÈS = rouge honnête. *Le garde-fou cesse de mentir.*
- **R3-1** : AVANT, suivre les hints peut ping-ponger `upload_webshell ↔ shell_exec` sans fin. APRÈS : cycles cassés + acyclicité assertée à l'import.
- **R3-2/3** : AVANT, un verdict trop gros est coupé en plein token JSON → un exploit confirmé lu comme un malfunction. APRÈS : verdict toujours parseable, branchement `exploitable` fiable.
- **R1-1** : AVANT, les triggers CJK des skills zh ne matchent jamais (le `\b` unicode) — le routage CN est mort. APRÈS : lookarounds → `越权` matche, les skills zh s'activent.
- **R1-8** : AVANT, une mission zh passe la fenêtre du provider (compte CJK ÷4) → HTTP 400 camouflé en « LLM unavailable ». APRÈS : estimateur CJK-aware → diet avant la fenêtre.

---

## ⚖️ CE QUI NE CHANGE PAS — et c'est voulu

1. **La couche d'acceptation reste intouchable** (annexe CODE_REVIEW, décision opérateur) — aucun fix ne la touche.
2. **Aucun outil n'est retiré** — l'arsenal complet reste appelable en mission offensive normale. On ne rétrécit pas la plateforme ; on rend les garanties déclarées (`do_not_exploit`, `in_scope`, le bucket anti-ban, la selftest) **vraies**.
3. **Les seuils restent tes décisions** — allow_private_ranges, la limite du Retry-After, les modes live de la selftest : tout est paramétrable, rien n'est gravé.
4. **Zéro redémarrage forcé** — tous les fixes s'arment au prochain restart naturel, le backend de campagne n'est jamais touché.

## 📊 La même plateforme, mesurée

| Métrique | AVANT | APRÈS vague 1 (rangs 1-5, ~1h) | APRÈS vague 2 (rangs 6-12 + addenda) |
|---|---|---|---|
| `do_not_exploit=true` bloque réellement | 0/24 offensifs passent | **24/24 bloqués** (+ forges + IPs) | idem |
| Anti-ban sous batch_execute (bucket à 5 workers) | burst 5× → 429 | **débit nominal tenu** | + 12 modules migrent vers paced_send |
| Bleed de secrets cross-missions | possible | **impossible** | idem |
| Read-anywhere via args LLM | 3 vectors (wordlist, drive-switch, tg) | **fermés** | + helper partagé _contained partout |
| Mission tuée par un paquet (Retry-After) | 11,5 jours possibles | **≤30s** | + budget wall-clock global |
| Transport meurt à la course du resolver | possible au 1er batch | **impossible** | idem |
| Browser → 104 tools (onglet hostile) | passe | **403** | + WS Origin strict + bind guard |
| Chat → campagne spontanée | possible | **404** | + acquire unique aux 4 chemins |
| Console vivante pendant une campagne | gèle sur 1 socket mort | **survit** | idem |
| Routage skills chinois | mort (`\b` CJK) | **vivant** | + budget CJK correct |
| Verdict JSON parseable | 1 payload >18k le casse | **toujours valide** | idem |

**En une phrase** : avant, les garanties de la plateforme sont des promesses qui tiennent tant que rien ne pousse dessus ; après, ce sont des mécanismes qui tiennent exactement quand quelque chose pousse dessus — batch, redirect, onglet hostile, cible bavarde, message envoyé trop tard.
