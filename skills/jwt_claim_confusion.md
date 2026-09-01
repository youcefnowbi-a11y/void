# skill: jwt_claim_confusion
title: JWT Claim Confusion Playbook
when: jwt,claim,confusion,alg none,key confusion,kid,jku,issuer,audience
tier: domain

## VOIDFORGE TOOL MAP
tools: jwt_analyst -> jwt_forge_replay (alg:none / key confusion / claim escalation)

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-jwt-claim-confusion/SKILL.md

---
name: competition-jwt-claim-confusion
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for JWT, JWS, and JWE validation paths, header parsing, key selection, claim acceptance, audience and issuer checks, role derivation, and token-to-identity confusion bugs. Use when the user asks to inspect JWT headers or claims, key lookup, `kid` handling, `alg` confusion, audience or issuer validation, role claims, or explain how a token becomes accepted identity or privilege. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition JWT Claim Confusion

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the decisive bug is not just "there is a JWT," but how headers, claims, and key selection turn into accepted identity.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Split the token path into parse, key lookup, signature or decryption, claim validation, and final acceptance.
2. Record header fields, claims, key source, issuer, audience, and role mapping before mutating anything.
3. Separate possession of a token from the exact service that accepts it.
4. Keep parser behavior, trust policy, and resulting app session or privilege in one chain.
5. Reproduce the smallest token-to-acceptance flow that proves the decisive confusion.

## Workflow

### 1. Map Header And Key Selection

- Record header fields such as `alg`, `kid`, `typ`, `cty`, `jku`, or embedded key material when present.
- Note where keys come from: static config, JWKS, local file, cache, or dynamic lookup.
- Keep token parser, key selection path, and validation mode tied together.

### 2. Prove Claim-To-Privilege Acceptance

- Show how subject, audience, issuer, tenant, scope, role, or custom claims become app session, route access, or backend privilege.
- Record expiration, not-before, clock skew, issuer matching, audience matching, and claim normalization behavior.
- Distinguish token parse success from actual authorization success.

### 3. Reduce To The Decisive JWT Path

- Compress the result to the smallest sequence: token supplied -> parser or key path taken -> claim accepted -> resulting capability.
- Keep one canonical accepted token path and one mutated token path if confusion or bypass depends on a delta.
- If the task broadens into a larger OAuth redirect chain, hand back to the tighter OAuth skill.

## Read This Reference

- Load `references/jwt-claim-confusion.md` for the header checklist, claim checklist, and evidence packaging.

## What To Preserve

- Raw headers, claims, key source, JWKS or local key path, and the accepting service
- The exact validation or normalization step that turns the token into accepted identity
- One minimal replayable token-to-acceptance sequence

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-jwt-claim-confusion/references/jwt-claim-confusion.md

# JWT Claim Confusion Checklist

## First Pass

- Token form: JWS, JWE, nested token, detached signature, or bearer wrapper
- Header fields: `alg`, `kid`, `typ`, `cty`, `jku`, x5u-like references, embedded keys
- Claim fields: `iss`, `aud`, `sub`, `exp`, `nbf`, `iat`, tenant, role, scope, custom privilege claims

## Validation Chain To Reconstruct

1. Token parser invoked
2. Key source selected
3. Signature or decryption step performed
4. Claim validation and normalization applied
5. App session or privilege accepted

## Evidence To Keep Together

- Header side: fields, key source, lookup behavior, cache or remote key material
- Claim side: issuer, audience, subject, roles, scopes, time claims, normalization rules
- Acceptance side: session cookie, route unlock, backend action, or privilege-bearing claim usage

## Common Pitfalls

- Stopping at successful decode without proving authorization acceptance
- Focusing on one claim without showing the whole validation chain
- Ignoring key lookup or normalization behavior that matters more than the raw claim value
