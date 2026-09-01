# skill: oauth_oidc_chain
title: OAuth/OIDC Chain Playbook
when: oauth,oidc,authorization code,state,pkce,redirect_uri,token exchange,magic link,mfa
tier: domain

## VOIDFORGE TOOL MAP
tools: auth_state_audit (state-machine audit), auth_signup_probe, auth_metadata_poison, redirect_cast

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-oauth-oidc-chain/SKILL.md

---
name: competition-oauth-oidc-chain
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for OAuth, OIDC, redirect flows, state or nonce handling, PKCE, token exchange, refresh logic, claim mapping, and accepted login paths. Use when the user asks to trace redirects, callback parameters, scopes, state, nonce, PKCE, refresh tokens, consent, or explain how an OAuth or OIDC chain turns into accepted identity or privilege. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition OAuth OIDC Chain

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the hard part is proving how an OAuth or OIDC flow is shaped, exchanged, and ultimately accepted.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Map the auth chain in order: entry route, redirect, authorize request, callback, token exchange, refresh, and final accepting service.
2. Record scopes, state, nonce, PKCE material, redirect URIs, and claim-bearing tokens before mutating anything.
3. Separate token possession from actual identity acceptance.
4. Keep browser-visible redirects and backend-visible token exchange in one compact chain.
5. Reproduce the smallest redirect-to-acceptance flow that proves the decisive identity edge.

## Workflow

### 1. Map The Redirect And Token Path

- Record issuer, client ID, redirect URI, authorize parameters, callback parameters, token endpoint, and refresh path.
- Note which values are user-controlled, derived, cached, or validated: `state`, `nonce`, PKCE verifier, audience, scope, or prompt.
- Keep browser redirects, server-side exchanges, and resulting session state tied together.

### 2. Prove Token-To-Identity Acceptance

- Show how code, ID token, access token, or refresh token turns into app session, claims mapping, tenant selection, or accepted privilege.
- Record token claims, expiration, audience, subject, scopes, and the exact accepting app or backend edge.
- Distinguish UI login success from backend authorization success.

### 3. Reduce To The Decisive OAuth Chain

- Compress the result to the smallest sequence: entry request -> redirect -> callback -> token or claim acceptance -> resulting capability.
- Keep one canonical good flow and one minimal mutated flow if a parameter change matters.
- If the task broadens into generic web routing or storage behavior outside the auth chain, switch back to the broader web-runtime skill.

## Read This Reference

- Load `references/oauth-oidc-chain.md` for the redirect checklist, token checklist, and evidence packaging.
- If the hard part is JWT header parsing, claim normalization, key lookup, or token validation confusion after issuance, prefer `$competition-jwt-claim-confusion`.

## What To Preserve

- Redirect URIs, parameters, codes, token claims, scopes, and the accepting service or callback
- The exact point where claims or tokens become accepted app identity
- One minimal replayable redirect-to-acceptance sequence

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-oauth-oidc-chain/references/oauth-oidc-chain.md

# OAuth OIDC Chain Checklist

## First Pass

- Entry route, issuer, client ID, redirect URI, callback route, token endpoint, refresh path
- Authorize parameters: `response_type`, `scope`, `state`, `nonce`, PKCE challenge, audience, prompt
- Browser redirects, backend token exchanges, stored session state, final app acceptance

## Chain To Reconstruct

1. Entry request or login trigger
2. Authorize redirect built
3. Callback parameters received
4. Code or token exchange performed
5. Claims or token accepted by app or backend

## Evidence To Keep Together

- Redirect side: route, parameters, callback values, issuer
- Token side: type, claims, scopes, audience, expiration, subject
- Acceptance side: session created, claims mapped, tenant selected, route unlocked, or privilege granted

## Common Pitfalls

- Stopping at the callback without proving token exchange or claim acceptance
- Treating possession of a token as authorization without showing where it is accepted
- Mixing browser-only redirect evidence and backend-only auth evidence without linking them
