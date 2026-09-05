# -*- coding: utf-8 -*-
"""CALIBRATION MISSION HARNESS — run a live mission with the FULL new
brain (Ω1-Ω4) and capture every system signal for weakness analysis.

Captures:
- every on_event (rails, twin, dream, doctrine, coverage)
- the full transcript
- skip_ledger summary at mission end
- doctrine file state before/after (did the autopsy mint?)
- world_model surprise map at end
- wall-clock timing per round

Usage: python lab/_calib_mission.py <run_id> <mission text>
Writes lab/calib_<run_id>/*.json
"""
import sys, os, time, json, yaml, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = None
RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "A"
MISSION = sys.argv[2] if len(sys.argv) > 2 else (
    "Recon complet de duskyr.com: fingerprint, endpoints, JS secrets, "
    "puis probing sqli/xss standard. Rapport final avec evidence.")

OUT = os.path.join(ROOT, "lab", f"calib_{RUN_ID}")
os.makedirs(OUT, exist_ok=True)

# ── crash-safe incremental capture (D2 lesson: a process killed at
#    round 52 left NOTHING — the harness only wrote at the end) ──────
_TR = open(os.path.join(OUT, "events.jsonl"), "w", encoding="utf-8",
           buffering=1)

def _tr_flush(kind, entry):
    """Incremental transcript append — survives a mid-mission death."""
    try:
        _TR.write(json.dumps({"kind": kind, "entry": entry},
                             ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass

# ── cfg: LO's provider.yaml, mutated IN MEMORY ONLY ──
# LO's law: NO limits — no time budget, no round cap. The agent
# finishes what it starts. (Twice I capped it; twice it amputated the
# chase. Never again.)
with open(os.path.join(ROOT, "config", "provider.yaml"), encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
cfg["provider"]["max_tool_rounds"] = 0          # unlimited — LO's law
cfg["provider"]["max_mission_minutes"] = 0     # no deadline — LO's law

# ── pre-mission state snapshot ─────────────────────────────────────────
from core import doctrine as _doc, skip_ledger as _sl, world_model as _wm
_doc.reset()
_pre_entries = 0
if _doc.load():
    _pre_entries = len(_doc._ENTRIES)

EVENTS = []
_t0 = time.time()
_round_marks = []

def on_event(ev):
    EVENTS.append(dict(ev, _t=round(time.time() - _t0, 1)))
    t = ev.get("type", "?")
    txt = str(ev.get("text", ""))[:110]
    print(f"[{EVENTS[-1]['_t']:7.1f}s][{t:18s}] {txt}", flush=True)
    # crash-safe: the event log IS the calibration data — append it
    # incrementally so an OS-level death (D2 at r52) keeps everything.
    try:
        _tr_flush("event", dict(ev, _t=EVENTS[-1]["_t"]))
    except Exception:
        pass

# ── run the mission ────────────────────────────────────────────────────
from core.agent import Agent
from core.report import write_report

agent = Agent(cfg)
transcript = agent.run(MISSION, on_event=on_event)

# ── post-mission state capture ────────────────────────────────────────
_dt = time.time() - _t0
_doc2 = __import__("core.doctrine", fromlist=["doctrine"])
post_entries = len(_doc2._ENTRIES) if _doc2.load() else 0
sk = _sl.summary()

surprise = {}
try:
    for k, ring in getattr(_wm, "_SURPRISE", {}).items():
        surprise[k] = list(ring)[-5:]
except Exception:
    pass

try:
    plays = _doc2  # placeholder
except Exception:
    pass

from core import dream as _dr
try:
    plays_now = _dr.load_plays(limit=64)
except Exception:
    plays_now = []

dump = {
    "run_id": RUN_ID,
    "mission": MISSION,
    "wall_clock_s": round(_dt, 1),
    "events": EVENTS,
    "rounds": len([1 for k, _ in transcript if k == "assistant"]),
    "tool_calls": len([1 for k, _ in transcript if k == "tool"]),
    "skip_summary": sk,
    "doctrine_pre_entries": _pre_entries,
    "doctrine_post_entries": post_entries,
    "surprise_rings": surprise,
    "plays_loaded_at_end": len(plays_now),
    "transcript_len": len(transcript),
}
with open(os.path.join(OUT, "capture.json"), "w", encoding="utf-8") as f:
    json.dump(dump, f, ensure_ascii=False, indent=1)

# full transcript dump
with open(os.path.join(OUT, "transcript.jsonl"), "w", encoding="utf-8") as f:
    for kind, entry in transcript:
        try:
            f.write(json.dumps({"kind": kind, "entry": entry},
                               ensure_ascii=False, default=str) + "\n")
        except Exception:
            f.write(json.dumps({"kind": kind, "entry": str(entry)[:2000]},
                               ensure_ascii=False) + "\n")

# doctrine state
try:
    _doc2.reset(); _doc2.load()
    with open(os.path.join(OUT, "doctrine_state.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": _doc2._ENTRIES,
                   "graveyard": _doc2._GRAVEYARD},
                  f, ensure_ascii=False, indent=1, default=str)
except Exception:
    pass

# the final report
try:
    os.makedirs(os.path.join(OUT, "reports"), exist_ok=True)  # calib fix
    path = write_report(MISSION, transcript,
                        os.path.join(OUT, "reports"))
    print(f"[report] {path}")
except Exception as ex:
    print(f"[report] write failed: {ex}")

print(f"\n[CALIB {RUN_ID}] DONE in {_dt:.0f}s — "
      f"{dump['tool_calls']} tool calls, "
      f"doctrine {dump['doctrine_pre_entries']}→{post_entries}, "
      f"skips total={sk.get('total', 0)}")
