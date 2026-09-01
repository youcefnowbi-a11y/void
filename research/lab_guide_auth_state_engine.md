# Guide de laboratoire — auth_state_engine v0

> **VOIDFORGE / Offensive Security Research Division** · Compagnon exécutable du `dossier_3_auth_state_machines.md`
> Version 0.1.0 · Python ≥ 3.10 · stdlib uniquement · Aucun trafic réseau émis par l'outil
> ⚠️ Périmètre : environnements de laboratoire dont vous détenez l'autorisation écrite. L'outil analyse des traces ; il ne pilote aucune attaque active.

---

## 1. Démarrage rapide

```powershell
cd C:\Users\youcef cheriet\D\VOIDFORGE\research
python auth_state_engine_v0.py            # démo déterministe intégrée (traces synthétiques)
python auth_state_engine_v0.py --out verdict_demo.json --pretty
```

Sortie attendue (résumé) : **7 findings** — `no_skip ×3` (critical), `no_replay ×1` (high),
`issuer_confinement ×2` (critical), `binding_preservation ×1` (high) — plus 3 checks d'entropie
(64.0 / 131.0 / 19.9 bits), 2 bindings JWT audités, 1 plan de course. Le fichier
[`verdict_demo.json`](verdict_demo.json) est l'exemple de référence du contrat §5.4 du dossier.

## 2. Ce que v0 implémente (vs pipeline §5 du dossier)

| Étape pipeline | v0 | Statut |
|---|---|---|
| (a) Instrumentation du flux | capture externe (mitmproxy) → fichier traces JSON | ✅ fourni par le guide §4 |
| (b) Inférence de machine | carte de transitions **manuelle** + traces annotées d'états | 🟡 v1 = L* via AALpy |
| (c) Property checking | moniteurs runtime `no_skip`, `no_replay`, `issuer_confinement` | ✅ implémenté |
| (d) Algèbre des tokens | audit JWT (alg/kid/jku/x5u/jwk), extraction τ, contrôle `aud` croisé | ✅ implémenté |
| (e) Course sur étapes one-shot | **plan** uniquement (endpoints, technique, modèle P) | 🟡 exécution = Turbo Intruder |
| (f) `verdict()` JSON | contrat §5.4 complet | ✅ implémenté |

## 3. Schéma des traces (format d'entrée)

```json
{
  "traces": [
    {
      "trace_id": "t1-victim-mfa-skip",
      "events": [
        {"event": "creds_submit",  "actor": "victim",  "params": {"user": "V"},
         "state": "s1_creds_ok",   "outcome": "200"},
        {"event": "session_establish", "actor": "victim", "params": {},
         "state": "s3_authenticated",  "outcome": "200"}
      ]
    }
  ]
}
```

Conventions :
- `event` — symbole de l'alphabet (§2.1 du dossier) : `creds_submit`, `otp_submit`, `magic_verify`,
  `code_consume`, `token_exchange`, `callback`, `token_present`, `resource_access`, `session_establish`, `logout`.
- `state` — marqueur d'état serveur observé (message d'erreur discriminant, page, header `Location`,
  présence de session). C'est l'abstraction qui rend l'automate fini.
- `outcome` — code HTTP. **2xx et 3xx = succès d'étape** (une redirection OAuth est un succès).
- `actor` — identité émettrice (`victim`, `attacker`, `attacker2`, `tenant1`…). Les croisements V↔A
  sont la matière première des findings.
- Événements one-shot : porter `token_id` dans `params` (le moniteur `no_replay` compte les
  consommations réussies par identité de token).

## 4. Capturer les traces avec mitmproxy

Addon minimal (enregistrer `auth_tracer.py`, lancer `mitmdump -s auth_tracer.py`) :

```python
import json, time
from urllib.parse import urlparse

AUTH_MARKERS = ("/auth", "/login", "/oauth", "/cb/", "/callback", "/saml", "/mfa", "/token", "/verify")
STATE_MARKERS = {"authenticated": "s3_authenticated", "mfa": "s2_mfa_pending",
                 "code": "s4_code_exchanged", "consent": "s1_creds_ok"}

def response(flow):
    path = flow.request.path
    if not any(m in path for m in AUTH_MARKERS):
        return
    event = infer_symbol(flow)                 # votre mapping (stable !) requête -> symbole
    state = next((v for k, v in STATE_MARKERS.items() if k in (flow.response.text or "").lower()
                  or k in (flow.response.headers.get("location", "").lower())), None)
    ev = {"event": event, "actor": current_actor(), "params": extract_params(flow),
          "state": state, "outcome": str(flow.response.status_code), "ts": time.time()}
    TRACE["events"].append(ev)
    with open("traces.json", "w", encoding="utf-8") as fh:   # flush continu
        json.dump(TRACE, fh, ensure_ascii=False, indent=2)
```

Règles d'or : (1) le mapping requête→symbole doit être **déterministe** — un symbole instable
détruit l'inférence ; (2) journaliser aussi les 3xx et les échecs (`outcome` le reflète) ;
(3) un fichier par session d'acteur, fusionner ensuite dans le schéma §3.

