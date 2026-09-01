# DOSSIER 3 — Complex Multi-Step Auth Flow Bugs via Session-Aware State Machines

> **VOIDFORGE / Offensive Security Research Division**
> Classification: internal research · Status: final · Version: 1.0 · Date: 2026-08-30
> Scope: OAuth 2.0 / OIDC, SSO/SAML, JWT chains, magic-link/passwordless, MFA/step-up, multi-tenant session isolation
> Method: research + writing only. All CVEs below were re-validated against NVD and all cited URLs were live-checked at time of writing.

---

## 1. TAXONOMIE DES BUGS DE FLOW

Un bug de "flow" n'est pas une injection classique : c'est une **violation d'ordre, d'exclusivité ou de liaison** dans une séquence d'échanges répartie entre client, serveur et fournisseur d'identité. Chaque classe ci-dessous est décrite par : mécanique exacte, cause racine (root cause), et cas réel documenté.

### 1.1 Interception du code d'autorisation (PKCE manquant)

**Mécanique.** Dans le `authorization_code` flow, le serveur renvoie le client vers `redirect_uri?code=XXXX`. Si la valeur du `code` traverse un canal observable — URL scheme personnalisé sur mobile (`myapp://callback?code=...`), referrer HTTP, historique navigateur, logs serveur, extension malveillante — l'attaquant récupère un code encore valide et l'échange contre des tokens. Sans PKCE (RFC 7636), l'échange n'exige aucun preuve de possession : n'importe qui avec le `code` peut le consommer. Avec PKCE, l'échange exige `code_verifier` dont `S256(code_verifier) == code_challenge` lié au `code` — le code volé devient inutilisable.

**Cause racine.** `response_type=code` sans `code_challenge`, ou PKCE optionnel (le serveur accepte l'échange sans `code_verifier` même si un challenge a été émis — un *PKCE downgrade* classique testé en supprimant simplement le paramètre à l'étape 2).

