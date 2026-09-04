"""VOIDFORGE :: belief memory — tested facts per target (Tier G4).

The plays/trajectory memory stores what WORKED (a grammar, a chain); it
cannot store what is TRUE about a target. Mission 75 rediscovered what
mission 74 had already tested. A researcher's real asset is a ledger of
BELIEFS: each one a tested claim about a specific target, with source,
age, confidence, and the exact re-test condition that would retire it.

Schema (data/learned/beliefs.json, gitignored):
{ "<target>": [ {"id", "claim", "verdict", "direction", "evidence",
                  "source_tool", "mission_id", "ts", "confidence"} ] }

API:
  record(target, claim, verdict, direction, evidence, source_tool,
         mission_id)  → belief dict (dedupes by claim-96; a re-test of the
                        same claim REVES confidence instead of stacking)
  recall(target, limit=40) → age-ranked, confidence-weighted list
  prompt_block(target) → compact round-0/round-N context block
  retire(target, claim_id) → drop a refuted belief
"""
import json
import os
import re
import time
import threading

_LOCK = threading.Lock()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "learned", "beliefs.json")
_MAX_PER_TARGET = 400
_MAX_BLOCK_CHARS = 3600


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(d):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PATH)
    except Exception:
        pass


def _norm_claim(claim):
    """Claim identity: lowercase, whitespace collapsed, terminal punctuation
    stripped — 'The server re-validates X!' and 'the server re-validates x'
    are THE SAME claim (a re-test, not a new belief)."""
    c = re.sub(r"\s+", " ", str(claim or "").strip()).lower()
    return re.sub(r"[!.?;:,]+$", "", c)[:96]


def record(target, claim, verdict, direction="violated", evidence="",
           source_tool="hypothesis_test", mission_id=None, confidence=None):
    """One tested fact. Same-claim re-tests REVISE confidence (a fresh
    CONFIRMED raises it toward 1.0; a fresh REFUTED sinks it toward 0 —
    beliefs age like science, not like stamps)."""
    if not target or not claim:
        return None
    with _LOCK:
        d = _load()
        beliefs = d.setdefault(str(target), [])
        key = _norm_claim(claim)
        existing = next((b for b in beliefs if b.get("_k") == key), None)
        ts = time.time()
        if existing:
            # Bayesian-flavored revision: n increments, confidence walks
            # toward the latest verdict with decaying step (1/(n+1))
            existing["n"] = int(existing.get("n", 1)) + 1
            step = 1.0 / existing["n"]
            v = 1.0 if verdict == "CONFIRMED" else (
                0.0 if verdict == "REFUTED" else 0.5)
            c = float(existing.get("confidence", 0.5))
            existing["confidence"] = round(
                min(1.0, max(0.0, c + (v - c) * step * 2)), 3)
            existing["verdict"] = verdict
            existing["ts"] = ts
            # Z4.1 (audit-5): a re-test that CONFIRMS must carry its own
            # direction — the first record's default ("violated") used to
            # persist forever, painting a confirmed defense as a violation.
            if verdict == "CONFIRMED":
                existing["direction"] = str(direction or "violated")[:12]
                existing["evidence"] = str(evidence or existing.get("evidence", ""))[:500]
            existing["mission_id"] = mission_id or existing.get("mission_id")
            existing["source_tool"] = source_tool or existing.get("source_tool")
            out = dict(existing)
        else:
            c = confidence if confidence is not None else (
                0.9 if verdict == "CONFIRMED" else (
                    0.85 if verdict == "REFUTED" else 0.5))
            belief = {
                "id": f"b{int(ts * 1000) % 100000000:08d}",
                "_k": key,
                "claim": str(claim)[:300],
                "verdict": str(verdict)[:16],
                "direction": str(direction or "violated")[:12],
                "evidence": str(evidence)[:500],
                "source_tool": str(source_tool or "")[:60],
                "mission_id": mission_id,
                "ts": ts, "n": 1,
                "confidence": round(float(c), 3),
            }
            beliefs.append(belief)
            while len(beliefs) > _MAX_PER_TARGET:
                beliefs.pop(0)
            out = dict(belief)
        _save(d)
    return out


def recall(target, limit=40):
    """Highest-value first: confidence desc, freshest wins ties."""
    with _LOCK:
        d = _load()
    beliefs = [dict(b) for b in d.get(str(target), [])]
    beliefs.sort(key=lambda b: (-(b.get("confidence") or 0),
                                -(b.get("ts") or 0)))
    for b in beliefs:
        b.pop("_k", None)
    return beliefs[:limit]


def retire(target, claim_id):
    with _LOCK:
        d = _load()
        beliefs = d.get(str(target))
        if not beliefs:
            return False
        before = len(beliefs)
        d[str(target)] = [b for b in beliefs if b.get("id") != claim_id]
        _save(d)
        return len(d[str(target)]) < before


def prompt_block(target, limit=18, cap=_MAX_BLOCK_CHARS):
    """Round-0 context: what is KNOWN about this target from past tests.
    High-confidence CONFIRMED violations first (skip re-deriving them),
    then proven defenses (don't re-prove what holds)."""
    if not target:
        return ""
    beliefs = recall(target, limit=limit * 3)
    if not beliefs:
        return ""
    violated = [b for b in beliefs
                if b["verdict"] == "CONFIRMED" and b["direction"] == "violated"]
    held = [b for b in beliefs
            if b["verdict"] == "CONFIRMED" and b["direction"] == "held"]
    L = ["═══ TARGET SCIENCE LEDGER (tested beliefs — do NOT re-derive) ═══"]
    if violated:
        L.append("Proven violations (impact chains to push further):")
        for b in violated[:limit]:
            age = int((time.time() - b.get("ts", 0)) / 86400)
            L.append(f"- [c={b['confidence']:.2f}] {b['claim']} "
                     f"({b['source_tool']}, {age}d old)")
    if held:
        L.append("Proven defenses (skip or re-test only with a NEW angle):")
        for b in held[:limit]:
            age = int((time.time() - b.get("ts", 0)) / 86400)
            L.append(f"- [c={b['confidence']:.2f}] {b['claim']} "
                     f"({b['source_tool']}, {age}d old)")
    if not violated and not held:
        return ""
    block = "\n".join(L)
    return block[:cap]
