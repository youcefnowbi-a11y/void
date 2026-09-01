"""VOIDFORGE :: TRAJECTORY ARCHIVE — the CAI recipe, in miniature.

Every tool run of every mission appends one JSONL line:
    {ts, mission_id, target, round, tool, ok, dur, args}
The file is the raw memory of WHICH SEQUENCES WIN. Trajectory insight rebuilds
bigram transitions (tool_a -> tool_b, success rate of B after A) plus per-tool
reliability — the strategist and the MCTS can consult what previous missions
proved instead of starting every campaign from zero.

Thread-safe (swarm runs parallel specialists), crash-safe (append-only).
"""
import json
import os
import re
import threading
import time
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_DIR = os.path.join(_HERE, os.pardir, "missions", "_trajectories")
_PATH = os.path.join(_DIR, "trajectories.jsonl")
_LOCK = threading.Lock()
_MAX_LINES = 200_000  # cible documentée — le « leash » devient réel ci-dessous
_MAX_BYTES = 30_000_000  # ~200k lignes JSONL ≈ 30 Mo (R2-7 : garde réelle)
_TAIL_LINES = 2000  # seule la queue du corpus est parsée par insight()

# ── G12: typed vulnerability states (PentAGI taxonomy, adapted) ──
# attempted → detected → confirmed → exploited. Memory distinguishes "tried"
# from "proven" — insight never mistakes motion for progress.
STATE_WEIGHT = {"attempted": 1, "detected": 2, "confirmed": 3, "exploited": 4}
# Audit#5 durci: les marqueurs de preuve ne comptent qu'en DÉBUT DE LIGNE
# (verdict des outils), dans les 2000 premiers chars — un "exploited" au
# milieu d'un dump HTML ne fait plus halluciner un état.
_EVIDENCE_CONFIRM = re.compile(r"(?im)^\s*(?:#{1,4}\s*)?VERIFIED\b|^\s*VERIFIED_[A-Z_]+")
_EVIDENCE_EXPLOIT = re.compile(r"(?im)^\s*(?:#{1,4}\s*)?(?:EXPLOITED\b|RCE CONFIRMED|SHELL ACQUIRED|EXFILTRATED\b)")


def evidence_state(name, ok, out):
    """G11 ground-truth lens: derive the honest state from the OUTPUT ITSELF —
    never from the tool's self-reported success. Hard evidence beats `ok` in
    BOTH directions: ok sans preuve = detected (pas confirmed); preuve
    EXPLOITED même avec ok=False (l'outil a réussi puis crashé) = exploited."""
    blob = (out or "")[:2000]
    if _EVIDENCE_EXPLOIT.search(blob):
        return "exploited"
    if _EVIDENCE_CONFIRM.search(blob):
        return "confirmed"
    return "detected" if ok else "attempted"


def record(mission_id, target, tool, ok, duration, round_num=0, args_digest="",
           state=None):
    """Append one tool-run event. Never raises into the mission loop."""
    try:
        os.makedirs(_DIR, exist_ok=True)
        state = state or ("detected" if ok else "attempted")
        line = json.dumps({
            "ts": round(time.time(), 3),
            "mission_id": mission_id,
            "target": (target or "unknown")[:120],
            "round": round_num,
            "tool": (tool or "")[:60],
            "ok": bool(ok),
            "dur": round(float(duration or 0), 2),
            "args": (args_digest or "")[:200],
            "state": state,
        }, ensure_ascii=False)
        with _LOCK:
            with open(_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            # R2-7 : rotation une seule fois au franchissement du seuil
            # (pas par ligne) — l'historique part dans une archive horodatée.
            try:
                if os.path.exists(_PATH) and os.path.getsize(_PATH) > _MAX_BYTES:
                    stamp = time.strftime("%Y%m%dT%H%M%S")
                    os.replace(_PATH,
                               os.path.join(_DIR, f"trajectories-{stamp}.jsonl"))
            except OSError:
                pass  # lecteur concurrent : nouvelle tentative au prochain record
    except Exception:
        pass


def _count_lines(path):
    """Comptage par blocs de 1 Mo — O(octets), zéro parse JSON (R2-7)."""
    n = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                n += chunk.count("\n")
    except Exception:
        pass
    return n


def _events():
    """R2-7 : seule la queue du corpus alimente les bigrammes — on saute
    l'entête (n - 2000 lignes) et on parse uniquement la fin du fichier."""
    evs = []
    try:
        n_lines = _count_lines(_PATH)
        with open(_PATH, encoding="utf-8", errors="replace") as f:
            skip = max(0, n_lines - _TAIL_LINES)
            for _ in range(skip):
                if not f.readline():
                    break
            for line in f:
                try:
                    evs.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return evs


def tool_reliability(limit=15):
    """Per-tool success rate + count across all archived missions."""
    stats = defaultdict(lambda: [0, 0.0])  # tool -> [n, sum(dur)]
    for e in _events():
        t = e.get("tool")
        if not t:
            continue
        s = stats[t]
        s[0] += 1
        s[1] = e.get("ok") and (s[1] + 1) or s[1]
    out = []
    for t, (n, wins) in sorted(stats.items(), key=lambda kv: -kv[1][0])[:limit]:
        out.append({"tool": t, "runs": n, "success_rate": round(wins / n, 2) if n else 0})
    return out


def chains(min_support=2, limit=10):
    """Bigram transitions A->B with B's success rate when it follows A.
    This is the seed of the winning-sequence memory."""
    seqs = defaultdict(list)  # mission_id -> [tool, ...] in ts order
    ok_by_key = {}
    for e in _events():
        mid = e.get("mission_id")
        if mid is None:
            continue
        seqs[mid].append(e)
    trans = defaultdict(lambda: [0, 0, 1])  # (a,b) -> [n, wins_b, best_weight]
    for mid, evs in seqs.items():
        evs.sort(key=lambda e: e.get("ts", 0))
        for a, b in zip(evs, evs[1:]):
            k = (a.get("tool"), b.get("tool"))
            if not k[0] or not k[1]:
                continue
            t = trans[k]
            t[0] += 1
            if b.get("ok"):
                t[1] += 1
            w = STATE_WEIGHT.get(b.get("state") or
                                 ("detected" if b.get("ok") else "attempted"), 1)
            if w > t[2]:
                t[2] = w
    ranked = sorted(((k, v) for k, v in trans.items() if v[0] >= min_support),
                    key=lambda kv: (kv[1][2], kv[1][1] / kv[1][0], kv[1][0]),
                    reverse=True)
    w2s = {v: k for k, v in STATE_WEIGHT.items()}
    return [{"chain": f"{k[0]} -> {k[1]}", "seen": v[0],
             "success_rate": round(v[1] / v[0], 2),
             "best_state": w2s.get(v[2], "attempted")}
            for k, v in ranked[:limit]]


def insight(min_support=2):
    """Full insight block for the strategist: reliability + winning chains."""
    n = _count_lines(_PATH)  # R2-7 : comptage par blocs, plus de scan-par-ligne
    return json.dumps({
        "corpus_events": n,
        "tool_reliability": tool_reliability(),
        "proven_chains": chains(min_support=min_support),
        "note": "chaînes classées par taux de réussite de l'étape finale (support >= "
                f"{min_support} missions). Pioche ces enchaînements avant d'improviser.",
    }, ensure_ascii=False, indent=1)
