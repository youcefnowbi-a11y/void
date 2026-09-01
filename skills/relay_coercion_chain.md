# skill: relay_coercion_chain
title: Relay & Coercion Chain Playbook
when: relay,coercion,ntlm relay,petitpotam,printerbug,spoolss, responder
tier: domain

## VOIDFORGE TOOL MAP
skills: kerberos_delegation, identity_windows; GAP: relay tools to forge

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-relay-coercion-chain/SKILL.md

---
name: competition-relay-coercion-chain
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for forced-auth coercion, relay chains, target selection, NTLM or related acceptance paths, and coercion-to-privilege transitions. Use when the user asks to trace a coercion primitive, follow a relay path, analyze forced authentication, determine which service accepts relayed auth, or connect a coercion step to resulting privilege, enrollment, or code execution. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition Relay Coercion Chain

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the hard part is proving the full chain from forced authentication to a service that actually accepts the relayed identity.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Split the chain into coercion source, captured auth, relay target, acceptance point, and resulting effect.
2. Record transport, protocol, and service identity at each hop.
3. Separate forced-auth generation from relay success and from downstream privilege.
4. Keep coercion trigger, relay transcript, and accepting service in one evidence chain.
5. Reproduce the smallest coercion-to-acceptance path that proves the decisive edge.

## Workflow

### 1. Map The Coercion Source

- Identify the service, RPC, file path, printer path, WebDAV edge, or protocol trigger that forces authentication.
- Record source host, coerced principal, transport, and any environmental preconditions.
- Keep one compact note of exactly what causes the auth to leave the source.

### 2. Trace The Relay Target

- Record where the authentication lands, how it is forwarded, and which protocol or service consumes it.
- Distinguish capture-only, replay-only, and actual relay acceptance.
- Keep service name, target host, protocol, relay transcript, and acceptance response tied together.

### 3. Reduce To The Decisive Relay Chain

- Compress the result to the smallest sequence: coercion trigger -> relayed auth -> accepted service -> resulting privilege or artifact.
- State clearly whether the decisive weakness lives in the coercion source, the relay target, signing settings, or the accepted downstream service.
- If the path ultimately becomes a certificate-enrollment issue or a pure Kerberos delegation edge, hand off to the tighter specialized skill.

## Read This Reference

- Load `references/relay-coercion-chain.md` for the coercion checklist, relay checklist, and evidence packaging.

## What To Preserve

- Coercion trigger details, source host, coerced identity, target host, accepting service, and resulting effect
- Relay transcripts, error or acceptance responses, and the exact protocol used at each hop
- The smallest replayable coercion-to-acceptance sequence

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-relay-coercion-chain/references/relay-coercion-chain.md

# Relay Coercion Checklist

## Chain Segments

- Coercion source and trigger
- Captured or forwarded authentication
- Relay target and protocol
- Acceptance point and resulting effect

## Reconstruction Order

1. What triggers the source to authenticate
2. Which identity leaves the source
3. Where that authentication is relayed
4. Which service actually accepts it
5. What privilege, enrollment, or artifact results

## Evidence To Keep Together

- Source side: host, service, trigger, protocol, coerced principal
- Relay side: listener, transcript, target host, protocol, response
- Effect side: accepted service, resulting account effect, privilege, or issued artifact

## Common Pitfalls

- Stopping at “forced auth happened” without proving relay acceptance
- Proving relay acceptance without showing what capability it produced
- Mixing several candidate relay targets without isolating the one that actually accepted the relayed auth
