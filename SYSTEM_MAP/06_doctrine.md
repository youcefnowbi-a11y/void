# 06 — Ω4 DOCTRINE: the loop closes (core/doctrine.py)

The system writes itself: entries minted by autopsies and dreams,
read at round 0, self-verified against outcomes, retired when they
stop working.

## 4.1 Entries: predicate × context × where
- add_entry(predicate, context, where, expected, origin, evidence):
  - predicate ≤300, context ≤200, where ≤120 — where is REQUIRED (a
    rule that names no action is prose, not law).
  - IDEMPOTENT per triple: re-minting reinforces (+0.02 score,
    times_re_minted++) instead of duplicating — the same quarantine
    rule re-minted every mission fuses, never floods.
  - score prior 0.6; used/worked/failed counters; ts.
  - Cap 512 live: overflow retires the WEAKEST to the graveyard
    (never hard-deleted).
- round0_block(target, limit=10): live entries, score desc, where the
  context matches the target (empty context = universal; fuzzy
  _ctx_matches: substring either way or \bword\b match) — rendered as
  `- ON <context>: <predicate> → <where> [confidence S, W✓/F✗]`.
- CRITICAL (test): doctrine text in the SYSTEM prompt must not contain
  underscore field names that look like tool names (arsenal integrity
  regex flags them as phantom tools).

## 4.2 Predicate termination (caldera Goal{trait,value,count})
- parse_goals(brief): grammar `trait: value [xN]` (+ explicit Goal{}
  wrappers stripped). RESERVED words (goal/trait/value/count) never
  CONSUME a following pair — 'Goal: keys: admin x3' must yield
  keys=admin x3, not eat 'keys' as Goal's value (the regex-consumption
  bug, fixed with prefix-strip).
- Loose natural language → NO goals (honesty over hallucination).
- goal_progress(goals, assets): counts assets whose props[trait]==value
  or value ⊆ asset value; met when have ≥ count.

## 4.3 Skip-taught doctrine
- skip_taught(summary) — honors the REAL skip_ledger.summary() shape:
  {total, by_reason:{cat:count}, example:{cat:"tool: detail"}} — NOT
  the counts/examples shape I first wrote (the shape-mismatch bug).
- _SKIP_RULES curated map (category → (rule template, where)):
  unknown_tool→naming, quarantined→patience, rail_pivot→
  wall-avoidance, scope_blocked→discipline, roe_blocked→roe,
  prereq_missing→sequencing. The example rides in the predicate.
- garbage-safe: non-dict by_reason/example → [] (the .items() crash).

## 4.4 Self-verification (Bayesian retire)
- report_use(entry_or_triple, worked):
  - score = 0.6 * laplace_rate + 0.4 * old_score, where
    laplace_rate = (worked+1)/(used+2).
  - CALIBRATION (the decay bug): the first draft used (1-0.72)*score
    on failure — ONE failure sent a fresh 0.6 to 0.168 → instant
    graveyard. The Laplace blend: fresh 0.6 → one failure 0.47 →
    survives ~3, retires ~4. Gentle decay, real retirement.
  - Below _RETIRE_AT (0.25): entry → graveyard WITH retired_ts, and
    save() fires IMMEDIATELY (a mission crash must not resurrect a
    dead rule) — which DEADLOCKED with threading.Lock; the lock is
    threading.RLock (report_use holds it and calls save → save re-
    enters). NEVER revert to Lock here.
- _find: dict identity OR triple match. A concurrent load() replaces
  _ENTRIES[:] — armed refs go stale, verdicts drop as honest no-ops
  (single-mission console is exact; documented swarm caveat).

## Graft points (agent.py)
1. Round 0 (after dream plays): _doc.load() → round0_block user
   message + _doctrine_armed = matching entries (Ω4.4 wiring).
2. Tool loop (after step_bump): if the tool == armed entry's where →
   report_use(entry, honest_status=="ok"); retire broadcast on event.
3. Teardown (before mission_complete): _doc.autopsy(target, skip
   summary, extra entries) → skip rules minted + save. The loop closes.

## Persistence
- intel/doctrine.json {entries, graveyard} — load() replaces both
  lists in place. save() on autopsy, on retire, on demand.