## 5. Matrice d'identités et croisements d'étapes

Minimum vital : `V` (victime), `A` (attaquant), `A'` (second compte attaquant), et en multi-tenant
`T1`/`T2` (IdP distincts si possible). Croisements à exécuter, un trace par ligne :

| # | Départ | Fin | Ce que ça détecte |
|---|---|---|---|
| 1 | V : flux complet honnête | — | baseline (aucun finding attendu) |
| 2 | V jusqu'à `otp_pending`, puis A : `session_establish` | session partagée ? | step-up skip (§1.9) |
| 3 | V : `code=α` émis, A : `code_consume α` ×2 concurrent | double 200 ? | no-replay / race (§1.9, §6.5) |
| 4 | A (IdP perso) : `callback?iss=<legit>` | échange accepté ? | mix-up (§1.4) |
| 5 | `callback` sans `iss` | accepté ? | mix-up (RFC 9207 non implémenté) |
| 6 | token de V (`aud=api`) présenté à `/api/admin` | 200 ? | binding-preservation (§1.8) |
| 7 | T1 : assertion/token → route du tenant T2 | accepté ? | IDP/tenant confusion (§1.5) |
| 8 | V : logout, puis refresh du token volé | 200 ? | invalidation incomplète (§1.10) |

## 6. Lancer l'analyse

```powershell
python auth_state_engine_v0.py --traces traces.json --flow oauth2 --out verdict.json --pretty
```

- `--flow` ne change pas encore la spécification (v0 : une spec MFA/OIDC générique intégrée) —
  éditer `run_engine()` (`protected`, `required`, `proof_events`, `expected_iss`, `endpoint_aud`)
  pour coller au flux cible. C'est voulu en v0 : la spec manuelle documentée vaut mieux qu'une
  inférence silencieuse et fausse.
- Ajuster les seuils d'entropie par appel `check_entropy(...)` (128 bits `state`, 160 bits `code`).

## 7. Interpréter le verdict

| Template | Classe dossier | Sévérité | Action de confirmation |
|---|---|---|---|
| `no_skip` | §1.9 (MFA bypass), §1.7 middleware skip | critical | rejouer le chemin en 3 requêtes ; vérifier si l'API finale accepte le token intermédiaire |
| `no_replay` | §1.1 code, §1.11 magic-link, OTP race | high → critical si cross-actor | course réelle via Turbo Intruder (plan §race_plan) ; mesurer le taux de double-usage |
| `issuer_confinement` | §1.4 mix-up, §1.5 IDP confusion | critical | forger callback avec `iss` légitime + code de l'IdP attaquant ; vérifier l'échange |
| `binding_preservation` | §1.8 aud/sub/epoch | high | mapper tous les endpoints × tous les tokens (matrice complète, pas un échantillon) |
| `entropy FAIL` | §1.3 state CSRF, §1.1 code | contextuel | collecter N secrets, tester PRNG (linéarité, corrélation temporelle) — voir §6.1/6.2 dossier |
| flags JWT (`ALG_CONFUSION`, `KID_INJECTION`, `JKU_REMOTE_KEY`) | §1.7 | à confirmer | jwt_tool `-X a/-X k`, tenter la vérification croisée ; vérifier si `jku` est résolu dynamiquement |

Chaque finding embarque `property` (la formule LTL violée), `trace`, `evidence` — c'est le
contre-exemple du dossier §2 : une **hypothèse de bug** à confirmer concrètement, pas une preuve.

## 8. Limites v0 & feuille de route

1. **v1 — inférence L*** : brancher AALpy (`github.com/DES-Lab/AALpy`) : MQ = rejeux HTTP,
   EQ = conformance testing (W-method) ; l'abstraction alphabétique du §3 devient l'input de L*.
2. **v1 — exécution des courses** : l'outil reste le plan ; le single-packet attack (HTTP/2,
   N streams, un paquet) s'exécute dans Turbo Intruder avec un script Python embarqué.
3. **v2 — états symboliques** : anti-unification des états concrets + gardes SMT (Z3) selon §2.5
   du dossier ; le moniteur no-skip gagne la gestion de `fresh()` (expirations réelles).
4. **SAML** : v0 n'audite pas le SAML — passer les POST `/acs` à SAML Raider (patterns XSW) et
   réinjecter le verdict ici (`event: "saml_consume"`, `outcome`).
5. **Multi-tenant** : étendre `expected_iss` en fonction `resolve(tenant) → issuer` et pincer
   la résolution (email de domaine, route) — cf. §1.5 du dossier.

## 9. Checklist de sortie de lab

- [ ] `traces.json` (schéma §3) + journal brut mitmproxy conservés
- [ ] `verdict.json` produit, tous les findings re-joués à la main (reproductibilité)
- [ ] Chaque finding : screenshot + requête de reproduction + mapping vers la classe §1 du dossier
- [ ] Entropie : ≥ 3 échantillons par type de secret collectés avant de conclure
- [ ] Aucun test hors périmètre autorisé ; traces anonymisées avant archivage
