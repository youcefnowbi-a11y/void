# 10 — INVARIANTS: THE LAWS (things that must never break)

Every audit wave re-verifies these against the code. A violated
invariant is a bug by definition, whatever the tests say.

## PRIME LAW (LO's law — above all others)
- **P0 NO SYSTEM IS PERFECT / NO SYSTEM IS LOCKED 100%.** Every
  "locked", "perfect", or "solid" system has leaks nobody knows yet.
  The mission is NEVER finished at a HELD gate: known vectors closed
  = the hunt for UNKNOWN leaks continues. Any internal state reading
  "proven sound / solid / locked" is a phase marker, NOT a verdict —
  the next surface, the next edge, the next session law applies.
  Concrete consequences in the fleet:
  - a "gate held" report must still propose the NEXT leak-hunt axis
    (target exhausted on the current plane = move planes, not stop);
  - doctrine entries minted from held-gates carry the assumption
    "held on the tested surface only";
  - the dream/differential stack exists BECAUSE of P0 — the leaks are
    found by varying invariants, not by accepting the wall.

## Truth laws
- I1 NO VERDICT WITHOUT PROOF (Ω2): a blind-class confirmation
  without OOB receipt AND without inline differential is capped at
  "partial" with proof: null, visible to the operator. Inline signals
  ≥1 = legitimate proof (never capped).
- I2 SURPRISE IS THE SIGNAL (Ω1): respected = 0.0; violated = 1.0;
  partial = fraction of violated axes; UNMEASURABLE NEVER FAKES a
  verdict (no status in output → unmeasured, not violated).
- I3 The simulator never invents success (Ω3): no archived evidence
  for a branch → NO play. Plays are suggestions, never verdicts.
- I4 Doctrine retires on evidence (Ω4): Laplace blend; gentle decay
  (one failure never kills a fresh rule); graveyard is auditable
  forever (nothing hard-deleted).

## Wire laws
- W1 STRIKES NEVER COALESCE — every side-effect request hits the wire
  (POSTs, injection payloads). Only cacheable GETs dedup.
- W2 STRIKES NEVER CACHE — a strike's response is never served from
  cache to a later caller.
- W3 The breaker counts TRANSPORT DEATH (status -1) only. -3 is
  synthetic (quarantine skip): never re-marks, never cached, never
  counted as "responded" by any consumer (the xxe responded bug).
- W4 Quarantine cooldown 300s; ANY real HTTP success = full removal.
- W5 The OOB predicate is FROZEN pre-send; a FAILING interaction does
  NOT consume the pending correlation (the WAF health-check law).
- W6 Offline OOB is honest: `<tok>.oob.internal`, never a fake domain.

## Loop laws
- L1 A3 MESSAGE DISCIPLINE: no mid-conversation system role; no user
  message between assistant(tool_calls) and tool(results). Everything
  rides tool-result content (rails note, twin note, pacing, surprise
  map). Wall-breaker intel waits for the user slot after the batch.
- L2 The heal loop never retries same-args on a deterministic error
  (mission-79 law); only NETWORK/TIMEOUT categories may same-args
  retry.
- L3 Scope re-check EVERY heal attempt (args may have been rewritten
  by the heal — a healed URL must not bypass G13).
- L4 Every refusal CATEGORIZES (skip_ledger): unknown_tool,
  scope_tool, roe_blocked, scope_blocked, quarantined, rail_pivot,
  budget, prereq_missing, other. An uncategorized skip is a bug.
- L5 The twin cap happens BEFORE every archive consumer (blackboard,
  workspace, transcript, evidence_pack) — the report can only cite the
  honest version.
- L6 Provenance stamps are immutable: an archived fact keeps its
  ORIGINAL prov; re-stamping would lie about birth.
- L7 Doctrine text in SYSTEM may never contain underscore names that
  look like registry tools (arsenal integrity bijection) and every
  registry tool MUST be named in doctrine OR whitelisted in
  MCTS_WHITELIST (test_arsenal_integrity).

## State laws
- S1 Per-mission resets (rails, ledger, datastore-mission-layer,
  world_model) run in agent.run init, all best-effort try/except.
- S2 Stores bounded: skip 512, ranks-by-trajectory, twin cache 256,
  plays 256, doctrine 512+graveyard, OOB 2048, breaker hosts 4096,
  in-flight 64, world kinds 2048 each, rings 256×25.
- S3 The playbook file paths are FUNCTIONS not module constants when
  tests monkeypatch roots (plays file — the frozen-const bug class).
- S4 Every store write is best-effort (a state failure NEVER kills a
  strike; the nervous system is silent armor).

## Determinism laws
- D1 No LLM inside world_model/dream/doctrine arithmetic (law #3).
  The ONLY LLM twin call is budgeted (≤40/h), cached, optional, and
  never gates alone.
- D2 The truth table, blind policy, ranks, and Bayesian retire run
  with a dead LLM — the twin is never a single point of failure.
