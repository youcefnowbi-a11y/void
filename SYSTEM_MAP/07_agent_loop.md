# 07 — THE AGENT LOOP: round by round, every graft in execution order

core/agent.py ~2400 lines. This is the loop as it EXECUTES, grafts in
order. Read this against the code — divergences are bugs.

## Agent.__init__(cfg, persona, tools_filter, extra_system, blackboard,
                  plan_mode)
- LLM bound (cfg["provider"]).
- PLAN_TOOLS (recon-only) if plan_mode; specialist filter if role.
- Ω2: twin.configure(cfg) — binds the challenger's LLM (best-effort).

## Agent.run(mission, ...) — SETUP PHASE (in order)
1. Vault reset (per-campaign tokens) unless swarm specialist.
2. Workspace: workspace_for(mission) → set_active(ws).
3. msgs = [system prompt].
4. Skills block (user message).
5. Ω3: _tgt = extract_target(mission); dream plays (≤8, TARGET-
   FILTERED) → "DREAM PLAYS" user message.
6. Ω4: doctrine load → round0_block(_tgt) user message +
   _doctrine_armed (entries whose context matches).
7. Learned plays recall (user message).
8. prior_intel / commander_orders / plan_doc injections.
9. Mission state, event tap, vault.
10. Per-mission resets (all try/except, in this order):
    stop_rails.reset(); skip_ledger.start_mission(id);
    datastore.start_mission(id); world_model.reset();
    twin.refresh_from_trajectory(); dream.bind_mission(id, target).
11. base_msgs snapshot, operator orders.

## ROUND LOOP (for rnd in range(max_rounds))
- Abort/inbox drain checks (operator messaging).
- LLM stream (chat_stream, fallback chat) → content + tool_calls.
- Refusal wipe protocol (refusal streaks → delay + fresh context).
- If tool_calls: for tc in tcs:
  1. name, args extract; dupe-check bookkeeping (G10).
  2. tools.execute(name, args, on_event=...) — THE CHOKE POINT (see 09).
     Returns out (string).
  3. transcript.append(("tool", ...)) — AFTER the twin cap? NO:
     transcript append happens AFTER the twin/graft block — the order
     in the file is: rails → twin → step_bump → Ω4 verify →
     transcript → pacing compute → append msgs. VERIFY against code.
  4. Rails: stop_rails.observe(name, out); if a rail is pending →
     deliver ONCE → skip_ledger rail_pivot → _rail_note (SET).
  5. Wall-streak logic (WAF/403 signature, _NOISE_TOOLS exemption,
     honest_status clearing) — wall_breaker auto at streak ≥ 2.
  6. Ω2 twin: blind-class trigger (oob + exploitable true, both
     separators) → blind_policy → cite or CAP (out replaced) →
     _rail_note APPEND.
  7. Ω3: dream.step_bump().
  8. Ω4: armed entry where==name → report_use(honest_status).
  9. Coverage counter, Living Graph feed (from_tool_result on the
     CAPPED out — the relocation was the bug fix), workspace save,
     trajectory record.
  10. Pacing compute: extraction/strike balance + ALERTE 0-strike +
     Ω1 SURPRISE MAP digest (rnd ≥ 1) + G10 dupe note.
  11. msgs.append(tool result + pacing + _rail_note) — A3: EVERYTHING
      rides the tool content, never a mid-convo system/user message.
- Wall-breaker intel (_wall_pending) → user message AFTER all results.
- Coverage order every COVERAGE_PERIOD rounds (escalation → offline
  brain proposal).
- Final report detection (RAPPORT DE MISSION FINAL heuristics) →
  evidence_pack check → mission ends.

## TEARDOWN
- release_workspace, board flush.
- Ω4 autopsy: doctrine.autopsy(target=_tgt, skip_ledger.summary(),
  extra_entries=[]) → skip rules minted + persisted. THE LOOP CLOSES.
- mission_complete event. return transcript.

## Known caveats (documented, by design)
- world_model.reset()/stop_rails.reset() are PROCESS-WIDE — two
  concurrent missions (swarm outer + manual) would cross-reset.
  Single-mission console is the supported shape.
- A concurrent _doc.load() (another mission's round 0) swaps
  _ENTRIES[:] → _doctrine_armed refs go stale → verdicts drop as
  honest no-ops (report_use returns None on miss). Exact in console.
- _rail_note: rails SET, twin APPENDS, reset at loop-head per tc.
  Order in file: rails before twin (same tc) — append-after-set safe.
