# skill: cloud_metadata_path
title: Cloud Metadata Path Playbook
when: cloud metadata,imds,169.254.169.254,ecs,aws metadata,gcp metadata,azure
tier: domain

## VOIDFORGE TOOL MAP
tools: ssrf_probe -> lfi_file_read -> data_extract; skill: cloud_takeover

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-cloud-metadata-path/SKILL.md

---
name: competition-cloud-metadata-path
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for cloud metadata services, instance identity, workload identity, link-local credential paths, role assumption, and metadata-to-privilege trust edges. Use when the user asks to inspect metadata-service access, instance credentials, pod or workload identity, link-local token paths, SSRF-to-metadata escalation, or explain how metadata-derived credentials turn into accepted cloud or control-plane privilege. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition Cloud Metadata Path

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the decisive edge is not just reaching metadata, but proving how metadata-derived identity becomes accepted privilege.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Identify which metadata surface is active: instance metadata, workload identity, node identity, task role, or platform-specific token endpoint.
2. Record the exact reachability path: local process, pod, container, proxy, SSRF surface, or host route.
3. Separate metadata reachability from credential issuance and from downstream privilege acceptance.
4. Keep token format, role identity, scope, and accepting API in compact evidence blocks.
5. Reproduce the smallest metadata-to-accepted-privilege path that proves the challenge edge.

## Workflow

### 1. Map Metadata Reachability

- Record the metadata endpoint, required headers, hop limits, session tokens, workload selectors, or path prefixes.
- Note whether access comes from direct local calls, pod networking, SSRF, sidecar, or host-level routing.
- Keep the reaching surface and the metadata endpoint in one chain.

### 2. Prove Credential Or Identity Issuance

- Show how the metadata response becomes a token, temporary credential, signed identity doc, or platform-specific workload identity.
- Record expiration, role name, subject, audience, issuer, or cloud account mapping that matters downstream.
- Distinguish raw metadata from usable credential material.

### 3. Reduce To The Decisive Trust Path

- Compress the result to the smallest sequence: reaching surface -> metadata call -> credential issued -> accepted cloud or cluster action.
- State clearly whether the weakness lives in reachability, metadata config, role trust, downstream policy, or workload binding.
- If the challenge narrows to RBAC or cluster mutation after credential issuance, switch back to the tighter control-plane skill.

## Read This Reference

- Load `references/cloud-metadata-path.md` for the reachability checklist, token checklist, and evidence packaging.
- If the hard part is first proving a server-side fetch primitive, SSRF reachability, or internal endpoint traversal before metadata itself, prefer `$competition-ssrf-metadata-pivot`.

## What To Preserve

- Metadata endpoints, required headers, reachability path, issued tokens or creds, and accepted APIs
- Role names, audiences, issuers, account bindings, and privilege-bearing actions
- The smallest replayable metadata-to-privilege chain

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-cloud-metadata-path/references/cloud-metadata-path.md

# Cloud Metadata Path Checklist

## First Pass

- Metadata endpoint, hop limit, required headers, session token requirements, link-local route, workload identity binding
- Reaching surface: local process, pod, container, proxy, SSRF, sidecar, or host namespace
- Downstream trust: role assumption, cloud API, cluster API, secret access, or signed identity use

## Chain To Reconstruct

1. Reachable path to metadata established
2. Metadata response or token obtained
3. Usable identity or credential material extracted
4. Downstream API or trust edge accepts it
5. Resulting privilege or artifact confirmed

## Evidence To Keep Together

- Reachability side: route, headers, namespace, container, SSRF primitive, or proxy path
- Identity side: role name, token claims, expiration, audience, issuer, account or project binding
- Acceptance side: API action, resource access, secret read, or spawned workload effect

## Common Pitfalls

- Proving metadata access without proving a useful credential was actually issued
- Proving token issuance without showing which downstream API accepts it
- Mixing node identity and workload identity without showing which one actually drove the privilege edge
