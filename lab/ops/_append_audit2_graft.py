# -*- coding: utf-8 -*-
"""Append audit-fixes graft section."""
import io

P = "SYSTEM_MAP/12_graft_log.md"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

section = """
## AUDIT-22 FIXES WAVE 2 (2026-09-06 — 7 more findings closed)

Following the 22-finding architecture audit (delivered in full, all
file:line verified), the second fix wave closed:
- #20 LLM stale-resp (fleet loop could parse the PREVIOUS provider's
  payload after a mid-loop rotation — resp=None pre-loop + isinstance
  check; the dir() sniff is dead).
- #7 dedup memory: mission-scoped call-signature history — a repeat
  of a FAILED signature (any distance back, not just consecutive)
  rides the tool result as [DUPE rN: signature deja tentee]. Verdicts
  banked AFTER honest_status so the twin sees the same truth.
- #6 planner-state harvesters: Set-Cookie strings, sb_secret_/
  service_role keys, host facts (the ad_spray/ad_bloodhound lane was
  unreachable from ANY brief — no host fact ever minted), and the
  email-as-handle regex bug fixed (contact@target.com no longer
  mints "target" as a Telegram handle). All verified live.
- #1 episodic digest (CRITICAL): every 10 rounds a self-index injects
  (last 10 calls: tool, target-args, verdict + blackboard asset
  count). The context diet amputates rounds 1..N-25 to 900-char
  fragments — the digest is the durable memory the model keeps.
Battery 382/382 after all fixes.

REMAINING from the audit (next session, priority order):
- #10 report-claims verifier (deterministic check of Cited proof
  artifacts vs the extractions index markers)
- #13 composite.py transport migration (naked urlopen violates the
  forge's own WIRE LAW — no pacing, no circuit breaker)
- #11 concurrent outer dispatch (serial=true flag for stateful tools)
- #2 real token counting (core/_tokenize exists, wire it into the
  budget estimate), #3 static preamble digest after r8
- #14 ranked cross-target play recall + mid-mission plays_search
- #18 soft-fail counters (subsystem death visibility), #19 event-tap
  thread-keyed pending, #22 wall-sig keyed off transport block flag
"""

with io.open(P, "a", encoding="utf-8") as f:
    f.write(section)
print("graft log appended:", len(section), "chars")
