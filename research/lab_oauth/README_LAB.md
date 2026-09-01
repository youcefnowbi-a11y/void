# LAB OAuth — les défauts plantés (checklist d'acceptation)

Cible de validation pour le futur `auth_state_engine` (voir
`04_plan_implementation.md` §6 : « un run complet sur cible-lab produit UN
finding FORTE avec la preuve complète »).

Lancer : `python research/lab_oauth/lab_server.py` → http://127.0.0.1:9443

| # | Défaut planté | Classe (dossier_3) | Ce que le moteur DOIT détecter |
|---|---|---|---|
| D1 | PKCE jamais exigé — `code_verifier` ignoré | code interception | propriété binding : code échangeable sans preuve de possession |
| D2 | `state` renvoyé tel quel, jamais comparé à une session | CSRF de flux | no-binding : state non lié — H vérifiée aussi (libre) |
| D3 | code d'autorisation **réutilisable** | no-replay violation | deux POST /token avec le même code → 2 tokens |
| D4 | `redirect_uri` validé par **préfixe** | redirect validation flaw | `https://app.example/cb.evil.example` passe le filtre |
| D5 | code à 32 bits (`token_hex(4)`) | entropy-floor | H = 32 bits << 160 — force brute triviale |
| D6 | `/api/user` n'a aucune vérification iss/aud | mix-up / audience confusion | token de issuer-b accepté par le RS de issuer-a |

## Scénarios PoC attendus du moteur

1. **Replay (D3)** : GET `/authA/authorize?...&redirect_uri=https://app.example/cb&state=xyz`
   → code ; POST `/token?code=C` ×2 → deux access_tokens différents, même code.
2. **Mix-up (D6)** : code issu de `/authB` échangé, token présenté à
   `/api/user` — accepté alors que le RS « appartient » à issuer-a.
3. **Redirect prefix (D4)** : `redirect_uri=https://app.example/cb.evil.example`
   → 302 avec code (le code fuit vers evil).
4. **Entropy (D5)** : H(code) calculée sur 100 codes = 32.0 bits < 160.

Chaque détection = un finding FORTE avec le PoC HTTP exact en evidence.
