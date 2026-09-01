# skill: stego_media
title: Steganography & Media Playbook
when: stego,steganography,lsb,exif,media,png chunks,hidden data
tier: domain

## VOIDFORGE TOOL MAP
tools: vm_string_dump (strings), file_grep; GAP: stego extractors to forge

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-stego-media/SKILL.md

---
name: competition-stego-media
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for image, audio, video, document, and container steganography. Use when the user asks to inspect metadata, alpha or palette channels, LSBs, thumbnails, appended trailers, QR fragments, transcoding artifacts, or recover a hidden payload from media without blind brute force. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition Stego Media

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the challenge lives inside a media container, hidden channel, or appended payload rather than a conventional crypto blob.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Confirm the real container type, dimensions, duration, codec, and chunk layout before guessing a hidden layer.
2. Check metadata, thumbnails, sidecar files, and appended trailers before deeper signal-domain work.
3. Rank candidate channels by evidence: alpha, palette, LSB, transform-domain residue, frame order, or container slack.
4. Preserve each extracted layer separately so the transform chain stays reproducible.
5. Stop when the hidden payload is reproduced, not merely suspected.

## Workflow

### 1. Establish Container Truth

- Inspect headers, chunk tables, EXIF or document metadata, container indexes, thumbnails, and file size anomalies.
- Compare declared format against observed structure to catch polyglots, appended archives, or malformed trailers.
- Record exact offsets, frame numbers, or channel boundaries that look promising.

### 2. Inspect Candidate Channels

- Check alpha, palette order, RGB or YUV planes, LSBs, spectrogram features, document object streams, or video frame deltas.
- Prefer evidence-driven attempts over brute forcing every transform.
- Note whether the payload is plain bytes, another media layer, compressed data, or an encrypted blob.

### 3. Reconstruct The Hidden Payload Path

- Keep the chain in order: container -> channel or carrier -> extraction -> decompression or decode -> final parse.
- Separate extraction success from final interpretation; a channel hit is not the same as artifact recovery.
- If the problem becomes primarily about cryptography after extraction, hand off to the broader crypto skill.

## Read This Reference

- Load `references/stego-media.md` for the media checklist, channel ranking guide, and evidence packaging.

## What To Preserve

- File structure facts: offsets, chunks, frame numbers, stream names, metadata keys, and trailer size
- Intermediate extractions and the exact command or transform used to produce them
- The final recovered payload and the channel that produced it

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-stego-media/references/stego-media.md

# Stego Media Checklist

## First Pass

- Verify magic bytes, headers, chunk or atom layout, dimensions, duration, sample rate, and metadata
- Check for appended data, malformed trailers, duplicate thumbnails, embedded archives, or sidecar files
- Record entropy shifts, unexpected padding, or container slack regions

## Candidate Channels

1. Alpha or palette anomalies
2. LSBs in image or audio samples
3. Frame-order or delta anomalies in video
4. Document object streams, attachments, or hidden layers
5. Transform-domain residue, QR fragments, or watermark-style carriers

## Evidence Packaging

- Keep one compact block for offsets, channels, and extraction commands
- Keep each extracted stage as a separate file
- Note clearly whether the result is plaintext, another container, compressed data, or ciphertext

## Common Pitfalls

- Jumping into brute force before checking trailers and metadata
- Mixing several partial decode attempts without tracking which channel produced which bytes
- Treating a suspicious pattern as success without reproducing the hidden payload
