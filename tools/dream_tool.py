"""VOIDFORGE :: dream_rehearsal tool (Ω3.2/3.3 — the replay lane).

Between-mission rehearsal: re-open the ARCHIVED blackboard of a target,
enumerate the branches that never ran, simulate them against archived
evidence (zero live traffic), mint the verified plays, and persist them
for the next mission's round-0 feed.

The dream is read-only toward the live world: no network calls, no
blackboard mutation — it reads the archive and writes only its own
play ring. An LLM narrator is NOT required (deterministic simulation).
"""
import json

from tools import register


@register(
    name="dream_rehearsal",
    desc="Between-mission rehearsal: mine the archived campaign of a "
         "target for untaken branches and mint verified plays for the "
         "next mission (zero live traffic, reads the archive only).",
    params={"type": "object",
            "properties": {
                "target": {"type": "string",
                           "description": "The archived target (domain or "
                                           "host) to dream about"},
                "max_plays": {"type": "integer",
                              "description": "Cap on returned plays "
                                              "(default 8)"}
            },
            "required": ["target"]},
    danger="safe")
def dream_rehearsal(target, max_plays=8):
    from core import dream
    if not target or not str(target).strip():
        return json.dumps({"error": "target required"}, ensure_ascii=False)
    report = dream.dream(str(target).strip())
    plays = report.get("plays") or []
    entries = [dream.mint_doctrine_entry(p) for p in plays]
    entries = [e for e in entries if e]
    out = {
        "tool": "dream_rehearsal",
        "target": report.get("target"),
        "plays_minted": len(plays),
        "doctrine_entries": entries[:6],
        "plays": [
            {"try_first": f"{p.get('action', {}).get('tool', '?')} on "
                          f"{str(p.get('action', {}).get('on', ''))[:80]}",
             "precondition": p.get("precondition", "")[:120],
             "expected": p.get("expected", "")[:160]}
            for p in plays[:int(max_plays or 8)]
        ],
        "note": "plays persisted — the next mission's round-0 feed loads "
                "them automatically",
    }
    if report.get("error"):
        out["sim_error"] = report["error"]
    return json.dumps(out, ensure_ascii=False, indent=1)
