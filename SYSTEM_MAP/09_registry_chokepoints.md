# 09 — REGISTRY CHOKEPOINTS: tools.execute() gates in EXACT order

tools/__init__.py execute(name, args, on_event) — every tool call in
the fleet (agent, chat, batch_execute, swarm) passes HERE. The gate
order is load-bearing; verify against code on every change.

## GATE ORDER (as executed)
1. Registry lookup — unknown name → UNKNOWN_TOOL error + skip_ledger
   ("unknown_tool", closest names in detail).
2. Token unmasking (_tokenize.unmask_obj) — the scope guard sees REAL
   destinations, not [HOST-n] placeholders.
3. Arsenal gate (current_allowed) — plan-mode/role/swarm restricted
   arsenals; SCOPE_TOOL + skip_ledger.
4. ROE gate — do_not_exploit=true blocks everything but danger=safe;
   ROE_BLOCKED + skip_ledger.
5. Scope guard G13 (_scope_check) — destinations in args must be in
   the operator's sanctioned perimeter; SCOPE_BLOCKED + skip_ledger.
6. _coerce_args — LLM type coercion PER THE TOOL'S SCHEMA (string
   booleans "true"/"1" → True; "5" → 5 for integer params; JSON
   strings → dict for object params). NOTE: iterates schema_props —
   unknown keys like `predict` pass through UNTOUCHED (verified law).
7. Datastore cascade — _CASCADE_KEYS fills present-but-EMPTY params
   from mission globals (mission layer > session); explicit args
   ALWAYS win; filled values re-coerced per schema (_coerce_one).
   The `predict` key is NEVER in _CASCADE_KEYS — no interaction.
8. Ω1 predict extraction — parse_prediction(args): predict REMOVED
   from args (the tool never sees it). Slot-defer → return "TOOL
   DEFERRED" + skip_ledger prereq_missing. Normal: pred held for
   post-run measurement.
9. sys.path guard + healer import; emitter resolution (thread-local
   nesting — batch_execute captures its thread's emitter and passes
   it explicitly to inner calls).
10. HEAL LOOP (≤3 attempts):
    - attempt 2+: Ω1 re-parse of healed args (predict re-extracted
      or measurement dropped — heal hygiene).
    - scope re-check EVERY attempt (args may have been rewritten).
    - allowed.names save/restore around the run (A2 propagation).
    - out = t["run"](**args) → str coerce (json.dumps) → 60KB cap.
    - EXCEPTION → healer.classify → heal_attempt; same-args retry only
      for TRANSIENT (NETWORK/TIMEOUT) categories — the mission-79
      crash-loop law (V16).
11. Post-run, in order: Ω1 measure (pred vs out; note appended if
    <55KB); chain hints (_hints.hint_for); capability vault touch
    (forged_*/session_keep); tool_result event; return out.

## Ω1 graft placement laws
- Extraction AFTER the cascade (predict must survive step 6-7 —
  verified: coerce iterates the tool's schema, cascade touches only
  curated keys).
- The defer return fires BEFORE the emitter start — no tool_start
  event for a deferred call (nothing flew).
- Measurement on the FIRST successful attempt's output; heal-retry
  re-parses.

## batch_execute inheritance
- The thread-local allowed set + scope are captured and re-applied to
  inner workers; inner events flow through the captured emitter (the
  event tap sees everything).
