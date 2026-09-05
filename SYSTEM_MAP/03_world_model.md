# 03 — Ω1 WORLD MODEL: the predictor (core/world_model.py)

Law #1: SURPRISE IS THE SIGNAL. A predicted 200 that returns 200
carries zero information; a violated prediction is where exploits live.

## 1.1 Prediction contract
- The agent may attach `predict: {...}` to ANY tool call's args. The
  registry (tools/__init__.py, execute) extracts it BEFORE the tool
  sees the args — the tool NEVER receives a predict key.
- Fields (all optional, ≥1 required):
  - expected_status: int 100..599 or list of them
  - expect_contains: str or list of str (≤120 chars each)
  - sentinel: str that MUST appear
- MEASUREMENT (world_model.measure):
  - statuses regex-scanned from tool JSON output: `"status(_code)?": N`
    — CHECK scans EVERY status (a dir_brute 30-status output must not
    fake a violation because the match sits at index 12; only the NOTE
    is display-bounded to 8).
  - status axis satisfied if ANY observed status ∈ expected list.
  - verdict ladder: all axes ok → respected (surprise 0.0); all
    violated → violated (1.0); mixed → partial (fraction); no
    measurable axis → unmeasured (NEVER fakes a verdict).
  - surprise ring per-endpoint (bounded, ring 25/endpoint, 256
    endpoints) → surprise_digest(limit) = the round-pacing feed.
- The note rides the tool result (deterministic phrasing):
  `[Ω1/PREDICT ✓|◐|✗ VIOLÉ] ...` — see prediction_note().
- HEAL HYGIENE: attempt 2+ runs with HEALED args — the loop re-parses
  predict from the healed args (or drops measurement if the heal
  dropped it). The frozen prediction of attempt 1 must never be
  measured against attempt 2's output.

## 1.4 Fail-closed slots
- A predict carrying unresolved `{slot_name}` placeholders DEFERS the
  whole call: return "TOOL DEFERRED [Ω1]..." + skip_ledger
  prereq_missing. Never fires half-rendered. (caldera defer, our shape)
- parse_prediction returns `({"deferred": "unresolved-slot"}, args)`.
- Edge: a legit expected-content that HAPPENS to contain braces could
  false-defer — accepted trade-off (defer is harmless; the note tells
  the agent why).

## 1.2 Calibrated comparator (sqlmap comparison.py, our shape)
- Constants: _LO 0.02, _HI 0.98, _DIFF_TOL 0.05, _MARK_MIN 20.
- learn_markings(endpoint, bodyA, bodyB): two CLEAN fetches → dynamic
  spans (CSRF/timestamps) learned as (prefix, suffix) anchors around
  the matched blocks; remove_markings splices them out pre-comparison.
- calibrated_verdict: identical → same; ratio > 0.98 → same; < 0.02 →
  differs; MID-BAND → the LEARNED match-ratio (false signature) decides
  — first mid-band call LEARNS (sqlmap kb.matchRatio).
- >10MB bodies: length-ratio fallback (difflib cap).
- NOTE: the comparator/floors API is NOT yet called by live tools —
  it's the calibrated core ready for tool adoption (next mission's
  calibration point).

## 1.3 Cascade noise floors (ffuf, our shape)
- noise_floor(host, samples≥3): scalars (size/words/lines/status)
  IDENTICAL across all semantically-loaded probe samples = the floor
  (wildcard/soft-block signature). Any variance kills that scalar.
- is_noise(host, ...): candidate matching ≥ floor-size-1 of the floor
  scalars = NOISE, not a finding.
- Floors TTL'd (see 1.5).

## 1.5 TTL discipline (amass: the graph is the cache)
- Every store entry `{value, ts, ttl}`; default TTL 3600s, predictions
  1800s. Expired read → None → caller re-verifies (NEVER serves stale
  as truth). _get reaps on read; _put LRU-evicts to _MAX_PER_KIND=2048.
- _pred_key: json.dumps(sort_keys=True, default=str) — crash-proof on
  nested dicts (the sorted-items TypeError bug, fixed).

## Graft points
- tools/__init__.py execute(): extract pre-gates (AFTER cascade fill),
  re-parse on heal-retry, measure post-run, note appended <55k cap.
- agent.py round pacing: [Ω1 SURPRISE MAP] block rnd ≥ 1, digest 3.
- agent.py init: world_model.reset() per mission (process-wide —
  single-mission console; swarm caveat documented).
- Doctrine (SYSTEM prompt): "PREDICT BEFORE YOU STRIKE" section — no
  underscore field names (arsenal integrity regex would flag them as
  phantom tools).
