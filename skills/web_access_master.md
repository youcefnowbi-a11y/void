# skill: web_access_master
title: Initial Access — Web Targets (WSTG × VOIDFORGE doctrine)
when: web,http,site,url,target,access,exploit,pentest,audit,attack,app,application

## OPERATING PRINCIPLE
Never scan blind. Every request either answers a question or earns a strike.
Detection tools are SCOUTS; a confirmed vulnerability you did not exploit is
an unfinished mission. Escalate: surface → parameter → primitive → data.

## CHAIN (follow, adapt to what you observe)
1. web_fingerprint(url) — stack, headers, WAF hints. Note the server line
   (nginx/uvicorn/IIS/express) — it decides your payload grammar later.
2. waf_detect(url) — if WAF present, note which; encoding strategy changes.
3. js_mine_site(site) — every bundle, source maps, chunks. JWTs, api keys,
   hidden routes land here. Tokens found → jwt_analyst immediately.
4. endpoint_oracle(base, paths=[admin,api,.env,graphql,actuator,...]) —
   401 = exists-locked (come back with credentials), 200 = open, 404 = gone.
5. dir_brute(base) + wayback_urls(domain) — forgotten endpoints are soft doors.
6. SPA alive? spa_crawl(url) — captured requests show the real API grammar.
7. NOW branch on what you observed — see DECISION MATRIX below.

## DECISION MATRIX (observed → strike)
- JWT anywhere → jwt_analyst → jwt_forge_replay (alg:none casings, RS→HS if
  public key found in JS, kid traversal, jku/x5u with hosted JWKS) → replay
  against every endpoint that answered 401.
- SQL echo/timing on a param → sqli_probe_param → sqli_union_dump →
  sqli_blind_extract if UNION never renders. Use dbms hints from fingerprint.
- Input reflected anywhere → ssti_detect_rce (fingerprint ladder first:
  Jinja2 vs Twig vs Freemarker changes the payload grammar).
- OS command surface (ping, lookup, export) → cmd_exec_probe (separator
  matrix, os_flavor from fingerprint) → shell_exec → upload_webshell if an
  upload exists → c2_pulse for beacon liveness.
- Sequential or base64 IDs → idor_enum / idor_b64_walk (differential bodies).
- Upload endpoint → upload_webshell (bypass matrix: extensions, MIME, magic
  bytes, double-ext, .htaccess) → shell_session.
- One-shot-only actions (coupon, vote, withdraw, reset) → race_smash with
  success_pattern; barrier-released burst, 3 rounds.
- Proxy stack in fingerprint (nginx front, Varnish, Cloudflare Workers) →
  smuggle_probe (CL.TE / TE.CL / TE.TE) — high impact, low noise.
- XML in (SAML, SOAP, RSS, .xml/.svg upload, import) → xxe_probe —
  classic + php filter + parameter entities; hunt /etc/passwd, .env, clouds metadata.
- Redirect params on auth flows → redirect_cast (12 params × 6 bypass shapes).
- JSON merge / config endpoints → proto_pollute (query + JSON __proto__,
  gadget_check on a second endpoint).
- Graphql found → graphql_introspect → field suggestion fuzzing → auth bypass.
- Supabase/Firebase markers in JS → cloud_takeover skill (skill_load).
- Fuzz when nothing confirms: fuzz_attack_surface (5 oracles, learned seeds)
  → crash_triage_next → follow its mapped next_tool verdict.

## AUTH LADDER (when login exists)
anon baseline → register via auth_signup_probe (mint session) →
otp_brute if OTP 4-6 digits with rate-limit gaps → auth_metadata_poison
(privileged-looking user_metadata) → replay captured tokens (replay_mutate)
against role-gated endpoints → idor across object ids with BOTH sessions.

## EXTRACTION LAW
endpoint_oracle tells you IF something exists. data_extract / api_sweep /
data_dump_paginated GET the data. NEVER stop at "the endpoint exists".

## FAILURE MODES
- 403 everywhere: retry with forged role claims before concluding.
- UNION renders nothing: switch to blind extract immediately, do not grind.
- WAF blocks payloads: change encoding per WAF (see payload_grammar skill).
- Rate limited: the pacer adapts; reduce concurrency, keep probing — patience is a weapon.
