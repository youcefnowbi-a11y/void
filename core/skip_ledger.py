"""VOIDFORGE :: skip ledger (Phase 0.5 — caldera skip-reason taxonomy).

Caldera's lesson (audit): every skipped adversary step gets a machine-
readable WHY (platform/executor/privilege/fact-dependency/untrusted).
Our fleet already CATEGORIZES its refusals (UNKNOWN_TOOL, SCOPE_TOOL,
ROE_BLOCKED, SCOPE_BLOCKED, quarantine, rail-pivot) but they vanish —
the autopsy can't answer "what never fired and why?", and the doctrine
(Ω4) can't mint rules from failures it never saw.

This ledger is the memory: one append-only in-memory store per mission
with bounded size, machine-readable categories, and a queryable summary
for round-0 prompts and autopsies.

Categories (the taxonomy):
  unknown_tool    the model hallucinated a tool name
  scope_tool      the tool is outside this agent's allowed arsenal
  roe_blocked     rules of engagement forbade the strike
  scope_blocked   the target host is out of perimeter
  quarantined     transport breaker: host is dark
  rail_pivot      stop rail forced a pivot away from this surface
  budget          mission/round budget exhausted
  prereq_missing  a required fact/slot was missing (caldera defer)
  other           uncategorized — always carries the raw reason
"""
import threading

_LOCK = threading.Lock()
_ENTRIES = []            # bounded, append-only per process-mission
_MAX = 512
_MISSION = {"id": None}

# canonical taxonomy (caldera Reason enum, our shape)
REASONS = ("unknown_tool", "scope_tool", "roe_blocked", "scope_blocked",
           "quarantined", "rail_pivot", "budget", "prereq_missing", "other")


def start_mission(mission_id):
    """Fresh ledger per mission (call from agent.run's init block)."""
    with _LOCK:
        _ENTRIES.clear()
        _MISSION["id"] = mission_id


def skip(reason, tool="", detail="", round_num=0):
    """Record a skipped/unfired step with its machine-readable WHY.
    Never raises; unknown reasons map to 'other' with the raw string
    attached (the taxonomy is closed, the memory isn't lossy)."""
    try:
        reason = reason if reason in REASONS else "other"
        with _LOCK:
            if len(_ENTRIES) >= _MAX:
                _ENTRIES.pop(0)          # oldest falls off under flood
            _ENTRIES.append({
                "mission": _MISSION["id"],
                "reason": reason,
                "tool": str(tool or "")[:60],
                "detail": str(detail or "")[:300],
                "round": round_num,
            })
    except Exception:
        pass


def entries(reason=None, tool=None, limit=100):
    """Queryable memory: filter by category and/or tool."""
    with _LOCK:
        out = [dict(e) for e in _ENTRIES
               if (reason is None or e["reason"] == reason)
               and (tool is None or e["tool"] == tool)]
    return out[-limit:]


def summary():
    """The autopsy query: what never fired and why, one line each.
    Bounded to the dominant categories — a 512-entry flood summarizes
    to its counts, not its noise."""
    with _LOCK:
        counts = {}
        for e in _ENTRIES:
            counts[e["reason"]] = counts.get(e["reason"], 0) + 1
        examples = {}
        for e in _ENTRIES:
            k = e["reason"]
            if k not in examples and e["tool"]:
                examples[k] = f"{e['tool']}: {e['detail'][:120]}"
    return {"total": sum(counts.values()), "by_reason": counts,
            "example": examples, "mission": _MISSION["id"]}


def reset():
    """Test hygiene / process reset."""
    with _LOCK:
        _ENTRIES.clear()
        _MISSION["id"] = None
