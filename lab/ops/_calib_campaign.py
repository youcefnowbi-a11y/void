# -*- coding: utf-8 -*-
"""VOIDFORGE :: CALIB CAMPAIGN — the premium mission runner.

Usage:
    python -X utf8 lab/_calib_campaign.py <RUN_ID> "<brief>"

The 3-phase architecture (new era premium):
  PHASE A — PLAN: a recon-only agent (plan_mode) maps the surface and
            emits the ATTACK PLAN + machine JSON chains. No strikes.
  PHASE B — SWARM: PlannedSwarm executes the approved chains in
            parallel — each chain a scoped specialist with its own
            context window, its own arsenal, streaming events tagged
            chain:<name>. Long missions stop rotting: 5 fresh windows
            instead of one rotting window.
  PHASE C — VERIFY: the adversarial verifier attacks OUR OWN work
            (contradictions, coverage gaps, unmade connections,
            overclaims), then a synthesis agent seals the final report.

Events stream crash-safe to lab/camp_<ID>/events.jsonl (same tail-
follow protocol as _calib_mission).
"""
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else f"camp_{int(time.time())}"
MISSION = sys.argv[2] if len(sys.argv) > 2 else None
if not MISSION:
    print("usage: _calib_campaign.py <RUN_ID> \"<brief>\"")
    sys.exit(1)

OUT = os.path.join("lab", f"camp_{RUN_ID}")
os.makedirs(OUT, exist_ok=True)

import yaml  # noqa: E402

_t0 = time.time()
_events_f = io.open(os.path.join(OUT, "events.jsonl"), "a", encoding="utf-8")


def on_event(ev):
    ev = dict(ev, _t=round(time.time() - _t0, 1))
    t = ev.get("type", "?")
    txt = str(ev.get("text", ""))[:140]
    print(f"[{ev['_t']:8.1f}s][{t:16s}] {txt}", flush=True)
    try:
        _events_f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        _events_f.flush()
    except Exception:
        pass


def sysmsg(text):
    on_event({"type": "system", "text": text})


