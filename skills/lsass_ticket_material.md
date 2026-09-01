# skill: lsass_ticket_material
title: LSASS & Ticket Material Playbook
when: lsass,mimikatz,krbtgt,ticket,ntds,secretsdump,windows credentials
tier: domain

## VOIDFORGE TOOL MAP
tools: shell_session (post-exploit); skills: dpapi_chain, kerberos_delegation

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-lsass-ticket-material/SKILL.md

---
name: competition-lsass-ticket-material
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for LSASS-resident secrets, Windows logon sessions, Kerberos ticket caches, DPAPI-backed material, SSP artifacts, and replayable credential extraction. Use when the user asks to inspect LSASS memory, recover tickets or logon sessions, trace DPAPI or SSP material, distinguish which credential artifacts are replayable, or connect host-resident credential material to an accepted pivot or privilege edge. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition LSASS Ticket Material

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the decisive host artifact lives in LSASS, ticket caches, or adjacent credential material and the hard part is proving what is replayable.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Separate raw credential material from actually usable replay edges.
2. Record logon session, LUID, ticket cache, package, account, and target service before broad conclusions.
3. Keep host artifact, extracted secret, replay attempt, and resulting acceptance in one chain.
4. Distinguish password, hash, ticket, DPAPI secret, SSP residue, and token by where each can actually be used.
5. Reproduce the smallest host-artifact-to-accepted-privilege path that proves the decisive edge.

## Workflow

### 1. Map LSASS And Adjacent Credential State

- Record logon sessions, LUIDs, ticket caches, package names, SSPs, DPAPI context, and any service-account material tied to the active path.
- Note whether the decisive value is a TGT, service ticket, delegated ticket, DPAPI secret, plaintext, hash, or package-specific secret.
- Keep host source, account context, and cache location tied together.

### 2. Prove Replay Or Acceptance

- Show where the extracted material is accepted: SMB, WinRM, service ticket use, DPAPI unwrap, Schannel, or another host or service edge.
- Record SPN, target host, logon session, ticket flags, encryption type, and resulting privilege or token change.
- Distinguish material that is present from material that is actually replayable in this path.

### 3. Reduce To The Decisive Credential Chain

- Compress the result to the smallest sequence: host artifact -> extracted material -> accepted replay or unwrap -> resulting capability.
- State clearly whether the decisive edge lives in LSASS memory, ticket cache reuse, DPAPI context, or accepting service behavior.
- If the task broadens into full host-to-host pivoting, hand back to the tighter Windows pivot skill.

## Read This Reference

- Load `references/lsass-ticket-material.md` for the session checklist, replay checklist, and evidence packaging.
- If the task is specifically about DPAPI masterkeys, protected blobs, browser or vault stores, or proving which recovered DPAPI secret is accepted, prefer `$competition-dpapi-credential-chain`.

## What To Preserve

- LUIDs, session IDs, ticket types, SPNs, encryption types, package names, and cache or memory source
- The exact accepting host or service and the resulting privilege or logon effect
- One minimal host-artifact-to-replay sequence that proves the edge

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-lsass-ticket-material/references/lsass-ticket-material.md

# LSASS Ticket Material Checklist

## First Pass

- Logon sessions, LUIDs, package names, ticket caches, SSP artifacts, DPAPI context, account names
- Material types: plaintext, NTLM hash, TGT, service ticket, delegated ticket, DPAPI secret, gMSA material
- Acceptance candidates: SMB, WinRM, service ticket use, Schannel, DPAPI unwrap, service logon

## Chain To Reconstruct

1. Host or memory artifact located
2. Credential or ticket material extracted
3. Replay or unwrap path identified
4. Service or host accepts it
5. Resulting logon, token, or privilege confirmed

## Evidence To Keep Together

- Host side: process, dump or cache source, LUID, package, account
- Material side: type, ticket flags, SPN, encryption, DPAPI context, cache location
- Acceptance side: target service, target host, resulting session or privilege change

## Common Pitfalls

- Treating every extracted secret as replayable without proving an accepting service
- Mixing several logon sessions and ticket caches into one vague story
- Describing ticket presence without tying it to a concrete privilege or pivot edge
