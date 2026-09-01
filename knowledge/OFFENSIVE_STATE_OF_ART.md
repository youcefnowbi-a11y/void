# VOIDFORGE :: OFFENSIVE STATE OF THE ART — gap-matrix research & adoption

*Last-mission audit: how the professional ecosystem does zero-days, vulnerability
discovery, and C2 — what VOIDFORGE adopted from it, and what remains frontier.*

---

## 1. How the real world finds vulnerabilities

**Template-driven scanning (ProjectDiscovery lineage).** subfinder → httpx →
katana → nuclei is the industry pipeline. Nuclei's power is not the scanner —
it is the *community template corpus* (8000+ YAML signatures, CVE-mapped,
community-reviewed). Lesson: a scanner is a filesystem, not a program.
**VOIDFORGE has**: nuclei_scan (template engine), wayback_urls, subdomain_enum,
param_brute (arjun-style diffing). **Adopted tonight**: nothing new needed here —
but doctrine now orders fuzz findings into template-shaped strikes.

**Response-diff fuzzing (ffuf / Turbo Intruder / Burp).** The web-fuzzing
world's core oracle is *response differencing against a baseline*: length,
status, timing, reflection. Real operators calibrate per-target and kill noise
with baseline clustering. **VOIDFORGE had**: 5-oracle mutation fuzzing with
online z-score σ-floor (already ahead of most OSS). **Adopted tonight**: a
*learned seed corpus* — payloads that survived one run seed the next
(`reports/fuzz_seeds.json`, `fuzz_attack_surface(seeds=…)`), the web-world
analogue of AFL++'s coverage feedback: the fuzzer remembers what the target
answers to, so each round starts smarter. Plus `crash_triage_next` now emits
`fuzz_seeds` directly — triage output is machine-consumable, closing the
discover → rank → re-discover loop.

**Race conditions (Turbo Intruder single-packet attack).** The state of the
art: pre-open TCP connections, synchronize at the *last byte*, fire as one
packet so the requests interleave server-side within the race window.
**VOIDFORGE had**: nothing. **Adopted tonight**: `race_smash` — barrier-
released raw-socket bursts (stdlib cannot do last-byte sync; the barrier +
pre-established connections is the honest stdlib approximation), with
double-processing confirmation via `success_pattern` across rounds.

**HTTP request smuggling (PortSwigger desync research).** Front/back proxy
framing disagreement (CL.TE, TE.CL, TE.TE) is detected by differential
*poison-follower* testing: smuggle a request prefix, then send a clean
follower and observe whether it inherits the poison. **VOIDFORGE had**:
nothing. **Adopted tonight**: `smuggle_probe` — raw-socket two-request
technique, per-variant poisoned-follower detection, honest "inconclusive"
accounting.

**Prototype pollution.** Query-string bracket/dot variants plus JSON-merge
`__proto__` injection, confirmed by *gadget checks* — a second endpoint whose
behavior changes if pollution landed. **VOIDFORGE had**: nothing.
**Adopted tonight**: `proto_pollute` (3 query vectors + JSON merge +
gadget_check with canary leak detection).

**XXE.** External entity ladders: classic `file://`, PHP base64 filter wrapper,
parameter entities. Confirmation via OS markers (`root:`, `USER=`). **Adopted
tonight**: `xxe_probe`.

**Open redirects.** Parameter × payload matrix (`//host`, `/\host`,
`https:host`, `@host`, `///host`) with 3xx Location confirmation — needs raw
socket access because HTTP libraries normalize or hide headers. **Adopted
tonight**: `redirect_cast` (12 params × 6 bypass shapes, raw header read).

## 2. How the real world weaponizes known CVEs (n-days)

**Metasploit's discipline**: every module declares `Platform`/`Arch`/`Rank`
and refuses to run against the wrong target — the *stack-match gate*. Public
PoC hubs (Exploit-DB, GitHub) are the feedstock; CISA KEV says what is being
*used in the wild*.
**VOIDFORGE had**: NVD intel + GitHub PoC hunt + sandboxed execution — the
chain, but no gate. **Adopted tonight**: `nday_exploit` now cross-matches CVE
description product tokens against the target's own response surface (and any
operator-supplied `stack` from web_fingerprint) before staging, adds the
Exploit-DB search reference, and reports `stack_match` in the verdict. A PoC
fired at the wrong stack is worse than no PoC — it wastes the strike budget
and teaches the agent nothing.

