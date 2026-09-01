# skill: linux_credential_pivot
title: Linux Credential Pivot Playbook
when: linux,credential,ssh keys,authorized,bash history,crontab,linux pivot
tier: domain

## VOIDFORGE TOOL MAP
tools: shell_session -> file_grep -> shell_exec; skill: privesc_linux

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-linux-credential-pivot/SKILL.md

---
name: competition-linux-credential-pivot
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for Linux credential artifacts, service tokens, SSH material, cloud and container secrets, socket-level trust, and host-to-host pivot chains. Use when the user asks to trace Linux auth artifacts, accepted token or key replay, socket or service-account trust edges, sudo or capability abuse, or explain lateral movement across Linux challenge nodes. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition Linux Credential Pivot

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the decisive edge is Linux credential material and where that material is accepted.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Separate credential storage from accepted privilege.
2. Record user, process, namespace, socket, key file, and service trust boundary before conclusions.
3. Keep artifact recovery, replay path, and resulting capability in one chain.
4. Distinguish local escalation from lateral host pivot.
5. Reproduce one minimal artifact-to-accepted-access path.

## Workflow

### 1. Map Credential And Trust Artifacts

- Record SSH keys, agent sockets, kubeconfigs, cloud tokens, service-account secrets, env vars, config files, and process memory clues.
- Note sudoers rules, capabilities, setuid binaries, systemd unit context, and namespace boundaries.
- Keep each artifact tied to owner, scope, and expected accepting service.

### 2. Prove Replay And Pivot

- Show where key, token, socket, or secret is accepted: SSH, API, Unix socket, container runtime, or control-plane endpoint.
- Record host target, protocol, principal, and resulting session or privilege.
- Distinguish authentication success from useful capability gain.

### 3. Reduce To Decisive Linux Pivot Chain

- Compress to: recovered artifact -> accepted replay path -> pivot host or privilege transition -> resulting capability.
- State whether root cause is weak key handling, token leakage, socket trust, sudo or capability abuse, or namespace crossover.
- If the chain pivots into kernel exploit boundaries, hand off to kernel container escape skill.

## Read This Reference

- Load `references/linux-credential-pivot.md` for artifact checklists, replay matrix, and evidence packaging.

## What To Preserve

- Artifact path, owner, scope, accepting service, and resulting principal
- Exact pivot order with protocol and target host or namespace
- One minimal replayable chain proving capability gain

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-linux-credential-pivot/references/linux-credential-pivot.md

# Linux Credential Pivot Checklist

## First Pass

- SSH keys, agent sockets, kubeconfigs, cloud tokens, service-account secrets
- Env vars, config files, systemd units, sudoers, capabilities, setuid binaries
- Namespace context, container runtime sockets, control-plane endpoints

## Chain To Reconstruct

1. Credential artifact recovered
2. Accepting service identified
3. Replay or auth path executed
4. New session, token, or privilege gained
5. Pivot or lateral effect reproduced

## Evidence To Keep Together

- Artifact side: file or socket path, owner, scope, lifetime
- Replay side: target host, service, protocol, principal
- Effect side: privilege change, new shell, control-plane action, lateral movement

## Common Pitfalls

- Listing secrets without proving acceptance on a target service
- Mixing local privilege escalation and lateral movement in one vague chain
- Ignoring namespace or socket ownership context