**Cas réel / état de l'art.** La classe entière est suffisamment dominante pour que RFC 9700 (*OAuth 2.0 Security Best Current Practice*, janvier 2025) rende PKCE **obligatoire** pour tous les clients, confidents comme publics, et déprécie l'implicit flow. Les labs OAuth du Web Security Academy de PortSwigger ([portswigger.net/web-security/oauth](https://portswigger.net/web-security/oauth)) codifient l'attaque : dérober le `code` via referrer ou via un `redirect_uri` contrôlé, puis échanger le code avant la victime — course d'exclusivité pure (voir §1.9 et §6.5).

### 1.2 Validation défaillante de `redirect_uri` (exact-match vs préfixe/wildcard)

**Mécanique.** Le serveur d'autorisation doit comparer le `redirect_uri` reçu à celui enregistré **caractère par caractère** (RFC 6749 §3.1.2.3 : *simple string comparison*). Les vulnérabilités apparaissent quand le serveur implémente une comparaison de préfixe, une glob trop large (`https://app.example.com/*` où `*` franchit les `/`), une normalisation différente de celle du navigateur (double slashes, `//\`, encodage `%2f`, sous-domaine `.attacker.com` suffixé à un domaine légitime), ou ouvre la porte aux *open redirectors* internes. L'attaquant enregistre alors `https://app.example.com/oauth/redirect?next=https://evil.tld/` et le `code` (ou le token de l'implicit flow) atterrit chez lui.

**Cause racine.** Matching par `startsWith()` ou glob au lieu d'un ensemble exact ; confiance excessive dans les *path tricks* (dot-segments, `;` parameters, fragmentation).

**Cas réel.** **CVE-2024-1132** (Red Hat Keycloak) — validation insuffisante des URLs de redirection, permettant de construire une redirection malveillante utilisable en phishing avec flux OAuth légitime (validé NVD). Le writeup historique du domaine « wildcard redirect_uri sur GitHub OAuth apps → vol de code en masse » (disclosure publique 2020, auteur William Woodruff) reste l'exemple canonique : un seul wildcard d'app tierce suffisait à rediriger les codes de n'importe quelle application authentifiée vers un domaine contrôlé. Le correctif industriel moderne est l'exact-match strict par défaut et l'usage systématique du paramètre `iss` (RFC 9207).

### 1.3 `state` parameter CSRF (exigences d'entropie)

**Mécanique.** Sans `state` lié à la session navigateur, l'attaquant peut **injecter** un code ou des tokens *à* la victime : l'attaque « OAuth CSRF / account bind » force la session victime à se lier au compte de l'attaquant (la victime se connecte avec le compte IdP de l'attaquant sans s'en apercevoir — session fixation applicative), ou exécute un login CSRF complet.

**Cause racine.** (a) `state` absent ; (b) `state` présent mais prévisible (timestamp, UUIDv1, séquentiel) ; (c) `state` présent mais **non vérifié** côté callback — le cas le plus fréquent en bug bounty : le serveur accepte le callback sans `state` ou avec un `state` quelconque.

**Cause racine / exigence.** RFC 9700 et l'OWASP OAuth2 Cheat Sheet ([cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html)) exigent un `state` à entropie cryptographique : **≥ 128 bits** d'entropie réelle (voir §6.1) et vérification stricte de l'égalité `state(reçu) == state(émis)`, one-time, avec invalidation à l'usage. RFC 9700 recommande en complément le mode `nonce` OIDC pour la réidentification.

**Cas réel.** Classe omniprésente sur HackerOne ; le pattern typique accepté en bounty : « lack of state/nonce validation → forced account binding → full account takeover via email recovery ». La défense formelle est une propriété de *binding-preservation* (§2.3).

### 1.4 Attaque mix-up (confusion d'émetteur / issuer confusion)

**Mécanique.** Un client (RP) configuré pour plusieurs IdPs (ex : `google`, `okta`, `auth0` en tant qu'upstreams) choisit l'endpoint de token selon un paramètre visible de l'URL de callback (`?iss=`, `?idp=`, ou la route `/callback/google`). L'attaquant, enregistré comme IdP légitime chez le même RP, dirige la victime vers l'autorisation **de l'attaquant** mais avec un callback faisant référence à l'IdP légitime : le RP échange le code **auprès de l'IdP de l'attaquant** ou accepte des tokens émis par lui tout en les attribuant à l'identité légitime → **hijack de compte sans interaction de la victime**.

**Cause racine.** Absence de vérification `iss` dans la réponse d'autorisation ; appariement callback→IdP par un paramètre falsifiable. Documentée par Arbuthnot & Jones (2019) et analysée en profondeur par Daniel Fett ([danielfett.de/2020/05/04/mix-up-revisited](https://danielfett.de/2020/05/04/mix-up-revisited/)).

**Mitigation de référence.** RFC 9207 : l'IdP DOIT inclure `iss=<issuer>` dans la réponse d'autorisation et le RP DOIT la vérifier ; RFC 9700 la rend obligatoire. Variantes 2024-2026 : mix-up par confusion de *client_id* dans les portails multi-IdP, et mix-up par *route inference* (le callback `/cb/<tenant>` où `<tenant>` choisit le stockage de clés). Test pratique : enregistrer son propre IdP (Auth0 free tier, Keycloak local), émettre un code, forger le callback avec `iss` de la cible, observer si le RP l'accepte.

### 1.5 IDP confusion multi-tenant (tenant isolation via upstream identity)

**Mécanique.** Architecture SaaS multi-tenant : chaque tenant configure son propre IdP/AC. Le moteur d'authentification résout « quel tenant, quel IdP » depuis des entrées faibles : le domaine de l'email (email-aliasing, sous-domaines), l'ACRS/whitelist d'AC en SAML, le paramètre de route. Deux effets : (a) **tenant cross-login** — un compte d'un tenant A s'authentifie dans le tenant B parce que la résolution du tenant accepte l'assertion d'un IdP non configuré pour B ; (b) **verifier confusion** — l'assertion est validée avec le mauvais certificat/métadonnées (signature vérifiée mais contre le trousseau d'un autre tenant).

**Cause racine.** La fonction de résolution `resolve(tenant, identity) → {expected_issuer, keyset}` n'est pas injective ou accepte des entrées attaquant-contrôlées (email, route, param).

**Cas réel.** La recherche 2026 de William Woodruff sur les **audience constraints OIDC de GitHub Actions** ([blog.yossarian.net/2026/08/10/github-actions-needs-oidc-audience-constraints](https://blog.yossarian.net/2026/08/10/github-actions-needs-oidc-audience-constraints)) documente la même famille à l'échelle CI/CD : des tokens OIDC émis pour un contexte peuvent être acceptés par des fédérations qui ne contraignent pas assez `aud`/`sub` — confusion d'émetteur et de liaison entre « arènes » cloisonnées. C'est le pattern multi-tenant généralisé : *le cloisonnement n'est réel que si la vérification portent les quatre composantes de la liaison τ* (§2.2).

### 1.6 SAML signature wrapping (XSW)

**Mécanique.** L'assertion SAML est signée (XML-DSig, enveloped). La signature ne couvre qu'un sous-arbre identifié par un `Reference URI="#_id"`. L'attaquant **duplique** un élément : il place une assertion non signée contrôlée à un emplacement que le parser du SP lit en priorité (extension du `Subject`, `Extensions`, nouvelle assertion en tête), tout en préservant l'assertion signée originale comme « couverture » de la signature. Le SP valide la signature (elle couvre bien l'assertion originale), mais **extrait l'identité de l'élément injecté**. Variantes : Comment injection (Comment injection attack), XSLT, `x509` swap.

**Cause racine.** Validation et interprétation effectuées par **deux parsers différents** (differential parsing) ou extraction de l'assertion « première / par position » plutôt que par la référence signée. L'attaque exige un IdP/SP où l'on peut s'inscrire (IdP personnel) et rejouer une réponse légitime interceptée.

**Cas réels (2022-2024).**
- **CVE-2024-45409** — Ruby-SAML (gem utilisée par GitLab) : vérification de signature incorrecte permettant signature wrapping / bypass d'authentification SAML (validé NVD) ; c'est la chaîne utilisée pour les prises de contrôle GitLab via SSO SAML en 2024.
- **CVE-2022-47966** — Zoho ManageEngine : RCE pré-auth par parsing SAML vulnérable (Apache Santuario `xmlsec` ancien), la signature est validée mais le traitement XML induit une exécution.
- L'écosystème `SAML-Toolkits/python-saml` ([github.com/SAML-Toolkits/python-saml](https://github.com/SAML-Toolkits/python-saml)) documente explicitement les contre-mesures XSW après de multiples advisories.

**Test pratique.** Extension **SAML Raider** (Compass Security, [github.com/CompassSecurity/SAMLRaider](https://github.com/CompassSecurity/SAMLRaider)) : interception de la réponse POST SAML, décodage base64 + inflate, menu de **générations automatiques de XSW** (8 patterns), re-signature avec certificat auto-signé, envoi au SP. Verdict : si le SP accepte une assertion dont l'ID ne correspond pas au `Reference` signé → XSW confirmé.

### 1.7 JWT : alg-confusion, `kid` injection, `jwk`/`x5u` injection

**Mécanique — alg confusion.** Le header `alg` est une entrée attaquant-contrôlée. Si la bibliothèque de vérification accepte `HS256` pour un token normalement signé en `RS256`, elle utilisera la **clé publique** comme secret HMAC : l'attaquant signe le token modifié (`alg:HS256`, payload admin) avec la clé publique publiquement lisible (endpoint `/.well-known/jwks.json`).

**Mécanique — `kid` injection.** `kid` est interpolé dans une requête de base de données (SQLi), un chemin de fichier (`kid: ../../dev/null` → clé vide), ou un appel JWK distant non validé.

**Mécanique — `jwk`/`x5u` injection.** Les specs JOSE permettent d'inclure la clé de vérification *dans* le token (`jwk` header) ou de pointer vers elle (`jku`, `x5u` URL). Une bibliothèque permissive vérifie la signature avec la clé fournie par le token lui-même — l'attaquant signe avec sa propre clé et embarque cette clé.

**Cause racine.** Le rang (priority) des sources de clés : *trust-on-first-sight* des clés distantes (`jku`/`x5u`), sélection d'algorithme pilotée par l'attaquant, absence de pinning `alg` côté vérificateur.

**Cas réels.**
- **CVE-2018-0114** — Cisco node-jose : « re-sign tokens using a key embedded in the token » — l'injection de clé `jwk` header, toujours enseignée comme le patron canonique (validé NVD).
- **CVE-2022-29217** — PyJWT : algorithm confusion HS256/RS256 corrigée en 2.4.0 (validé NVD).
- **CVE-2015-9235** — node-jsonwebtoken : la confusion d'algèbre historique, encore présente dans des implémentations maison.
- En 2024-2026, la variante dominante en bug bounty n'est plus la confusion d'alg mais la **confusion d'usage** : réutiliser un access token comme ID token (voir §1.8) et les clés distantes `jku` sur des endpoints multi-tenant.

**Test pratique.** `jwt_tool` ([github.com/ticarpi/jwt_tool](https://github.com/ticarpi/jwt_tool)) : mode `-X a` (alg confusion), `-X k` (kid SQLi/path), `-X i` (jwk injection), `-T` (tamper + re-sign), fuzz des claims (`aud`, `sub`, `exp`, `jti`). Complément : décoder tous les tokens croisés (access, refresh, ID, device, API keys) et **poser la question d'algèbre** : quel claims sont vérifiés, lesquels sont simplement lus ?

### 1.8 Violations de binding des tokens (audience / subject / epoch)

**Mécanique.** Un token JWT/SAML est une liaison τ = (subject, scope, epoch, audience, issuer) (§2.2). Trois violations :
1. **Audience violation** — un token émis pour l'API `payments.internal` accepté par `admin.internal` parce que le récepteur ne vérifie pas `aud` (ou vérifie `aud` contre une liste ouverte).
2. **Subject violation** — un token de session A réutilisé pour muter l'état de B (BOLA par token) ; un ID token d'A utilisé comme credential d'A' après fusion de comptes.
3. **Epoch violation** — token émis avant révocation consommé après (`exp` long + absence de `jti`/revocation list ; `pwd_at`/`iat` non comparés au changement de mot de passe ; refresh token non roté).

**Cause racine.** Vérification incomplète des claims, registres de tokens partagés entre services, absence de *epoch marker* (counter signé incrémenté à chaque événement de sécurité).

**Cas réel.** **CVE-2024-38856** — Apache OFBiz : *incorrect authorization* — des endpoints protégés par un filtre d'authentification restaient accessibles parce que la liaison « session authentifiée → route protégée » n'était pas appliquée sur tous les chemins (validé NVD). Famille complémentaire : les fédérations CI (GitHub Actions OIDC) acceptant des tokens avec des contraintes d'audience insuffisantes (cf. §1.5, writeup 2026).

### 1.9 Contournement de flux MFA (step-up skip, remember-device, race OTP)

**Mécanique.** Le flux MFA est un automate en N étapes : `credentials → mfa_challenge → session`. Trois vecteurs :
1. **Step-up skip** — l'état `mfa_challenge` n'est pas réellement requis avant `session` : l'API accepte l'appel final avec le token intermédiaire, ou une route alternative (`/api/mfa/skip`, paramètre `remember=true` forcé, header `X-Forwarded-For` interne simulé) plonge l'automate dans l'état final.
2. **Remember-device abuse** — le cookie « appareil de confiance » est un JWT longue durée non lié au device (pas de binding User-Agent/IP/pubkey) : volé une fois, il établit la branche MFA-skip pour toujours ; ou il est *attribuable par l'attaquant* (le serveur honore un `remember` client-side au login suivant).
3. **OTP race** — l'endpoint de validation du code à usage unique n'est pas atomique : N requêtes concurrentes sur le même code passent toutes avant la marque d'invalidation ; variante : la fenêtre de rate-limit est réinitialisée par le race, permettant le bruteforce des 6 chiffres (1 000 000 combinaisons, 10^6 essais avant verrouillage).

**Cause racine.** Le *proof of step N* n'est pas un pré-requis structurel de la transition vers N+1 (§2.3, propriété no-skip) ; compteur d'usage non-atomique (TOCTOU).

**Cas réels.**
- **CVE-2023-7028** — GitLab CE/EE : réinitialisation de mot de passe envoyée à une adresse email contrôlée par l'attaquant (validation de l'email insuffisante) — le flux de récupération court-circuite la chaîne de preuves et annule MFA par une prise de contrôle de compte complète (validé NVD).
- **CVE-2025-29927** — Next.js middleware : le header `x-middleware-subrequest` permet de **bypasser le middleware d'authentification** — équivalent d'un step-skip structurel : la route finale croit être protégée alors que la couche de preuve n'a jamais tourné (validé NVD).
- **CVE-2024-45409** (§1.6) — l'attaque SAML Ruby-Gem aboutit à un *bypass MFA* puisque l'assertion forgée est acceptée comme preuve d'identité complète.

### 1.10 Failles de logout et d'invalidation de session

**Mécanique.** Le logout est un automate à trois branches souvent mal câblé : (a) **logout local seulement** — le cookie applicatif est détruit mais l'access token reste valide jusqu'à `exp` (min : 5 min, max : heures) et le refresh token jusqu'à révocation ; (b) **absence de back-channel logout IdP** — le `id_token_hint`/`logout_uri` OIDC n'est pas propagé, la session SSO survit ; (c) **révocation sélective manquante** — changer de mot de passe n'invalide ni refresh tokens ni « sessions de confiance » ; les tokens d'accès pré-epoch restent consommables.

**Cause racine.** Modèle *stateless* sans epoch marker ; absence de composition logout = `invalidate(access) ∧ invalidate(refresh) ∧ invalidate(sso_session) ∧ bump_epoch(subject)`.

**Référence.** RFC 9700 §4.13 exige la révocation des refresh tokens au logout et aux changements de credentials ; NIST SP 800-63B ([pages.nist.gov/800-63-3/sp800-63b](https://pages.nist.gov/800-63-3/sp800-63b.html)) impose la terminaison de toutes les sessions actives au changement de mot de passe. Test pratique : voler (console) un refresh token, logout côté victime, tenter le refresh — si 200 avec un nouveau token, invalidation incomplète.

### 1.11 Replay des magic links (passwordless)

**Mécanique.** Le magic link est un secret porteur dans une URL : `https://app.tld/auth/verify?token=<random>`. Failles : (a) **replay** — le token reste valide après usage (compteur d'usage non atomique ou absent) ; (b) **fuite** — le token passe dans le `Referer` (page externe liée depuis l'email ouverte dans le même tab), dans les logs de proxy corporate, dans les previews de messagerie (scan de liens) ; (c) **Host header poisoning** — l'email de login est généré avec `Host`/`X-Forwarded-Host` attaquant-contrôlé : le lien pointe vers `https://evil.tld/auth/verify?token=<secret valide>` — l'utilisateur clique, l'attaquant intercepte et consomme le token **avant** lui (course d'exclusivité) ; (d) **chaînage cross-tenant** — le token de vérification d'un tenant est accepté par un autre.

**Cause racine.** Secret porteur à usage unique sans binding (pas de nonce de session côté navigateur, pas de binding au fingerprint de boîte mail) + génération d'URL par entrée non approuvée.

**Cas réel.** Classe documentée en profondeur par les labs de password-reset PortSwigger (host header injection → password reset poisoning) et par une longue lignée de disclosures HackerOne sur les magic links non-invalidés. CVE-2023-7028 (§1.9) est le cas d'école 2024 : le flux « envoyer le secret au client » a envoyé le secret **au mauvais client**.

---

## 2. LA THÉORIE : AUTOMATES DE SESSION

### 2.1 Le flux d'authentification comme automate

Définition formelle. Un flux d'authentification est un automate à états finis (DFA élargi en machine de Mealy pour les échanges HTTP) :

```
A = (S, Σ, δ, s0, F)
```

- `S` — états du flux : `s0=idle, s1=creds_sent, s2=mfa_pending, s3=code_issued, s4=code_exchanged, s5=authenticated, s6=step_up_pending, F={authenticated, logged_out}`
- `Σ` — alphabet des entrées : requêtes HTTP (avec leurs paramètres), callbacks IdP, webhooks, timers (`exp`, timeouts de code)
- `δ : S × Σ → S` — fonction de transition, éventuellement partielle (`δ(s,σ) = ⊥` = rejet)
- `s0` — état initial, `F` — états acceptants

La **décomposition serveur/client** est essentielle : le *client flow* (navigateur/app) et le *server flow* (back-end) sont deux automates A_c et A_s synchronisés par messages. La plupart des bugs §1 sont des **désynchronisations** : A_c croit être dans l'état `mfa_pending` alors que A_s accepte d'avancer vers `authenticated`.

### 2.2 Entrées contrôlées par l'attaquant et liaison de token

**Sous-ensemble attaquant.** On partitionne `Σ = Σ_h ∪ Σ_a` où `Σ_h` est honnête (généré par le RP/IdP) et `Σ_a` est contrôlable par l'attaquant. En pratique : `Σ_a ⊇ {paramètres de requête (state, code, iss, redirect_uri, jku, x5u, alg, kid, host), tokens injectés (cookie porteur, Bearer), réponses IdP de l'IdP de l'attaquant, timing}`. La menace formelle : il existe une exécution acceptante où au moins une transition consomme une entrée de `Σ_a` alors que la propriété de sécurité suppose `Σ_h`. Un bug de flow = une trace acceptante w telle que `|w ∩ Σ_a| > 0` et `w ⊢ P_violation`.

**Binding de token.** Un token est une liaison :

```
τ = (subject, scope, epoch, audience, issuer)
```

- `subject` — l'identité nommée (user_id, tenant_id)
- `scope` — ensemble de permissions portées
- `epoch` — marqueur d'époque (monotone par subject : mot de passe changé, MFA changée, logout global ⇒ epoch+1 ; tout token avec `epoch < current` est invalide)
- `audience` — ensemble des récepteurs légitimes
- `issuer` — émetteur attendu ( clé de vérification correspondante )

**Propriété de préservation de liaison** (informelle puis formelle en §2.3) : *un token émis pour le subject A et l'audience X ne doit jamais accorder l'accès pour le subject B ou l'audience Y*, sur toutes les traces, y compris les traces où l'attaquant contrôle l'émetteur.

### 2.3 Propriétés de sécurité en LTL/CTL

Le modèle temporel est discret (un pas = une requête HTTP observée). Notations LTL : `□` (toujours), `◇` (éventuellement), `X` (pas suivant), `U` (until).

**P1 — chaîne de preuve complète (no-skip).** Toute libération d'une ressource protégée doit être précédée d'une preuve complète :

```
□(resource_access → ◇completed_proof_chain)
```

instancié par étape pour un flux MFA à N étapes :

```
∀n ∈ [1, N-1] : □( enter_step(n+1) → ◇ proof_of_step(n) ∧ ¬expired(proof_of_step(n)) )
```

`completed_proof_chain` = la conjonction des preuves `{creds_valid, otp_valid, device_bound, consent_granted}` exigées par la politique. Contre-exemple = trace menant à `resource_access` avec `otp_valid` faux ou expiré → bug §1.9.

**P2 — exclusivité d'usage (no-replay).** Les secrets à usage unique (code, otp, magic token) obéissent à :

```
□( consume(c) → X □ ¬consume(c) )       [one-shot]
```

variante forte (exclusivité concurrente, non exprimable en LTL pur, requiert CTL ou sémantique interleaving) :

```
AG( consume(c) → AX( ∀c' = c : ¬consume(c') ) )
```

**P3 — préservation de liaison.**

```
□( grant_access(subj=B, res) → ∃τ : τ.subject = B ∧ τ.epoch ≥ epoch_now(B) ∧ res ∈ τ.audience )
```

**P4 — non-falsification d'émetteur (anti mix-up).**

```
□( accept_token(τ) → τ.issuer ∈ TrustedIssuers ∧ verify(τ, key_of(τ.issuer)) )
□( authz_response(resp) → resp.iss = expected_iss(route) )
```

**P5 — réacheminement contraint (redirect confinement).**

```
□( issue_redirect(r) → r ∈ exact_registered_set(client_id) )
```

(`exact_registered_set` : comparaison chaîne à chaîne, pas de glob.)

**P6 — entropie.** Pour tout secret généré s par l'honnête partie : `H(s) ≥ 128 bits` (state, nonce) et `H(code) ≥ 160 bits` (codes d'autorisation, magic tokens) — formulation en §6.1.

**P7 — terminaison de session.**

```
□( logout(u) → X □ ¬grant_access(any token τ : τ.subject = u ∧ τ.issued_at < logout_time(u)) )
```

**CTL vs LTL.** LTL exprime les propriétés linéaires (traces) ; les propriétés d'exclusivité entre branches et les races exigent CTL (`AG/EF/AX`) sur le *product automaton* (§2.4). En pratique un model-checker comme SPIN ou NuSMV sur l'abstraction du flux, ou un runtime monitor (§5.3) pour les propriétés instanciées sur traces réelles.

### 2.4 L'automate produit : client × serveur × token store

Le système complet est le **synchronisation produit** :

```
A_sys = A_client × A_server × A_store     (synchronisé sur les messages partagés)
```

- `A_client` — états du navigateur/app (barre d'URL, cookies, mémoire JS)
- `A_server` — états back-end (sessions, challenges MFA, comptes d'usage des codes)
- `A_store` — l'état du trousseau de tokens (access/refresh/ID par subject, avec leur τ)

Taille du produit : `|S_sys| = |S_c| · |S_s| · |S_t|`. Pour un flux réaliste : `|S_c| ≈ 10`, `|S_s| ≈ 50` (comptes d'usage, flags), `|S_t|` croît avec les bindings — chaque token actif ajoute un facteur : avec 3 tokens actifs × 5 valeurs de τ pertinentes, `|S_t| ≈ 10^3`. Le produit atteint 5×10^5 états : **explosion combinatoire** (détails et bornes §6.3). C'est le cœur du problème : le test manuel explore un infime voisinage de `s0`, alors que les bugs vivent dans les états **profonds et concurrents**.

### 2.5 Explosion d'états, bisimulation et états symboliques

**Quotient par bisimulation.** Deux états sont bisimilaires s'ils indiscernables pour l'observateur (les réponses HTTP et les effets de sécurité). Le quotient `A_sys / ~bis` préserve toutes les propriétés LTL/CTL : on peut réduire drastiquement avant model-checking. Algorithme de Paige–Tarjan : `O(m · log n)` pour n états, m transitions — linéaire-logarithmique, applicable à 10^5-10^6 états. En pratique, la relation d'abstraction est construite à la main : on abstrait les valeurs (timestamps, tokens) par des symboles et on ne garde que les **prédicats de sécurité** (verifié/échoué, consommé/libre, epoch).

**États symboliques et anti-unification.** Au lieu d'énumérer les valeurs concrètes (token = `eyJhbG...`), on manipule des **états paramétrés** : `(state=code_exchanged, code=α, τ=τ(α))` où α est une variable SMT. L'**anti-unification** de deux états concrets (leurs différences sont des valeurs non-sécurité-relevantes) produit l'état généralisé : `(code_exchanged, code=α)` couvre à la fois. Le model checking devient symbolique : les transitions sont des formules SMT sur α, β (solver Z3), et l'équivalence de deux états symboliques = satisfiabilité de la conjonction des différences. C'est exactement l'architecture des checkers symboliques modernes : garder `n_sym` (10²-10³) états symboliques représentant 10^5-10^6 états concrets.

### 2.6 Propriétés comme templates paramétrés

Un template de propriété = schéma LTL/CTL + fonction d'instanciation sur le flux cible :

| Template | Formule (instanciée) | Bug ciblé |
|---|---|---|
| no-skip | `□(enter(s_{n+1}) → ◇proof(n) ∧ fresh(proof(n)))` | MFA bypass, middleware skip |
| no-replay | `□(consume(c) → X□¬consume(c))` | code/OTP/magic-link replay |
| binding-preservation | `□(grant(B) → ∃τ: τ.sub=B ∧ τ.aud ∋ res ∧ τ.epoch≥now)` | aud/sub confusion, BOLA |
| issuer-confinement | `□(accept(τ) → τ.iss ∈ T ∧ key(τ.iss) ⊢ verify)` | mix-up, IDP confusion |
| redirect-confinement | `□(redirect(r) → r ∈ R_exact(client))` | redirect_uri bypass |
| entropy | `H(gen(secret)) ≥ Lmin` | state/nonce/code prévisibles |
| epoch-invalidation | `□(event(u) → bump_epoch(u))` | logout/rotation gaps |

Le pipeline de chasse (§3, §5) consiste à : (1) inférer la machine du flux, (2) instancier les templates, (3) chercher un contre-exemple sur la machine inférée **et** confirmer sur la cible réelle (car la machine inférée est une approximation — le contre-exemple est une hypothèse de bug, pas une preuve).

---

## 3. MÉTHODOLOGIE DE CHASSE PRATIQUE

### 3.1 Phase A — instrumentation du flux (proxy scripté)

**Outils.** mitmproxy ([github.com/mitmproxy/mitmproxy](https://github.com/mitmproxy/mitmproxy)) pour un contrôle total en Python (addons `on_request`/`on_response`, rejeu, dumpters), ou Burp Suite (Match & Replace, Session Handling Rules, macros) pour l'ergonomie. Le principe : **tout le flux est journalisé en traces structurées** `(timestamp, direction, method, path, params, headers(clé), body_token_fields, cookies)`.

**Matrice d'identités.** On construit le minimum vital : `V` (victime), `A` (attaquant), `A'` (deuxième compte attaquant — nécessaire pour détecter les confusions inter-comptes), et si multi-tenant : `T1`, `T2` (comptes de tenants distincts, IdP distincts si possible). Toute la méthodologie consiste à **croiser les étapes** : démarrer le flux avec V, terminer avec A, et réciproquement, à chaque transition.

**Scripting type (mitmproxy addon, Python).**

```python
class AuthTracer:
    def __init__(self):
        self.trace = []
    def response(self, flow):
        if is_auth_step(flow):            # filtre: /auth, /oauth, /saml, /login, /mfa...
            self.trace.append(serialize(flow))
            save_json(self.trace)          # trace = séquence symbolique
```

### 3.2 Phase B — inférence de l'automate (L*, Angluin)

L'apprentissage actif (L* d'Angluin) infère l'automate du flux depuis des requêtes cibles :

- **MQ (membership query)** — « exécuter cette séquence d'entrée, quel état observable ? » = envoyer la séquence de requêtes HTTP et lire la réponse observable (code HTTP + marqueurs).
- **EQ (equivalence query)** — « la machine candidate est-elle équivalente à la cible ? » — réalisé par conformance testing (W-method) ou par les contre-exemples manuels du chercheur.

Le nerf : **l'abstraction alphabétique**. Les requêtes HTTP brutes sont infinies ; on mappe vers un alphabet fini de symboles d'entrée : `submit_otp(α)`, `exchange_code(α)`, `callback(iss=β, code=γ)`, `refresh(τ)`… et l'état observable se réduit aux signaux : code HTTP, présence/absence de session, message d'erreur discriminant. Une machine de Mealy suffit (sortie à chaque transition).

**Implémentations.** AALpy ([github.com/DES-Lab/AALpy](https://github.com/DES-Lab/AALpy)) — bibliothèque Python pure d'apprentissage actif (DFA/Mealy, algorithms KV/RPNI/L*) ; LearnLib ([learnlib.de](https://learnlib.de/)) — la référence Java. Pour un moteur VoidForge en Python, AALpy est le choix naturel (scriptable Windows, pas de JVM).

**Complexité.** Voir §6.2 : L* en `O(k·n·(n+|Σ|))` membership queries et `k·n` equivalence queries pour une machine à n états, k = nombre de contre-exemples. Pour un flux auth (n ≈ 15-30, |Σ| ≈ 10-25), c'est quelques centaines à quelques milliers de requêtes HTTP — bruitant mais faisable sur un environnement de test.

**En pratique, deux niveaux.** (1) *L* complet* sur un lab (PWM, Keycloak local, démonstrateur) pour comprendre la machine. (2) *Transition map partielle* sur la cible : on ne construit que les transitions suspectes (les croisements V↔A, les skips d'étapes, les doublons de consommation) — c'est 95 % de la chasse réelle, la machine inférée sert de carte, pas de preuve.

### 3.3 Phase C — vérification des propriétés contre la machine

Chaque template §2.6 est instancié sur la machine (ou sur la carte partielle) : le no-skip devient « existe-t-il un chemin `s0 →* authenticated` qui n'emprunte pas `mfa_challenge` ? » (reachability analysis, BFS sur la carte). Le no-replay devient « la transition `consume(code)` a-t-elle un self-loop ou une garde d'invalidation ? ». Toute violation candidate est **rejouée concrètement** (reproductibilité en 3 requêtes) — c'est le verdict.

### 3.4 Phase D — algèbre des tokens (decode-all-the-things)

Procédure systématique sur chaque token capturé (access, refresh, ID, device, invitation, API) :

1. **Décodage** — split `.` , base64url decode header/payload (JWT) ; base64 + inflate + pretty XML (SAML Response, voir SAML Raider).
2. **Inventaire des claims** — `alg, kid, jku, x5u, jwk, iss, aud, sub, exp, iat, nbf, jti, scope, tenant, epoch-equivalents (pwd_at, auth_time, amr)`.
3. **Questions d'algèbre** — aud est-il vérifié partout ? le sub est-il porteur de droits ou seulement d'identité ? existe-t-il un epoch ? le `kid` est-il injectable (SQLi/path) ? le `jku`/`x5u` est-il résolu dynamiquement ?
4. **Manipulation contrôlée** — jwt_tool `-T` (tamper), `-X a` (alg confusion), `-X k` (kid), re-signature avec clés connues, rejeu cross-audience.
5. **Chorologie des tokens** — remplacer le token de V par celui de A dans chaque requête de la carte (phase B) : toute acceptation = violation de binding-preservation.

### 3.5 Phase E — fenêtres de course sur les étapes à usage unique

Les étapes `consume(code)`, `consume(otp)`, `consume(magic_token)`, `redeem(invite)` sont des **sections critiques** : la garde d'usage unique est un check-then-set (TOCTOU). Deux techniques :

- **HTTP/1.1 — last-byte sync** (Turbo Intruder, [github.com/PortSwigger/turbo-intruder](https://github.com/PortSwigger/turbo-intruder)) : N connexions TCP parallèles, toutes les requêtes pré-écrites sauf **le dernier octet** ; on relâche les derniers octets en rafale — les N requêtes traversent le réseau en un temps quasi nul et se présentent au serveur simultanément.
- **HTTP/2 — single-packet attack** (James Kettle, « Smashing the State Machine », [portswigger.net/research/smashing-the-state-machine](https://portswigger.net/research/smashing-the-state-machine)) : une seule connexion HTTP/2, N streams (`HEADERS` envoyés, `DATA` en un seul paquet) — **toutes les requêtes arrivent dans un unique segment TCP**, le serveur les traite dans la même fenêtre d'ordonnanceur ; la synchronisation est quasi parfaite, bornée par la discipline de queue du serveur (voir la discussion des files d'attente dans l'article de Kettle — les points de désynchronisation côté serveur sont les files et les worker pools).

**Cible privilégiée** : les endpoints à usage unique avec écriture asynchrone (code → marked_used en queue), les redeem d'invitations, les OTP de transfert de propriété, et les **retraits de garantie** (changer d'email sans re-vérifier).

---

## 4. OUTILLAGE SOTA 2024-2026

| Outil | Type | Licence | Langage | Windows + scriptable Python | Lien |
|---|---|---|---|---|---|
| **mitmproxy** | Proxy instrumentation + addons Python | MIT | Python | ✅ natif | [repo](https://github.com/mitmproxy/mitmproxy) |
| **Turbo Intruder** | Extension Burp de courses HTTP (single-packet, last-byte sync) | open source | Java core + scripts Python | ✅ scripts Python embarqués | [repo](https://github.com/PortSwigger/turbo-intruder) |
| **Auth Analyzer** | Extension Burp — comparaison multi-rôles (réponses V vs A) | BApp Store | Java | ⚠️ Java, pas Python | BApp Store Burp |
| **Autorize** | Extension Burp — détection automatique d'authorization enforcement | open source | Jython | ⚠️ Jython (Python 2) | [repo](https://github.com/Quitten/Autorize) |
| **AuthMatrix** | Extension Burp — matrice rôles × requêtes | open source | Java | ⚠️ | [repo](https://github.com/SecurityInnovation/AuthMatrix) |
| **Authz-ExeC** | Extension Burp — cross-identity & **cross-tenant** access control | open source | Java | ⚠️ | [repo](https://github.com/execiq/Authz-ExeC) |
| **SAML Raider** | Extension Burp — décodage, XSW patterns, re-signature SAML | open source | Java | ⚠️ | [repo](https://github.com/CompassSecurity/SAMLRaider) |
| **jwt_tool** | Boîte à outils JWT (tamper, alg confusion, kid, jwk) | open source | **Python** | ✅ natif | [repo](https://github.com/ticarpi/jwt_tool) |
| **AALpy** | Apprentissage actif d'automates (L*, KV, RPNI) | open source | **Python** | ✅ natif | [repo](https://github.com/DES-Lab/AALpy) |
| **LearnLib** | Apprentissage actif d'automates (référence académique) | open source | Java | ⚠️ JVM | [site](https://learnlib.de/) |
| **oauth.tools** | Playground OAuth/OIDC interactif (flows, tokens) | gratuit | — | — | [site](https://oauth.tools/) |
| **OAuth 2.0 Playground** | Playground complet (Parecki) | gratuit | — | — | [site](https://www.oauth.com/playground/) |
| **authn.io** | Outils de génération/décodage (JWT, DID) | gratuit | — | — | [site](https://authn.io/) |
| **SAML-Toolkits (python-saml)** | Lib + décodeur SAML de référence | open source | **Python** | ✅ | [repo](https://github.com/SAML-Toolkits/python-saml) |

**Lecture Windows/Python.** Le cœur VoidForge scriptable est : **mitmproxy (traces) + jwt_tool (algèbre) + AALpy (inférence) + Python stdlib/asyncio (courses via httpx/HTTP2 h2)**. Les extensions Burp (Java/Jython) servent d'atelier interactif ; le moteur automatisé (§5) les remplace.

**Référentiels d'entraînement** : les labs OAuth de PortSwigger ([web-security/oauth](https://portswigger.net/web-security/oauth)) couvrent les classes §1.1-1.3 et §1.9 ; un Keycloak local + un Auth0 free-tier permettent de reproduire mix-up (§1.4) et XSW (§1.6) de bout en bout.

---

## 5. ARCHITECTURE D'UN MOTEUR VOIDFORGE : `auth_state_engine`

### 5.1 Entrées et pipeline

```
INPUT:
  base_url: str
  flow_type: oauth2_code | oidc | saml_sp | jwt_chain | magic_link | mfa_stepup | multi_tenant
  identities: [ {name, creds, tenant}, ... ]        # matrice V / A / A'
  props: [ no_skip | no_replay | binding | issuer | redirect | entropy ]

PIPELINE:
  (a) flow_instrumentation   → traces[]   (client HTTP scripté + session pool)
  (b) machine_inference      → Mealy M    (AALpy L* ou transition map manuelle)
  (c) property_checking      → violations[] (moniteurs runtime sur les templates LTL)
  (d) token_algebra          → bindings τ + résultats de manipulation
  (e) race_harness           → double-consumption confirmée / réfutée
  (f) verdict()              → JSON contract
```

### 5.2 Conception du runtime

```python
class AuthStateEngine:
    def __init__(self, base_url, flow_type, identities):
        self.session_pool = SessionPool(identities)     # cookies/tokens par identité
        self.tracer      = TraceRecorder()              # (a) instrumentation
        self.machine     = None                         # (b) Mealy inférée
        self.bindings    = TokenStore()                 # (d) τ observés
        self.findings    = []

    # (a) — le client scripté rejoue le flux et log chaque échange
    def instrument(self, script: FlowScript):
        for step in script.steps:
            resp = self.session_pool[step.actor].send(step.request)
            self.tracer.record(step, resp)
            self.bindings.ingest(resp)                  # extraction JWT/SAML/cookies

    # (b) — inférence : abstraction alphabétique puis L*
    def infer(self, alphabet: dict, oracle: TargetOracle):
        mapper   = SymbolMapper(alphabet)               # requête → symbole
        learner  = AALpyLStar(mapper, oracle)           # MQ = requêtes HTTP réelles
        self.machine = learner.learn()                  # Mealy Machine

    # (c) — propriétés : moniteurs runtime (voir 5.3)
    def check(self, templates):
        for t in templates:
            v = t.monitor(self.machine, self.tracer.traces)
            if v.counterexample:
                self.findings.append(v)

    # (d) — algèbre des tokens
    def algebra(self):
        for tok in self.bindings.all():
            self.findings += TokenAlgebra(tok).run()    # decode, kid, jku, aud cross-replay

    # (e) — courses sur les étapes one-shot détectées par le no-replay monitor
    def race(self, endpoints_single_use):
        for ep in endpoints_single_use:
            self.findings += RaceHarness(ep, self.session_pool).attempt_pair()

    # (f) — contrat de sortie
    def verdict(self):
        return Verdict(self.findings).to_json()
```

### 5.3 Moniteur runtime — no-skip et mix-up (pseudo-code)

**No-skip (P1).** Moniteur sur la machine inférée : recherche d'un chemin acceptant vers l'état protégé qui contourne la preuve.

```python
def no_skip_monitor(machine, protected_state, required_proofs):
    """
    P1:  □(enter(s_{n+1}) → ◇proof(n) ∧ fresh(proof(n)))
    Trouve toute trace s0 →* protected_state qui n'acquiert pas
    les preuves requises (ou les acquiert expirées).
    """
    violations = []
    for path in machine.bfs_paths(machine.s0, protected_state):
        acquired = {s for s in path if machine.symbol(s).is_proof}
        missing  = required_proofs - acquired
        expired  = {p for p in acquired if not machine.guard_fresh(path, p)}
        if missing or expired:
            violations.append({
                "template": "no_skip",
                "property": "□(enter(s_protected) → ◇proof ∧ fresh)",
                "path": machine.symbols(path),           # trace symbolique
                "missing_proofs": sorted(missing),
                "expired_proofs": sorted(expired),
            })
    return violations   # chaque entrée = scénario de reproduction (rejeu concret)
```

**Mix-up (P4).** Moniteur sur les traces réelles : tout callback qui sélectionne l'endpoint de token sans preuve d'issuer vérifiée.

```python
def mixup_monitor(traces, expected_iss_by_route):
    """
    P4: □(authz_response(resp) → resp.iss = expected_iss(route))
        □(accept_token(τ) → τ.issuer ∈ TrustedIssuers ∧ key(τ.issuer) ⊢ verify(τ))
    Test actif : IdP de l'attaquant émet un code ; on forge le callback
    avec iss = IdP légitime ; toute acceptation = mix-up.
    """
    findings = []
    for tr in traces:
        cb = tr.last("/callback")
        if cb and cb.iss_param is None and not tr.has("issuer_bound_in_session"):
            findings.append({
                "template": "issuer_confinement",
                "evidence": tr.symbolic,
                "test": "attacker_idp_code + forged iss → token exchange",
            })
        if cb and cb.iss_param and cb.iss_param != expected_iss_by_route[cb.route]:
            findings.append({"template": "issuer_confinement",
                             "verdict": "MISMATCH_ACCEPTED" if tr.token_accepted else "rejected"})
    return findings
```

### 5.4 Contrat `verdict()` (JSON)

```json
{
  "engine": "auth_state_engine",
  "target": {"base_url": "https://app.tld", "flow": "oidc", "date": "2026-08-30"},
  "machine": {"states": 27, "alphabet": 19, "inference": "L* (AALpy)", "confidence": 0.91},
  "findings": [
    {
      "id": "VF-AUTH-001",
      "template": "no_replay",
      "severity": "critical",
      "title": "Authorization code not atomically single-use (race)",
      "property": "□(consume(c) → X□¬consume(c))",
      "evidence": {"n_races": 10, "double_use_success": 8,
                   "trace": ["GET /authorize", "302 cb?code=α", "POST token(α) x2 → 200,200"]},
      "repro": ["step1: ...", "step2: ..."],
      "impact": "code interception + concurrent exchange → account takeover"
    }
  ],
  "entropy": {"state_bits": 63, "verdict": "FAIL(<128)"},
  "token_bindings": [{"jwt": "access", "aud_verified": false, "notes": "aud ignored by /api/admin"}]
}
```

---

## 6. MATHS APPLIQUÉES

### 6.1 Entropie des tokens

Pour un secret de `L` caractères tirés uniformément d'un alphabet de taille `|C|` :

```
H = L · log2(|C|)   [bits]
```

| Charset | \|C\| | log2\|C\| | bits/caractère |
|---|---|---|---|
| hex | 16 | 4.000 | 4.00 |
| base36 | 36 | 5.170 | 5.17 |
| base62 (A-Za-z0-9) | 62 | 5.954 | 5.95 |
| base64url | 64 | 6.000 | 6.00 |
| ASCII imprimable | 95 | 6.569 | 6.57 |

**Longueurs minimales** pour atteindre un budget d'entropie (`L = H / log2|C|`) :

- `state ≥ 128 bits` : hex 32 car ; base62 **22 car** (128/5.954 = 21.5) ; base64url 22 car.
- `code ≥ 160 bits` : hex 40 car ; base62 **27 car** ; base64url 27 car.
- OTP 6 chiffres = log2(10^6) ≈ **19.9 bits** — jamais suffisant seul, ce qui impose le rate-limit et le verrouillage (c'est le no-replay + rate qui compense, pas l'entropie).

### 6.2 Bornes d'anniversaire (birthday bounds)

La probabilité de collision d'un secret de H bits après `n` tirages est approx `1 − e^{−n²/2^{H+1}}`. Le seuil 50 % est atteint à `n ≈ 2^{H/2}` :

| Entropie H | n @ 50 % collision | Lien de sécurité |
|---|---|---|
| 64 bits | 2^32 ≈ 4.3 × 10^9 | insuffisant pour un secret online |
| 80 bits | 2^40 ≈ 1.1 × 10^12 | marginal |
| **128 bits** | 2^64 ≈ 1.8 × 10^19 | standard state/nonce |
| **160 bits** | 2^80 | standard codes |
| 256 bits | 2^128 | overkill sauf clés |

Pour l'attaquant *online* (limité par le débit réseau), la borne pertinente est le nombre d'essais réalisables : à 10 000 req/s, 128 bits rend l'attaque online impossible même en un siècle (10^12 essais ≪ 2^128). C'est pourquoi les bugs d'entropie réels sont presque toujours des **PRNG faibles** (seed temporel) et non des longueurs trop courtes — le test est de **collecter N secrets et tester la distribution** (gaps, corrélations temporelles, PRNG linéaire).

### 6.3 Explosion d'états et quotient

Produit de trois automates : `|S_sys| = |S_c| · |S_s| · |S_t|`. Avec k bindings de tokens actifs, chacun muni de 5 composantes de τ bornées à r valeurs : `|S_t| ≈ r^{5k}`. Exemple : r=4, k=3 → 4^15 ≈ 10^9. **Le model checking naïf est impossible** ; la réduction passe par :

1. **Bisimulation** (Paige–Tarjan, `O(m log n)`) — préserve LTL*/CTL* ;
2. **Anti-unification symbolique** — fusion des états ne différant que par des valeurs non-sécurité : en pratique un facteur de compression de 10²-10^4 (les 10^9 états concrets se réduisent à 10²-10^3 états symboliques traités par un solver SMT) ;
3. **Bounds checking** — vérification incrémentale par BMC (bounded model checking) à profondeur d = longueur maximale d'un flux (typiquement 12-20 transitions), coût `O(|δ|^d)` borné et réel.

### 6.4 Complexité de l'inférence L*

Pour une machine cible à n états, un alphabet de taille |Σ|, et k contre-exemples fournis par l'oracle d'équivalence, l'algorithme d'Angluin L* (avec table d'observation T) requiert :

```
MQ : O(k · n · (n + |Σ|))            membership queries
EQ : ≤ k · n                          equivalence queries
```

Chaque MQ = une séquence HTTP rejouée (coût linéaire en longueur). Pour un flux OIDC : n ≈ 25, |Σ| ≈ 20, k ≈ 10 → MQ ≈ 10·25·45 ≈ **11 250 requêtes** ; en pratique, la carte partielle (§3.2) n'explore que ~2-5 % de cet espace.

### 6.5 Math des courses (race window probability)

Modèle : la fenêtre critique du serveur (entre check et set de l'usage unique) a une durée `w` ; les requêtes concurrentes arrivent avec un écart médian `d` ; le délai aller-retour est `rtt`.

- **k requêtes, fenêtre w, dispersion σ** : la probabilité qu'au moins deux requêtes tombent dans la même fenêtre s'approche de `P ≈ 1 − (1 − w/σ)^{C(k,2)}` (approx. indépendante).
- **Last-byte sync / single-packet** : la dispersion σ chute à l'ordre du temps de traitement par le noyau (≈ 50-500 µs par requête). Avec w = 1 ms (écriture asynchrone) et k = 30 requêtes single-packet, l'attaque réussit typiquement : `P ≈ 1 − (1 − 10^{-3}/5·10^{-4})^{435}` → saturée à ~1 — en pratique, 60-90 % des tentatives produisent au moins une double-consommation.
- **Sans synchronisation** (k envois étalés sur rtt = 50 ms) : σ ≈ 17 ms pour k=30 → `P ≈ k·w/rtt ≈ 30·10^{-3}/5·10^{-2} = 0.6` — viable mais bruité ; d'où l'intérêt du single-packet attack (Kettle 2023).

La **course d'exclusivité** du code OAuth (vol + échange) est duale : l'attaquant et la victime font la même requête `POST /token` ; celui qui arrive en second obtient `invalid_grant` **si et seulement si** la garde d'usage unique est atomique — le test consiste à mesurer si le second appel passe (bug) ou échoue.

---

## 7. SOURCES

**Standards & référentiels**
1. RFC 9700 — *Best Current Practice for OAuth 2.0 Security* (IETF, jan. 2025) — <https://datatracker.ietf.org/doc/rfc9700/>
2. RFC 7636 — *Proof Key for Code Exchange (PKCE)* — <https://datatracker.ietf.org/doc/rfc7636/>
3. RFC 8252 — *OAuth 2.0 for Native Apps* — <https://datatracker.ietf.org/doc/rfc8252/>
4. RFC 9207 — *OAuth 2.0 Authorization Server Issuer Identification* — <https://datatracker.ietf.org/doc/rfc9207/>
5. OWASP OAuth 2.0 Cheat Sheet — <https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html>
6. NIST SP 800-63B — *Digital Identity Guidelines: Authentication* — <https://pages.nist.gov/800-63-3/sp800-63b.html>

**Recherche & writeups**
7. James Kettle — *Smashing the State Machine: the True Potential of Web Race Conditions* (PortSwigger Research) — <https://portswigger.net/research/smashing-the-state-machine>
8. PortSwigger Web Security Academy — *OAuth 2.0 Authentication Vulnerabilities* — <https://portswigger.net/web-security/oauth>
9. Michał Bentkowski (Securitum) — *Clickjacking OAuth Flows* — <https://research.securitum.com/clickjacking-oauth-flows/>
10. Daniel Fett — *Mix-Up Revisited* (analyse formelle de l'attaque mix-up) — <https://danielfett.de/2020/05/04/mix-up-revisited/>
11. William Woodruff — *GitHub Actions needs OIDC audience constraints* (2026) — <https://blog.yossarian.net/2026/08/10/github-actions-needs-oidc-audience-constraints>

**CVEs (validés NVD)**
12. CVE-2024-45409 — Ruby-SAML signature verification flaw (GitLab SAML bypass) — <https://nvd.nist.gov/vuln/detail/CVE-2024-45409>
13. CVE-2022-47966 — Zoho ManageEngine / Apache Santuario SAML pre-auth RCE — <https://nvd.nist.gov/vuln/detail/CVE-2022-47966>
14. CVE-2018-0114 — Cisco node-jose : clé embarquée dans le token (`jwk` injection) — <https://nvd.nist.gov/vuln/detail/CVE-2018-0114>
15. CVE-2022-29217 — PyJWT algorithm confusion (HS256/RS256) — <https://nvd.nist.gov/vuln/detail/CVE-2022-29217>
16. CVE-2023-7028 — GitLab : réinitialisation de mot de passe vers email contrôlé (prise de contrôle, contournement de la chaîne de preuves) — <https://nvd.nist.gov/vuln/detail/CVE-2023-7028>
17. CVE-2025-29927 — Next.js : bypass du middleware d'authentification (step-skip structurel) — <https://nvd.nist.gov/vuln/detail/CVE-2025-29927>
18. CVE-2024-1132 — Keycloak : validation insuffisante des URLs de redirection — <https://nvd.nist.gov/vuln/detail/CVE-2024-1132>
19. CVE-2024-38856 — Apache OFBiz : incorrect authorization — <https://nvd.nist.gov/vuln/detail/CVE-2024-38856>

**Outillage**
20. mitmproxy — <https://github.com/mitmproxy/mitmproxy>
21. Turbo Intruder (PortSwigger) — <https://github.com/PortSwigger/turbo-intruder>
22. AALpy — *An Automata Learning Library in Python* — <https://github.com/DES-Lab/AALpy>
23. LearnLib — <https://learnlib.de/>
24. jwt_tool — <https://github.com/ticarpi/jwt_tool>
25. SAML Raider (Compass Security) — <https://github.com/CompassSecurity/SAMLRaider>
26. Autorize — <https://github.com/Quitten/Autorize> · AuthMatrix — <https://github.com/SecurityInnovation/AuthMatrix> · Authz-ExeC (cross-tenant) — <https://github.com/execiq/Authz-ExeC>
27. SAML-Toolkits / python-saml — <https://github.com/SAML-Toolkits/python-saml>
28. oauth.tools — <https://oauth.tools/> · OAuth 2.0 Playground — <https://www.oauth.com/playground/> · authn.io — <https://authn.io/>

---

## 8. ARTIFACTS COMPAGNONS (implémentation de référence v0)

Le §5 de ce dossier est accompagné d'une implémentation exécutable de référence, maintenue dans ce répertoire :

| Fichier | Rôle |
|---|---|
| [`auth_state_engine_v0.py`](auth_state_engine_v0.py) | Moteur v0 (stdlib uniquement, Python ≥ 3.10) — moniteurs runtime `no_skip` / `no_replay` / `issuer_confinement` (§5.3 rendus exécutables), audit JWT algèbre des tokens (§1.7, §3.4), vérificateur d'entropie (§6.1, canonique par classe de caractères), générateur de plan de course (§3.5, §6.5), contrat `verdict()` §5.4. Démo déterministe intégrée, zéro réseau. |
| [`lab_guide_auth_state_engine.md`](lab_guide_auth_state_engine.md) | Guide de laboratoire : schéma des traces, addon mitmproxy de capture, matrice d'identités V/A/A′ et croisements d'étapes, interprétation des findings → classes §1, limites v0 et feuille de route (L*/AALpy, single-packet via Turbo Intruder, états symboliques SMT). |
| [`verdict_demo.json`](verdict_demo.json) | Verdict de démonstration (sortie réelle du moteur) : 7 findings sur traces synthétiques vulnérables — no-skip MFA ×3, code non-atomique ×1, mix-up (iss manquant + émetteur non approuvé) ×2, violation d'audience ×1 — plus entropies (64.0 / 131.0 / 19.9 bits) et 2 bindings JWT audités. |

Exécution de vérification (2026-08-31, Python 3.14.5, Windows) : `python auth_state_engine_v0.py` → exit 0, contrat JSON conforme.

---

*Fin du dossier 3. Dossier suivant suggéré : dossier_4 — races applicatives au-delà de l'auth (state machines de paiement et de workflow).*
