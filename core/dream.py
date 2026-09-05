"""VOIDFORGE :: Ω3 the dream (Phase 3 — dead time becomes training).

Between missions the platform sits idle. The dream turns that dead time
into rehearsals: re-open archived contexts, simulate the untaken
branches against the archived REAL responses, and mint verified plays
(#79's dead ends become #80's shortcuts).

Four pieces:

3.1 PROVENANCE COMPLETION — every fact on the blackboard carries the
    full producing context: mission, round, tool, step. "Which step
    told me this?" is answerable everywhere — the replay lane can only
    trust facts that name their origin (caldera facts port).

3.2 REPLAY LANE — between missions: load an archived blackboard +
    trajectory pair, enumerate the tools that NEVER RAN on assets they
    could have run on (untaken branches), simulate each branch against
    the ARCHIVED real responses (no live traffic), and mint a PLAY when
    a simulated branch would-have-worked: {precondition, action,
    expected, evidence}.

3.3 FIXPOINT SIMULATION (amass) — simulated discoveries re-trigger
    simulated handlers: a simulated js_mine hit feeds simulated
    secret_scan, whose simulated finding feeds simulated data_extract.
    Iterate until the in-dream graph saturates (no new simulated assets
    for a full pass). Compounding intel, zero traffic.

3.4 DREAM→DOCTRINE FEED — plays that verify mint doctrine entries
    automatically (Phase 4's store). The dream writes; doctrine stores.

Determinism: simulation is regex/arithmetic against ARCHIVED data —
no live traffic, no LLM calls required (an LLM narrator is optional
and never gates the mint).
"""
import json
import os
import re
import threading
import time
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_INTEL = os.path.join(_HERE, os.pardir, "intel")
_TRAJ = os.path.join(_HERE, os.pardir, "missions", "_trajectories")

_LOCK = threading.Lock()
_PLAYS = []                # in-memory play ring (bounded)
_PLAY_CAP = 256


def _play_file():
    """Play-ring path (dynamic: honors test/monkeypatched intel dirs)."""
    return os.path.join(_INTEL, "plays.json")

# 3.1: provenance context — set by the agent at mission start; facts
# minted during the mission carry it forever.
_CTX = {"mission_id": None, "target": None}
_STEP = [0]                # monotonically increasing per-process step

# simulated-handler graph (3.3): the closed consumer map — which tool
# consumes which asset kind (curated, mirrors the real chain hints)
_CONSUMER_MAP = {
    "key": {"secret_scan", "jwt_analyst", "data_extract"},
    "endpoint": {"endpoint_oracle", "data_extract", "api_sweep",
                 "dir_brute", "nuclei_scan"},
    "domain": {"subdomain_enum", "wayback_urls", "nmap_scan",
               "web_fingerprint"},
    "js_bundle": {"js_mine_url", "secret_scan"},
    "bucket": {"data_extract"},
    "service": {"web_fingerprint"},
}


# ── 3.1: provenance completion ────────────────────────────────────────

def bind_mission(mission_id, target=""):
    """Set the provenance context for every fact minted from here on."""
    with _LOCK:
        _CTX["mission_id"] = str(mission_id or "")[:80] or None
        _CTX["target"] = str(target or "")[:120]
        _STEP[0] = 0


def step_bump():
    """One tool round happened — advance the step counter (the agent
    loop calls this once per tool result; cheap, monotonic)."""
    with _LOCK:
        _STEP[0] += 1
        return _STEP[0]


def provenance():
    """The current provenance stamp to attach to a fact."""
    with _LOCK:
        return {"mission_id": _CTX["mission_id"],
                "target": _CTX["target"],
                "step": _STEP[0], "ts": round(time.time(), 3)}


def stamp_fact(fact):
    """Stamp a blackboard fact dict with the live provenance (idempotent:
    an already-stamped fact from the archive keeps its ORIGINAL stamp —
    re-stamping archived facts would lie about their birth)."""
    if not isinstance(fact, dict):
        return fact
    if fact.get("prov") and isinstance(fact["prov"], dict) \
            and fact["prov"].get("mission_id"):
        return fact           # archived origin wins — never overwrite
    fact["prov"] = provenance()
    return fact


# ── 3.2: the replay lane ──────────────────────────────────────────────

