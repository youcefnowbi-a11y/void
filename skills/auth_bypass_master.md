# skill: auth_bypass_master
title: Authentication Bypass Systems (JWT / session / OTP / reset / OAuth)
when: auth,login,jwt,session,token,password,otp,reset,oauth,signup,bypass,admin

## OPERATING PRINCIPLE
Auth is a state machine, and every state transition is an attack surface.
The universal law: forge the state the server wants to see, and replay it
where the server checks it. Never conclude "locked" from one 403 — auth
is layers, and each layer has its own bypass grammar.

## CHAIN
1. Baseline both sides: one anon session, one (self-registered) low-priv
   session via auth_signup_probe — differential testing needs both.
2. jwt_analyst on every token you hold (bundle leaks via js_mine_site,
   cookies, headers) — read alg, claims, exp, kid.
3. jwt_forge_replay — the full matrix: alg:none (4 casings — servers
   compare the alg STRING, case-sensitively), RS→HS confusion (public key
   from the JS bundle or /jwks.json signs an HMAC), kid injection
   (../../dev/null → empty secret, /etc/hostname traversal), jku/x5u
   header injection (operator-hosted JWKS), claims escalation (role:admin).
   Replay against EVERY endpoint that returned 401 — different endpoints,
   different verification code paths.
4. OTP logic (otp_brute): 4-6 digit codes, no rate limit = minutes to
   break. Rate limited? Check if the limit is per-IP (rotate) or
   per-session (re-session). Response timing differences on valid prefixes
   (first 2 digits fast = split the search).
5. Password reset: token entropy (is it the timestamp? user id + md5?),
   token-in-response leaks on the API, host-header poisoning of the reset
   link (auth_metadata_poison patterns on the reset flow), reset with
   tampered email parameter.
6. OAuth flows: redirect_cast on redirect_uri (open redirect = code theft),
   state-less CSRF on callback, code reuse, scope confusion.
7. Session fixation/refresh: replay_mutate old tokens — do sessions expire
   server-side or only client-side?
8. IDOR across identity boundaries: idor_enum / idor_b64_walk with BOTH
   sessions — the low-priv session reading the admin's object ids is the
   classic escalation.

## STATE-MACHINE ATTACKS (response manipulation class)
- OTP verified in response body → flip "success": false to true (client
  trusts server response for state) — test on every verification step.
- Negative / huge / float values on prices and quantities during checkout
  auth boundaries.
- Duplicate email registration (case variation, +suffix, unicode) →
  password reset lands on the VICTIM's account with YOUR password.
- Register with an existing admin's email, modified casing.

## EXTRACTION LAW
Every bypass must end in DATA: data_extract with the forged identity on
the admin endpoints, dump what the elevated state can see. A bypass that
shows 200 but yields no data is "partial" — say so in the verdict.

## FAILURE MODES
- All forgery variants rejected: server pins the algorithm in code — pivot
  to session-level attacks (signup flows, reset flows, IDOR) which never
  touch JWT verification.
- OTP rate-limited hard: timing side-channel first, response-manipulation
  second, lockout-report third — never fight the rate limiter head-on.
- Signup closed: email_domain variants, invite-code brute via param_brute
  on the invite param, referral flows.
