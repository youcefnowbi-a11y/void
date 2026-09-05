# 04 — Ω2 TWIN: the doubter (core/twin.py)

Law #2: NO VERDICT WITHOUT PROOF. Every CONFIRMED blind-class finding
passes a standing challenger BEFORE it can ride into the report. The
twin is POLICY (metasploit AutoCheck prepend), never a tool to forget.

## 2.2 Truth table (sqlmap checkFalsePositives, our shape)
- truth_table(oracle_fn, reps=2): fresh distinct randoms r1≠r2≠r3 per
  rep. The oracle MUST answer: r1=r1 → True; r1=r2 → False; r1=r3 →
  False; INVALID (no '=') → False.
- Kills: always-true (honeypot), always-false (broken), echoing
  oracles. Exception in oracle_fn → (False, table) — fail closed.
- Consumer: NOT yet wired into live boolean tools — the sqli blind
  tools' adoption is a calibration-mission target.

## 2.4 Blind-verdict policy (the DETERMINISTIC gate)
- blind_policy(tool_out) reads the REAL tool output shape:
  ssrf_probe/xxe_probe emit: `oob: {url, callback_received, proof}`,
  `signals_found: int`, `exploitable: bool|str`, `proof_object: {...}`.
- Returns:
  - (True, citation) — OOB callback + proof_object → CONFIRMED, cite
    protocol + token in the report.
  - (None, None) — not blind-class, OR honest hypothesis (exploitable
    not true), OR INLINE-CONFIRMED (signals_found ≥ 1 — the tool's own
    differential is legitimate proof; capping it was the Phase-2 bug).
  - (capped_json, note) — the CONTRADICTION: exploitable=true with
    ZERO inline signals and NO receipt → capped to
    `"exploitable": "partial"`, proof_object nulled, twin_note rides.
- agent.py graft: trigger `'"oob"' in out and ('"exploitable": true'
  in out or '"exploitable":true' in out)` (both JSON separators);
  the CAP REPLACES `out` BEFORE blackboard/§workspace/transcript/pacing
  — every downstream consumer sees the honest version. Placement was a
  real bug: first graft sat AFTER the archive consumers.

## 2.3 Reliability ranks (metasploit MinimumRank, our shape)
- refresh_ranks({tool: {runs, wins, hard}}): rank =
  0.6*(wins/runs) + 0.4*(hard/runs), clamped 0..1; runs < 3 → neutral
  0.5. Garbage entries skipped (isinstance dict).
- refresh_from_trajectory(): rebuilds from the archive tail — runs =
  all events, wins = ok, hard = state ∈ {confirmed, exploited}. Called
  once per mission start (agent init block).
- rank_note(tool): below TWIN_DISCOUNT (0.35) → deterministic discount
  citation the twin argues from.
- RANKS ARE PROCESS STATE (not persisted) — cross-mission within the
  process, rebuilt on restart. Persistence is a post-ultimate option.

## 2.1 The LLM twin call (budgeted second opinion)
- twin_attack(tool, out, target): deterministic weapons first (rank
  note + blind policy note); then — ONLY if configured via
  twin.configure(cfg) (Agent.__init__ binds it) and _budget_ok() —
  a second LLM pass with _TWIN_DOCTRINE ("this finding is WRONG;
  attack it: honeypot? canary? misread status?...").
- Interface: builds LLM(base_url, api_key, model, temperature=0.2)
  from cfg["provider"], messages=[user], max_tokens=400. NO module-level
  chat() exists — that was the phantom-interface bug.
- Response parsed as FIRST {...} JSON block (DOTALL regex); survives
  [LLM HTTP ...] error strings (no braces → no parse → deterministic-
  only record). Cache per identical verdict key (bounded 256), budget
  ≤40 calls/hour (window reset).
- Unconfigured/offline → deterministic-only, survived=True default —
  the twin is NEVER a single point of failure.

## Doctrine (SYSTEM prompt)
"THE ADVERSARIAL TWIN" section after strike discipline: capped
verdicts, TWIN notes = live doubt, low-rank tools must re-prove.