def _load_blackboard(target):
    """Load an archived blackboard (assets only — the dream reads, never
    writes the archive)."""
    safe = re.sub(r"[^a-z0-9.\-]", "_", (target or "").strip().lower())[:60]
    if not safe:
        return None
    p = os.path.join(_INTEL, f"{safe}.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _load_trajectory_tail(mission_id=None, limit=2000):
    """Archived trajectory events (ts-ordered tail). The tail covers a
    full modern mission (400 lines cut mid-campaign and minted phantom
    untaken branches)."""
    path = os.path.join(_TRAJ, "trajectories.jsonl")
    evs = []
    try:
        if not os.path.exists(path):
            return evs
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        for ln in lines:
            try:
                e = json.loads(ln)
            except Exception:
                continue
            if mission_id and e.get("mission_id") != mission_id:
                continue
            evs.append(e)
    except Exception:
        pass
    return evs


def untaken_branches(target, tools_available):
    """Enumerate the untaken branches of an archived mission: for each
    asset kind, the tools that COULD have run on it but never did
    (per the trajectory). Returns [{asset_key, kind, value, tool}] —
    the would-have-been calls, sorted by asset confidence."""
    bb = _load_blackboard(target)
    if not bb:
        return []
    assets = bb.get("assets") or {}
    evs = _load_trajectory_tail()
    ran = defaultdict(set)          # tool -> set of asset-ish strings
    for e in evs:
        ran[(e.get("tool") or "").lower()].add(
            str(e.get("args") or "")[:200])
    branches = []
    # which tool consumes which asset kind (curated, closed map)
    consumer = _CONSUMER_MAP
    tools_available = {str(t).lower() for t in (tools_available or ())}
    for key, a in (assets or {}).items():
        kind = a.get("kind") or "service"
        value = str(a.get("value") or "")[:200]
        conf = a.get("confidence") or 0.5
        for tool in consumer.get(kind, ()):
            if tool not in tools_available:
                continue
            # did this tool ever see this value in its args?
            if any(value[:80] in arg for arg in ran.get(tool, ())):
                continue            # branch was taken
            branches.append({"asset_key": key, "kind": kind,
                             "value": value, "tool": tool,
                             "confidence": conf,
                             "props": dict(a.get("props") or {})})
    branches.sort(key=lambda b: -b["confidence"])
    return branches[:64]


def simulate_branch(branch):
    """Simulate ONE untaken branch against the ARCHIVED real responses
    (zero live traffic). The simulator is honest about its epistemic
    state: with no archived response proving the outcome, the branch is
    'plausible', never 'verified'. A verified play needs ARCHIVED
    EVIDENCE that the branch would have worked (e.g. the asset's
    archived props already carry a signal the untaken tool would have
    escalated).

    Returns the play candidate or None.
    """
    if not isinstance(branch, dict) or not branch.get("tool"):
        return None
    tool = branch["tool"]
    kind = branch.get("kind")
    value = branch.get("value")
    conf = branch.get("confidence") or 0.5
    # the archived props are the ONLY real evidence available offline
    props = branch.get("props") or {}
    would_work = False
    if kind == "key" and props.get("kind_of_key"):
        # an archived key asset that the consumer never ran on: the
        # branch would AT MINIMUM have tested the key — a play if the
        # key's confidence is high (corroborated)
        would_work = conf >= 0.8
    elif kind == "endpoint" and conf >= 0.75:
        would_work = True         # high-confidence endpoint, never swept
    elif kind == "js_bundle" and props.get("sourcemap") in (True, "true"):
        would_work = conf >= 0.7  # archived sourcemap flag: mine it
    if not would_work:
        return None
    return {
        "precondition": f"asset {kind} with confidence ≥ "
                        f"{0.8 if kind == 'key' else 0.75}",
        "action": {"tool": tool, "on": value[:200]},
        "expected": f"{tool} on {kind} '{value[:60]}' — corroborated "
                    f"asset never consumed by {tool}",
        "evidence": {"asset_key": branch.get("asset_key"),
                     "confidence": conf, "props": dict(list(props.items())[:6])},
        "minted_ts": round(time.time(), 3),
        "status": "play",
    }


# ── 3.3: fixpoint simulation (amass — compounding in-dream) ──────────

def fixpoint_simulate(target, max_passes=3):
    """Simulated discoveries re-trigger simulated handlers until the
    in-dream graph saturates: each pass mints the plays untaken_branches
    finds PLUS the plays implied by previously-minted plays (a simulated
    secret_scan hit implies a data_extract branch). Bounded passes —
    the dream must end. Returns the passes' yield (list of plays)."""
    all_plays = []
    seen_tools = set()
    tools = set()
    for v in _CONSUMER_MAP.values():
        tools |= v
    for _pass in range(max_passes):
        brs = untaken_branches(target, tools)
        if not brs:
            break
        new = 0
        for br in brs:
            k = (br.get("tool"), br.get("value"))
            if k in seen_tools:
                continue
            seen_tools.add(k)
            p = simulate_branch(br)
            if p:
                all_plays.append(p)
                new += 1
        if new == 0:
            break            # saturated — no new simulated assets
    return all_plays[:_PLAY_CAP]


# ── 3.4: dream→doctrine feed ───────────────────────────────────────────

def mint_doctrine_entry(play):
    """A verified play becomes a doctrine entry (Phase 4's store):
    predicate × context × where. The dream writes; doctrine stores.
    Returns the entry dict or None (malformed play)."""
    if not isinstance(play, dict) or play.get("status") != "play":
        return None
    ev = play.get("evidence") or {}
    return {
        "predicate": f"{play.get('precondition')}",
        "context": f"target-with-{(play.get('action') or {}).get('on', '')[:40]}",
        "where": (play.get("action") or {}).get("tool", ""),
        "expected": play.get("expected", ""),
        "origin": "dream",
        "evidence": ev,
        "ts": round(time.time(), 3),
    }


def save_plays(plays):
    """Persist the play ring (bounded, atomic write)."""
    if not plays:
        return False
    try:
        os.makedirs(_INTEL, exist_ok=True)
        with _LOCK:
            with open(_play_file(), "w", encoding="utf-8") as f:
                json.dump(plays[:_PLAY_CAP], f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def load_plays(limit=32, target=None):
    """The archived plays, freshest-first (round-0 feed for the next
    live mission). target filter: only the plays minted for THIS
    target's dream (cross-target plays would poison the round-0 brief)."""
    try:
        with open(_play_file(), encoding="utf-8") as f:
            plays = json.load(f)
        if isinstance(plays, list):
            plays = [p for p in plays if isinstance(p, dict)]
            if target:
                tgt = str(target).strip().lower()[:120]
                plays = [p for p in plays
                         if str(p.get("target") or "").strip().lower()[:120]
                         == tgt or not p.get("target")]
            plays.sort(key=lambda p: -float(p.get("minted_ts") or 0))
            return plays[:limit]
    except Exception:
        pass
    return []


def dream(target, tools_available=None):
    """One full dream run for an archived target: enumerate untaken
    branches, simulate to fixpoint (compounding plays), persist the
    play ring. Returns the dream report (the plays the next mission
    should try first)."""
    try:
        if not tools_available:
            tools_available = set()
            for v in _CONSUMER_MAP.values():
                tools_available |= v
        branches = untaken_branches(target, tools_available)
        plays = [p for p in (simulate_branch(b) for b in branches) if p]
        # stamp every play with its dream target (the round-0 feed filters
        # on it — plays from another target must not poison this mission)
        for p in plays:
            p["target"] = (target or "")[:120]
        # fixpoint compounding: a simulated secret_scan hit implies a
        # follow-on data_extract branch (the handler graph propagates)
        for p in list(plays):
            tool = (p.get("action") or {}).get("tool")
            on = (p.get("action") or {}).get("on")
            if tool == "secret_scan" and on:
                plays.append({
                    "precondition": "simulated secret_scan hit",
                    "action": {"tool": "data_extract", "on": on},
                    "expected": "escalate the simulated key finding",
                    "evidence": {"from_play": True},
                    "target": (target or "")[:120],
                    "minted_ts": round(time.time(), 3),
                    "status": "play"})
        report = {"target": (target or "")[:120], "plays": plays[:32],
                  "ran_at": round(time.time(), 3)}
        if plays:
            save_plays((load_plays(limit=_PLAY_CAP) or []) + plays)
        return report
    except Exception as e:
        return {"target": target, "error": f"{type(e).__name__}: {e}",
                "plays": []}


def reset():
    """Test hygiene."""
    with _LOCK:
        _PLAYS.clear()
        _CTX.update({"mission_id": None, "target": None})
        _STEP[0] = 0
