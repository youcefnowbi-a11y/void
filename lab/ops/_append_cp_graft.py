# -*- coding: utf-8 -*-
"""Append CP1/CP2 campaign graft-log section."""
import io

P = "SYSTEM_MAP/12_graft_log.md"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

section = """
## NEW-ERA ARCHITECTURE + CAMPAIGNS CP1/CP2 (2026-09-06 — the premium session)

RESEARCH (3 subagents, live): (1) AI-hacking research report archived
  at SYSTEM_MAP/13 — wave-3 verdict: the moat is the HARNESS
  (verification + memory), MCTS-for-hacking is an open lane, auth
  walls are the field's biggest blocker; (2) threat-intel catalog
  archived at SYSTEM_MAP/14 — 45+ techniques, meta-pattern:
  "scanners test what a request does; humans test what two
  components DISAGREE about"; (3) internal audit — 22 findings with
  file:line evidence.

SHIPPED (all live-verified, battery 382/382 after each):
- GRIMOIRE 1.5.0: DIFF domain grafted (84 interpretation-differential
  techniques -> 141 total / 12 domains), recon-signal triggers in
  every detection field, tool desc + domain filter updated, verbose
  formatter fixed for string-shape detection records.
- AUDIT #4 CRITICAL fixed: MCTS tactical plan now injects at round 0
  of EVERY live mission (opening book — the planner participates
  while the LLM lives, not only when it dies).
- AUDIT #8 HIGH fixed: duplicate data_extract key in attack_graph
  ACTIONS — the dict silently kept the weak probe (yield 3.0) and
  deleted the Bearer-strike (5.5). Merged into one hybrid node.
- AUDIT #9 CRITICAL fixed: adversarial twin trigger widened from one
  whitespace-sensitive substring to every verdict-carrying strike
  structure (OOB, exploitables, CONFIRMED BOLA/leak/breach/bypass).
- AUDIT #12 HIGH fixed: 180s tool deadline watchdog in the registry
  execute choke point — no tool can freeze the mission anymore.
- CAMPAIGN RUNNER (lab/_calib_campaign.py): PLAN -> SWARM -> VERIFY
  3-phase premium flow, the dormant PlannedSwarm now reachable from
  the calib lane. CP1 caught the ("assistant" vs "agent") transcript-
  kind bug — plan extraction + round counting fixed in both runners.

CAMPAIGN CP1 (solo-fallback proof, 43 rounds, 105 calls): 8 findings
  confirmed on known terrain — XFF geo-spoof (DZ->US identity override
  trusted end-to-end, symmetric twins), race_smash 40/40 double-
  processing (zero dedup), h5_event plaintext ingestion, catalogs
  with tenant access_id never-expiring credentials, sqli_tamper GET-
  plane artifact caught honestly. DIFF doctrine did NOT find SQLi/
  smuggling/proto-pollution — HELD with proof (the wall verdicts
  are intelligence too).

CAMPAIGN CP2 (full architecture proof, 72 min total): PLAN sealed
  (11,360 chars, 8 chains detected) -> PlannedSwarm ran 4 parallel
  chains with fresh contexts (link_id_injection, app_twin_differential,
  counter_races_most_viewed, client_crypto_auth_gate) -> adversarial
  verifier engaged (2 provider refusals absorbed by wipe-restart,
  clean termination). Chain strikes: most_viewed full grammar
  ({uid,file_type:"FILE",os,language,size,index:[]}) -> 55KB
  cross-user PII (random-operation-account semantics decoded);
  AES-CBC static pair identified as the EVENT keypair; forged
  byte-exact client telemetry events ACCEPTED (200 true, 90/90 race
  accepted, zero rate-limit); per-video secretKey named as delivered
  only via APK authenticated channel (honest missing link); FIPS-197
  self-vindication discipline on the forged AES core; backend
  tightening observed live (size max 30, both twins in lockstep =
  one brain confirmed again).

FLEET BUGS (CP2, to fix next session):
- chain subagents have no workspace binding (evidence_pack/
  report_write dead inside chains — 'no active workspace' notes);
- verifier phase bound a wrong workspace (outerface.venice.ai from
  stale target_model extraction) and ate 2 provider refusals;
- sqli_tamper_chain fires GET-plane on POST-only routes (tool-shape
  false negative, the chain agent caught it itself);
- healing '[healer] TIMEOUT -> paced retry (no timeout knob)' noise
  on differential_sweep long sweeps.

NEXT-AXIS: fix the chain workspace binding + verifier target binding;
the campaign runner is now the premium lane for every fresh target.
"""

with io.open(P, "a", encoding="utf-8") as f:
    f.write(section)
print("graft log appended:", len(section), "chars")
