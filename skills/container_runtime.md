# skill: container_runtime
title: Container Runtime Escape Playbook
when: docker,container,escape,privileged,cgroup,namespace,runtime
tier: domain

## VOIDFORGE TOOL MAP
skill: cloud_takeover (core); tools: shell_session, file_grep

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-container-runtime/SKILL.md

---
name: competition-container-runtime
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for live container runtime analysis, mounted secrets, sidecars, namespaces, init containers, entrypoint drift, and route-to-container resolution. Use when the user asks why a live container differs from manifests, where a mounted secret is consumed, how a sidecar or init container changes runtime state, or which route resolves to which live container. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition Container Runtime

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the challenge is really about what the live container or pod is doing now, not what the checked-in manifest claims it should do.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Split intent from reality: manifest, image, startup, live mount, live route, live process.
2. Map host -> proxy -> container or pod -> mounted volume -> consuming process.
3. Keep secrets, rendered config, init output, and sidecar output separate from static manifests.
4. Prove one minimal live path from mounted or injected state to reachable behavior.
5. Reproduce the effect with the smallest runtime-specific chain.

## Workflow

### 1. Map The Live Runtime

- Compare compose or kube manifests against running containers, pods, mounted volumes, env, sidecars, init containers, and entrypoints.
- Identify which process actually consumes the mounted secret, rendered config, or shared volume output.

### 2. Trace Route And Mount Boundaries

- Map virtual host, reverse proxy, service, container port, filesystem mount, and runtime-generated file paths together.
- Record whether the decisive state is image-baked, env-injected, mounted later, or written by an init/sidecar process.

### 3. Report The Runtime Deviation

- State the earliest point where live runtime diverges from checked-in intent.
- Keep one compact evidence chain from manifest or compose intent to live consumer behavior.

## Read This Reference

- Load `references/container-runtime.md` for the runtime checklist, mount-chain checklist, and common live-vs-static pitfalls.
- If the hard part is kube API permissions, service-account trust, RBAC edges, admission mutations, or controller-created workload drift, prefer `$competition-k8s-control-plane`.
- If the hard part is Host-header routing, path-prefix rewriting, or route-to-service mapping across nodes, prefer `$competition-runtime-routing`.
- If the hard part is proving container-to-host crossover, kernel attack-surface preconditions, or stable escape primitives, prefer `$competition-kernel-container-escape`.
- If the hard part is replaying Linux secrets, socket trust edges, or host-to-host pivots after container foothold, prefer `$competition-linux-credential-pivot`.

## What To Preserve

- Compose/Kubernetes fragments tied to live mounts or routes
- Container IDs, pod names, mount paths, sidecar outputs, rendered config paths, and consuming processes
- The exact route or file path that becomes reachable only at runtime

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-container-runtime/references/container-runtime.md

# Container Runtime Checklist

## Compare Intent vs Reality

Inspect side by side:

- compose or kube manifests
- image layers and entrypoints
- init containers
- sidecars
- mounted volumes
- runtime env
- live processes and listeners

## Trace The Mount Chain

- who writes the file
- where it is mounted
- which process reads it
- which route or behavior depends on it

## High-Value Runtime Deviations

- rendered secrets written to shared volumes
- init output consumed by the main container
- sidecar-generated config or credentials
- runtime-only env values not visible in checked-in manifests
- reverse-proxy routing that exposes an internal path only after startup

## Evidence To Keep

- one compact block for manifest intent
- one compact block for live mounts, processes, or rendered files
- one compact block for the route or behavior reached only because of runtime state

## Common Pitfalls

- treating checked-in manifests as deployment truth
- stopping at “secret is mounted” without proving the consuming process
- missing sidecar or init output because only the main service was inspected