# ── cfg: LO's provider.yaml, in-memory limits stay UNLIMITED ──
with io.open(os.path.join("config", "provider.yaml"), encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
p = cfg["provider"]
p["max_tool_rounds"] = 0
p["max_mission_minutes"] = 0

sysmsg(f"CAMPAGNE {RUN_ID} — architecture premium 3 phases: PLAN → SWARM → VERIFY")
sysmsg(f"BRIEF: {MISSION[:180]}")

# ═══ PHASE A — PLAN (recon-only agent, no strikes) ═══
from core.agent import Agent  # noqa: E402

sysmsg("PHASE A — agent plan-mode (recon only) engaged")
planner = Agent(cfg, plan_mode=True)
planner.max_rounds = 40          # plan phase is bounded — recon maps, then stops
plan_doc = None
try:
    transcript = planner.run(MISSION + "\n\nProduce the ATTACK PLAN now — recon then the plan as your final message.",
                             on_event=lambda ev: on_event(dict(ev, phase="plan")))
    # CP1 BUG FIX: transcript tuples are ("agent", content) — NOT "assistant".
    # The old extraction searched k == "assistant" and ALWAYS found None →
    # the campaign silently fell back to solo despite a perfect plan.
    plan_doc = next((t for k, t in reversed(transcript) if k == "agent" and
                     ("ATTACK PLAN" in str(t) or '"chains"' in str(t))), None)
except Exception as ex:
    sysmsg(f"⚠ PHASE A died: {type(ex).__name__}: {str(ex)[:150]}")

if not plan_doc:
    sysmsg("⚠ no plan produced — campaign falls back to SOLO mode")
    from core.agent import Agent as _A  # noqa: E402
    solo = _A(cfg)
    solo.run(MISSION, on_event=on_event)
    sysmsg("CAMPAGNE terminée (solo fallback)")
    sys.exit(0)

with io.open(os.path.join(OUT, "plan.md"), "w", encoding="utf-8") as f:
    f.write(str(plan_doc))
sysmsg(f"PLAN scellé ({len(str(plan_doc))} chars) — lab/camp_{RUN_ID}/plan.md")

# ═══ PHASE B — SWARM (parallel chains from the plan JSON) ═══
from core.swarm import PlannedSwarm, parse_plan_json  # noqa: E402

parsed = parse_plan_json(str(plan_doc))
sysmsg(f"PHASE B — PlannedSwarm: {len((parsed or {}).get('chains', []))} chain(s), "
       f"mode={(parsed or {}).get('mode', 'swarm')}")

swarm = PlannedSwarm(cfg, str(plan_doc))
swarm.max_subagents = max(1, int((parsed or {}).get("max_subagents") or 4))
try:
    swarm.run(MISSION, on_event=lambda ev: on_event(dict(ev, phase="swarm")))
except Exception as ex:
    sysmsg(f"⚠ PHASE B died: {type(ex).__name__}: {str(ex)[:150]}")

# ═══ PHASE C — verify pass (adversarial) ═══
sysmsg("PHASE C — adversarial verifier (attack our own work)")
from core.blackboard import Blackboard  # noqa: E402
try:
    board = swarm.board
    # CP2 fleet fixes: (a) the verifier carried ["__no_tools__"] — a text
    # critic, no evidence; give it the READ-ONLY probe lane so it can
    # RE-TEST claims. (b) it ran workspace_for(verify_mission) on the
    # intel-graph text and bound outerface.venice.ai (a domain cited in
    # the graph) — inherit the campaign workspace instead. (c) the final
    # extraction searched k == "assistant" — transcript kinds are "agent"
    # (the CP1 bug AGAIN, in the verifier lane: verifier_report.md was
    # never written, silently).
    _vtools = ["data_extract", "web_fingerprint", "endpoint_oracle",
               "file_grep", "secret_scan", "workspace_status"]
    from tools import all_tools as _atl
    _vknown = {t["name"] for t in _atl()}
    _vtools = [t for t in _vtools if t in _vknown]
    verifier = Agent(cfg, tools_filter=_vtools or ["__no_tools__"],
                     extra_system=None, blackboard=board)
    from core.swarm import VERIFIER_PROMPT  # noqa: E402
    verifier.system_prompt += "\n\n" + VERIFIER_PROMPT
    verifier.max_rounds = 3
    vt = verifier.run(
        f"Target intel graph:\n{board.to_prompt(50)}\n\n"
        f"Original mission: {MISSION[:800]}\n\n"
        "Produce your verifier findings now (numbered, evidence-based): "
        "contradictions, coverage gaps, unmade connections, overclaims.",
        on_event=lambda ev: on_event(dict(ev, phase="verify")),
        inherit_ws=getattr(swarm, "ws", None))
    v_final = next((t for k, t in reversed(vt) if k == "agent" and len(str(t)) > 200), None)
    if v_final:
        with io.open(os.path.join(OUT, "verifier_report.md"), "w", encoding="utf-8") as f:
            f.write(str(v_final))
        sysmsg(f"VERDICT verifier scellé — lab/camp_{RUN_ID}/verifier_report.md")
    else:
        sysmsg("⚠ verifier n'a pas produit de verdict final")
except Exception as ex:
    sysmsg(f"⚠ PHASE C died: {type(ex).__name__}: {str(ex)[:150]}")

# ═══ ARSENAL HARVEST (EV3 fix): the campaign's ledger → plays ═══
try:
    from core.learned_plays import harvest_from_ledger
    from core.mission_workspace import workspace_for
    _hws = workspace_for(MISSION if "http" in MISSION else f"target https://duskyr.com")
    _n = harvest_from_ledger(_hws)
    sysmsg(f"📚 Arsenal harvest: +{_n} play(s) mintés depuis le ledger campagne")
except Exception as ex:
    sysmsg(f"⚠ Arsenal harvest failed: {type(ex).__name__}: {str(ex)[:150]}")

sysmsg(f"CAMPAGNE {RUN_ID} terminée en {round(time.time() - _t0, 0):.0f}s")
_events_f.close()