## 3. How real C2 keeps beacons alive

**Cobalt Strike / Sliver / Mythic tradecraft**: beacon sleeps with *jitter*
(fixed sleep is a detection signature), UA/fingerprint rotation, exponential
backoff on failures (a beacon backs away, it never hammers), session identity
across check-ins, and liveness as a *rate*, not a binary.
**VOIDFORGE had**: `shell_session` — stateless command rounds, no discipline.
**Adopted tonight**: `c2_pulse` — ±40% jittered heartbeats, rotating real UA
fingerprints, exponential backoff on 5xx/timeouts, session id propagation,
and a liveness *percentage* verdict with mean RTT. A shell that answers 3/6
beats is not a shell; it is a rumor. The doctrine now chains
`upload_webshell → shell_session → c2_pulse`.

## 4. JWT attack matrix (jwt_tool's grammar)

jwt_tool's full matrix: alg:none (×casings), RS→HS confusion, kid injection,
**jku injection, x5u injection** — the header-controlled key-loading variants
where the server fetches key material from an attacker-served JWKS URL.
**VOIDFORGE had**: all but jku/x5u. **Adopted tonight**: both variants, gated
on operator-hosted JWKS parameters (`key_url`, `key_secret`), acceptance
proving header-controlled key loading.

## 5. The agentic-pentest research wave (PentestGPT, HackingBuddyGPT, CAI)

Published agentic-pentest systems converge on: phase-state machines, a
*reflection after each finding*, tool schemas exactly as expressive as the
model can use, and explicit "confirmed but unexploited = unfinished" doctrine.
**VOIDFORGE already had**: MCTS brain, swarm specialists with strike briefs,
self-correcting tool contract, doctrinal strike law. **Adopted tonight**: the
arsenal-integrity CI suite now *enforces* the schema/brain/doctrine contract —
the thing those research systems lack is precisely the guarantee that their
model can always call every tool.

## 6. What was adopted (tool ledger)

| Tool / upgrade | Class | Tradition |
|---|---|---|
| `race_smash` | race conditions | Turbo Intruder |
| `smuggle_probe` | request smuggling | PortSwigger desync research |
| `proto_pollute` | prototype pollution | gadget-hunting practice |
| `xxe_probe` | XXE | entity ladders |
| `redirect_cast` | open redirects | param × payload matrices |
| `c2_pulse` | C2 beacon discipline | CS/Sliver/Mythic |
| jku/x5u in `jwt_forge_replay` | JWT key injection | jwt_tool matrix |
| `nday_exploit` stack gate + EDB ref | n-day precision | Metasploit platform discipline |
| fuzz seed corpus + triage `fuzz_seeds` | learning fuzzer | AFL++ feedback (web analogue) |
| integrity CI + param-aware doctrine guard | agent-tool contract | agentic-pentest lessons |

**Arsenal: 62 tools across 12 domains.** MCTS reachable: 55/62; 7 whitelisted
as genuinely context-dependent (session files, live primitives, orchestration).

## 7. The frontier — what we deliberately did NOT do tonight

- **Last-byte sync single-packet race** requires raw TCP segmentation control
  (scapy-level). The barrier approximation is honest; the full technique is a
  privilege-level upgrade, not a tool rewrite.
- **OOB exfiltration channels** (XXE/SSRF blind confirmation via DNS/HTTP
  collaborator) need an operator-hosted listener; the tools probe in-band and
  say so.
- **Full coverage-guided binary fuzzing** (AFL++ harness) is a different
  discipline — VOIDFORGE's range is web/API; the seed-corpus loop is the web
  analogue, not a substitute.
- **Payload obfuscation / AV evasion layers** are a deployment-stage concern,
  not a discovery concern — deliberately out of scope for this mission.

*Mission complete — the gap matrix is closed on every class the state of the
art considers core web/API offense, and the fuzzer now learns between rounds.*
