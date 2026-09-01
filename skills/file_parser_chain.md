# skill: file_parser_chain
title: File Parser Chain Playbook
when: file parser,xxe,csv injection,polyglot,parser confusion,file upload
tier: domain

## VOIDFORGE TOOL MAP
tools: xxe_probe -> lfi_file_read; upload_webshell; skill: zeroday_hunter

## OPERATING CONTEXT
Grafted from the reverse-skill pack (MIT) — original language preserved (FR/EN agent reads zh fluently).

## SOURCE: CTF-Sandbox-Orchestrator/competition-file-parser-chain/SKILL.md

---
name: competition-file-parser-chain
description: Internal downstream skill for ctf-sandbox-orchestrator. CTF-sandbox workflow for file uploads, imports, previews, archive extraction, format conversion, parser invocation, and deserialization chains. Use when the user asks to inspect an upload or import path, trace archive extraction, preview or converter behavior, explain how a file reaches a parser or deserializer, or connect one uploaded artifact to the decisive backend effect. Use only after `$ctf-sandbox-orchestrator` has already established sandbox assumptions and routed here.
---

# Competition File Parser Chain

Use this skill only as a downstream specialization after `$ctf-sandbox-orchestrator` is already active and has established sandbox assumptions, node ownership, and evidence priorities. If that has not happened yet, return to `$ctf-sandbox-orchestrator` first.

Use this skill when the hard part is following a file from ingress through every parser, extractor, converter, or deserializer boundary that matters.

Reply in Simplified Chinese unless the user explicitly requests English.

## Quick Start

1. Preserve the original upload and every derived artifact separately.
2. Map the chain in order: ingress, temp storage, archive extraction, format conversion, parser call, deserialization, and final consumer.
3. Record filenames, MIME guesses, extensions, temp paths, and parser choices before mutating anything.
4. Separate client-visible validation from backend parser behavior.
5. Reproduce the smallest file-processing chain that yields the decisive branch or artifact.

## Workflow

### 1. Map File Ingress And Derivation

- Record request shape, multipart names, content type, filename, temp paths, upload staging, and storage keys.
- Note every derived artifact: extracted archive member, converted preview, generated thumbnail, temp document, or deserialized object.
- Keep original file and each derivative labeled separately.

### 2. Trace Parser And Conversion Boundaries

- Show which parser, converter, extractor, or deserializer runs at each step.
- Record parser-specific decisions driven by extension, MIME, magic bytes, schema, archive member names, or embedded metadata.
- Distinguish parsing success, preview success, conversion success, and business-logic acceptance.

### 3. Reduce To The Decisive File Chain

- Compress the result to the smallest sequence: upload -> derived artifact -> parser boundary -> resulting effect.
- State clearly whether the decisive weakness lives in archive handling, MIME inference, file conversion, path resolution, or deserialization.
- If the chain becomes mostly a generic async worker problem after enqueue, hand off to the tighter queue or worker skill.

## Read This Reference

- Load `references/file-parser-chain.md` for the ingress checklist, parser checklist, and evidence packaging.

## What To Preserve

- Original uploads, derived files, temp paths, storage keys, parser names, and conversion steps
- The exact boundary where backend behavior diverges from user-visible validation
- One minimal replayable file-processing sequence that reaches the decisive effect

---

## SOURCE: CTF-Sandbox-Orchestrator/competition-file-parser-chain/references/file-parser-chain.md

# File Parser Chain Checklist

## First Pass

- Upload request shape, field names, content type, filename, extension, magic bytes, temp storage
- Archive members, conversion outputs, previews, thumbnails, extracted docs, serialized objects
- Final consumers: parser, converter, renderer, importer, deserializer, worker

## Chain To Reconstruct

1. File ingress accepted
2. Temp or staged artifact created
3. Extraction or conversion performed
4. Parser or deserializer invoked
5. Business-logic effect or artifact produced

## Evidence To Keep Together

- Ingress side: request, filename, MIME, temp path, storage key
- Parser side: tool or library invoked, branch condition, derived artifact, parser choice
- Effect side: rendered output, parsed object, backend branch, worker task, or privilege-bearing result

## Common Pitfalls

- Looking only at the original upload and ignoring derived intermediates
- Treating MIME or extension checks as proof of backend parser choice
- Mixing archive, preview, and deserialization stages without preserving each boundary separately
