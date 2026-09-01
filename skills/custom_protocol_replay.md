# skill: custom_protocol_replay
title: Custom Protocol Replay Playbook
when: custom protocol,replay,binary protocol,raw socket,protocol fuzz
tier: domain

## VOIDFORGE TOOL MAP
tools: replay_mutate, har_dissect; skill: attack_chain_pack

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-custom-protocol-replay/SKILL.md

---
name: competition-custom-protocol-replay
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for custom binary or text protocol recovery, handshake reconstruction, framing, sequence control, checksums, stateful replay, and accepted-session reproduction. Use when the user asks to decode an unknown protocol, recover custom framing, build a replay harness, satisfy sequence or checksum rules, replay a captured session, or prove the smallest message order that reaches an accepted branch. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition Custom Protocol Replay

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the hard part is not merely naming the protocol, but reproducing the exact message order and state needed for acceptance.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Identify client and server roles, session boundaries, and reset conditions before decoding field semantics.
2. Recover framing, lengths, delimiters, sequence numbers, checksums, nonces, and state transitions before broad replay attempts.
3. Keep one canonical transcript of a successful exchange.
4. Change one field or one message at a time while replaying.
5. Reproduce the smallest accepted conversation that proves the decisive branch.

## Workflow

### 1. Map The Session State Machine

- Identify handshake, negotiation, authentication, keepalive, command, and teardown phases.
- Record which fields are static, which are derived, and which depend on prior messages.
- Keep message order, direction, and timing tied to the same session identity.

### 2. Recover Framing And Integrity

- Reconstruct lengths, delimiters, type bytes, checksums, MACs, counters, compression, or encryption boundaries.
- Distinguish transport framing from application-level framing.
- Note exactly where server acceptance changes when one field or step is mutated.

### 3. Build The Minimal Replay Harness

- Reduce the path to the smallest transcript that reaches the accepted state, parser branch, command effect, or artifact.
- Preserve both the original captured sequence and the replayed minimal sequence.
- If the problem is mainly generic PCAP or stream decoding with no stateful replay requirement, switch back to the broader PCAP skill.

## Read This Reference

- Load `references/custom-protocol-replay.md` for the state-machine checklist, transcript checklist, and evidence packaging.

## What To Preserve

- Canonical transcript, message types, field boundaries, checksums, counters, and session identifiers
- Original capture slices and the replay harness inputs that produce acceptance
- The exact mutation that flips the protocol from rejected to accepted, or vice versa

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-custom-protocol-replay/references/custom-protocol-replay.md

# Custom Protocol Replay Checklist

## Transcript First

- Establish roles, stream IDs, ports, session resets, handshake boundaries, and successful transcript examples
- Separate transport segmentation from application messages
- Record retransmits or duplicate messages so they do not pollute the protocol model

## Recovery Order

1. Framing and message boundaries
2. Direction and sequence state
3. Integrity fields: checksum, MAC, counter, nonce, or signature
4. Compression, encoding, or crypto boundary
5. Accepted vs rejected transcript deltas

## Evidence To Keep Together

- Message identity: type, offset, length, direction, sequence, or delimiter
- Acceptance state: prior message dependency, negotiated value, checksum, or nonce source
- Replay proof: minimal transcript, harness input, and server response or side effect

## Common Pitfalls

- Trying broad replay before framing and state dependencies are understood
- Mixing messages from separate sessions into one replay model
- Claiming protocol recovery without producing an accepted replay or meaningful state transition
