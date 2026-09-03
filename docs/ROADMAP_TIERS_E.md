# VOIDFORGE :: Roadmap — the five vision tiers as concrete chantiers

*Drawn from docs/VISION_BIG_SYSTEMS.md (the five shared laws of apex
platforms). Each chantier lists scope, touched files, guard tests, and
acceptance criteria. Order recommended by the maturity scorecard: E1 is
the only ✖ law, then the ◐ laws harden in sequence.*

## E1 — Malleable transport profiles (law 4: detection surface = config)

**Why first**: the only ✖ on the scorecard; per-campaign traffic SHAPE is
what separates us from a fixed fingerprint; config-driven, no new
architecture.

**Scope**
- `config/transport.yaml` gains `transport.profile.<name>` blocks:
  header sets + order (extra headers ride as ordered list), Accept /
  Referer / Origin grammar per target category, jitter envelope
  (min/max factor on _roe pacing), per-profile UA-family lock.
- `tools/_transport.py`: profile resolution — campaign declares
  `profile=strict|mobile|api-client|custom` (default derived from
  target category); profile wins over op_identity defaults for ITS
  headers, identity still owns UA/language/burn (single writer rule:
  profile may SET headers, never override UA after identity).
- `core/op_identity.py`: profile id stamped into the identity record
  (burn keeps the profile, rotates the accent).
- Per-campaign profile hash logged in the report ROE header (what shape
  did we present — data, not a fingerprint).

**Files**: `tools/_transport.py`, `core/op_identity.py`,
`config/transport.yaml` (example profiles), `core/report.py` (ROE row),
tests.

**Guard tests**: profile resolution precedence (profile > identity >
pool); header ORDER preserved as declared; burn keeps profile, rotates
accent; two campaigns with different profiles produce disjoint header
sets; malformed profile → honest fallback to default, no crash.

**Acceptance**: two live fetches with profile A vs B emit disjoint
ordered header sets; ROE header shows `| Traffic profile | <name> <hash> |`.

## E2 — The unified capability vault (law 1: loader + vault)

**Why**: plays, forged_* tools and skills are three separate stores today
with three lifecycles; Equation's law is ONE vault, addressed one way.

**Scope**
- `core/capability_vault.py`: single facade — `recall(kind, target)`,
  `deposit(kind, payload)`, `score(handle)`; backs learned_plays,
  skill registry and forged registry behind one read path.
- Reuse scoring unified: plays `uses`, forged tool invocations, skill
  loads — one maturity score per capability, surfaced in prompt blocks
  (FIELD MANUAL / skill lists) sorted by score.
- Versioned deposits (capability id + content hash + mission provenance).
- Atomic writes (existing pattern) + gitignored store unchanged.

**Files**: `core/capability_vault.py` (new), thin adapters in
`core/learned_plays.py`, `core/skills.py`, `tools/__init__.py` (forged),
`core/agent.py` (prompt blocks read through the facade).

**Guard tests**: facade roundtrip for all three kinds; score unification
(uses bump visible through score); provenance recorded; prompt block
mentions top-scored capability first; degraded store (corrupt json) →
honest empty, no crash.

**Acceptance**: agent prompt (round 0) cites capabilities THROUGH the
facade; deleting any one store file degrades gracefully with an event.

## E3 — Graph ontology + mission diffs (law 5: the graph is the product)

**Why**: the Living Graph has kinds already; they need TYPE discipline
and cross-campaign diffs to become Palantir-grade.

**Scope**
- `core/blackboard.py`: typed node classes — asset / identity /
  credential / proof — each proof node carries an evidence-file pointer
  (extractions/ ledger line) as provenance; illegal links rejected.
- `graph_diff(target)`: campaign N vs N-1 — new/lost assets, confidence
  deltas, newly-proven links; rendered in the next campaign's recall
  block ("what changed since last time").
- Evidence provenance surfaced in the findings dossier (proof node →
  file citation already half-built via the mechanical index).

**Files**: `core/blackboard.py`, `core/mission_workspace.py` (recall +
dossier), tests.

**Guard tests**: ontology rejects malformed links; provenance survives
save/load; diff between two synthetic snapshots shows exactly the deltas;
dossier cites proof files for proof-typed nodes.

**Acceptance**: a second venice campaign's recall opens with "CHANGED
SINCE LAST CAMPAIGN" and the dossier proves every proof node.

## E4 — Kill-date discipline (laws 2+3: one bullet, honest expiry)

**Why**: Pegasus economics + Stuxnet expiry; makes campaign lifetime
explicit and auditable.

**Scope**
- Campaign kill-date: mission config gains `kill_date` (or derived
  from `max_mission_minutes` + campaign window); transport refuses new
  DNS resolution AFTER kill-date (already-opened requests finish — no
  mid-flight amputation).
- Identity burn schedule: op_identity auto-burns identities older than
  N days (stale accents are detection bait).
- Operator-side artifact self-inventory in the app-state report: files
  written, crash dirs, extractions, logs touched during the campaign —
  the client report's "cleanup" section becomes mechanical, not manual.

**Files**: `tools/_transport.py` (kill-date gate), `core/op_identity.py`
(age burn), `core/mission_workspace.py` (artifact inventory),
`core/agent.py` (doctrine line), tests.

**Guard tests**: post-kill-date fetch returns honest refusal verdict;
stale identity auto-burns on next recall; artifact inventory lists
exactly what the workspace recorded; no crash on missing config keys.

**Acceptance**: a campaign with a past kill-date refuses to start
transport; app-state gains "## OPERATOR ARTIFACTS" section, complete.

## E5 — Verifier farm (all laws: nothing unproven ships)

**Why**: the adversarial verifier is one voice with one model's blind
spots; findings deserve ranked multi-rubric attack before a report exists.

**Scope**
- `core/verifiers.py`: rubric classes — contradiction, coverage-gap,
  overclaim, opsec-leak (deliverable scrub preview + identity exposure
  scan), impact-inflation (rule-8 check: DEMONSTRATED claims must have
  evidence pointers).
- Farm runs N verifier agents (existing Agent, rubric-specific prompts)
  over the distilled transcript; findings ranked by severity → rendered
  as a "VERIFIER FARM REPORT" appendix section in the findings dossier.
- Budget: farm is opt-in per mission (`verify: full|quick|off`, default
  quick = 2 verifiers).

**Files**: `core/verifiers.py` (new), `core/swarm.py` (farm runner),
`core/mission_workspace.py` (dossier appendix), tests.

**Guard tests**: each rubric catches its seeded violation (synthetic
transcripts); off/quick/full honored; farm failures degrade to single
verifier (current behavior), never block the report.

**Acceptance**: a synthetic overclaim ("DEMONSTRATED" with no evidence
pointer) is caught by the farm and downgraded to POTENTIAL in the
dossier.

## Sequencing

E1 → E2 → E3 → E4 → E5, one chantier at a time, guard battery green and
pushed after each. E1 and E2 are independent enough to swap. E5 lands
last ON PURPOSE: it audits everything the others produce.
