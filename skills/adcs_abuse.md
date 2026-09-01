# skill: adcs_abuse
title: AD CS Certificate Abuse (ADCS)
when: adcs,certificate,esc1,esc2,esc3,esc4,certipy,cert template,enrollment
tier: domain

## VOIDFORGE TOOL MAP
NEW DOMAIN (arsenal gap): pairs with kerberos_delegation; request/craft certs then PKINIT

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-ad-certificate-abuse/SKILL.md

---
name: competition-ad-certificate-abuse
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for AD CS, certificate templates, enrollment rights, EKUs, SAN controls, PKINIT, certificate mapping, and cert-based privilege paths. Use when the user asks about ESC-style abuse, certificate templates, enrollment agents, EKUs, SAN or subject controls, smartcard or PKINIT logon, CA policy, or how an issued cert turns into accepted privilege. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition AD Certificate Abuse

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the decisive identity edge is certificate-based and the hard part is proving how a template or CA policy turns into accepted privilege.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Identify the CA, template, enrolling principal, and accepting service before diving into every certificate detail.
2. Separate template enrollability from cert-based authentication or privilege acceptance.
3. Record EKUs, subject or SAN controls, issuance requirements, enrollment rights, and mapping behavior in compact blocks.
4. Tie the issued cert to one accepted path: PKINIT, Schannel, LDAPS, WinRM, or another mapped service.
5. Reproduce the smallest certificate issuance-to-acceptance chain that yields the decisive privilege.

## Workflow

### 1. Map CA And Template Trust

- Record CA configuration, template name, enrollment permissions, manager approval, authorized signatures, EKUs, subject requirements, and SAN behavior.
- Note whether the path depends on alternate subject names, `UPN`, DNS names, enrollment agent behavior, or template supersedence.
- Keep principal, template, and issuance policy tied together.

### 2. Prove Cert-To-Privilege Acceptance

- Show how the issued certificate is mapped or accepted: PKINIT, smartcard logon, Schannel auth, service mapping, or explicit certificate mapping.
- Record serial, subject, SAN, EKU, validity, and the exact service or domain edge that accepts it.
- Distinguish certificate issuance from the separate step where privilege is actually granted.

### 3. Reduce To The Decisive Abuse Chain

- Compress the path to the smallest sequence: enrollment right or misconfig -> issued cert -> accepted mapping -> resulting privilege.
- State clearly whether the weakness lives in template config, CA policy, mapping logic, relay path, or enrollment rights.
- If the task is really about delegation or ticket transformation after PKINIT, switch back to the tighter Kerberos skill.

## Read This Reference

- Load `references/ad-certificate-abuse.md` for the AD CS checklist, template checklist, and evidence packaging.

## What To Preserve

- CA names, template names, rights, EKUs, issuance flags, SAN controls, and mapping details
- Issued certificate fields, serials, subjects, SANs, and the accepting service or logon path
- The smallest reproducible enrollment-to-privilege chain

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-ad-certificate-abuse/references/ad-certificate-abuse.md

# AD Certificate Abuse Checklist

## Core Surfaces

- Enterprise CA configuration, issuance policy, enrollment permissions, manager approval, authorized signatures
- Template flags, EKUs, subject or SAN controls, enrollment agent settings, superseded templates
- PKINIT, smartcard logon, Schannel, certificate mapping, relay paths, accepting services

## Abuse Chain To Reconstruct

1. Principal with enrollment or relay path identified
2. Template or CA weakness established
3. Certificate issued with exploitable identity material
4. Service or logon path accepts the cert
5. Resulting privilege or account effect confirmed

## Evidence To Keep Together

- Template side: name, rights, EKUs, flags, SAN controls, issuance requirements
- Cert side: subject, SAN, serial, validity, issuer, thumbprint
- Acceptance side: PKINIT or service mapping, target account, resulting privilege

## Common Pitfalls

- Stopping at template misconfiguration without proving cert issuance
- Proving issuance without proving where the cert is actually accepted
- Mixing certificate abuse with Kerberos delegation when the decisive edge is the template or mapping itself
