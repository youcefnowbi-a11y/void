"""VOIDFORGE :: Ω4 doctrine (Phase 4 — the loop closes; the system
writes itself).

The doctrine is the SELF-AUTHORED law: entries minted by autopsies,
dreams, and missions — machine-checkable, read at round 0, and
self-verifying (doctrine that stops working retires gracefully).

Four pieces:

4.1 DOCTRINE ENTRIES — predicate × context × where triples (sqlmap's
    grammar): "ON <context>: <predicate> → <where>". Authored by
    autopsies (mission ends), dreams (3.4 feed), and missions (the
    agent's own report minting); read at round 0.

4.2 PREDICATE TERMINATION (caldera) — mission goals as countable fact
    predicates: Goal{trait, value, count}. A brief like "pull 3 admin
    API keys" becomes countable against the blackboard: goal met when
    the map holds N assets of the trait.

4.3 SKIP-TAUGHT DOCTRINE — the autopsy's skip taxonomy generates rules:
    "never X on Y because Z" (unknown_tool hallucinations → naming
    doctrine; quarantine skips → patience rules; rail pivots →
    wall-avoidance rules). Failures become rules, not just scars.

4.4 DOCTRINE SELF-VERIFICATION — every entry carries evidence links and
    a Bayesian score (like the blackboard's belief fusion): used-and-
    worked reinforces, used-and-failed decays; below the retire
    threshold the entry archives itself (never hard-deleted — the
    graveyard is auditable).

Determinism: pure arithmetic + regex; the doctrine READS the world's
verdicts, it never computes them itself.
"""
import json
import os
import re
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_DOCTRINE_DIR = os.path.join(_HERE, os.pardir, "intel")
_DOCTRINE_FILE = os.path.join(_DOCTRINE_DIR, "doctrine.json")

_LOCK = threading.RLock()      # RLock: report_use (holding) may save()
_ENTRIES = []                 # live entries
_GRAVEYARD = []               # retired entries (auditable)
_MAX_ENTRIES = 512
_RETIRE_AT = 0.25             # Bayesian score below this → retire

# 4.2: goal predicate grammar — "trait: value" pairs with counts
_GOAL_RE = re.compile(
    r"(?P<trait>[a-z_]+)\s*[:=]\s*(?P<value>[a-z0-9_.\-]+)"
    r"(?:\s*(?:x|×|count)\s*(?P<count>\d+))?", re.IGNORECASE)


# ── 4.1: doctrine entries ─────────────────────────────────────────────

def add_entry(predicate, context, where, expected="", origin="autopsy",
              evidence=None):
    """Mint a doctrine entry (predicate × context × where). Idempotent
    per triple: re-minting the same triple reinforces the existing
    entry instead of duplicating it."""
    predicate = str(predicate or "").strip()[:300]
    context = str(context or "").strip()[:200]
    where = str(where or "").strip()[:120]
    if not predicate or not where:
        return None
    with _LOCK:
        # final-audit fix B5: consult the graveyard BEFORE minting — a
        # retired triple used to resurrect at the full 0.6 prior (revolving
        # door: "real retirement" never terminally retired recurring
        # patterns). A re-observation of retired law re-arms BELOW the
        # retire line, carrying its history; it must PROVE itself again.
        for gi, ge in enumerate(_GRAVEYARD):
            if (ge.get("predicate") == predicate
                    and ge.get("context") == context
                    and ge.get("where") == where):
                e = dict(ge)
                e["score"] = _RETIRE_AT - 0.05   # re-armed under the line
                e["re_armed_from_graveyard"] = True
                e["ts"] = round(time.time(), 3)
                _ENTRIES.append(e)
                _GRAVEYARD.pop(gi)
                return e
        for e in _ENTRIES:
            if e["predicate"] == predicate and e["context"] == context \
                    and e["where"] == where:
                # same triple re-observed: light reinforcement
                e["score"] = min(1.0, e["score"] + 0.02)
                e["times_re_minted"] = e.get("times_re_minted", 1) + 1
                return e
        e = {"predicate": predicate, "context": context, "where": where,
             "expected": str(expected or "")[:300],
             "origin": str(origin or "autopsy")[:40],
             "evidence": dict(evidence or {}) if isinstance(evidence, dict) else {},
             "score": 0.6,              # prior: minted = believed
             "used": 0, "worked": 0, "failed": 0,
             "times_re_minted": 1,
             "ts": round(time.time(), 3)}
        _ENTRIES.append(e)
        if len(_ENTRIES) > _MAX_ENTRIES:
            # retire the weakest beyond the cap (never hard-delete)
            _ENTRIES.sort(key=lambda e: e["score"])
            while len(_ENTRIES) > _MAX_ENTRIES:
                _GRAVEYARD.append(_ENTRIES.pop(0))
        return e


_UNIVERSAL_CTX = {"", "any-target", "any", "all", "*"}
# calib-B fix: mint_wins/skip_taught minted context "any-target" — a
# LITERAL that never matched any hostname (round0_block filter). These
# sentinels are now first-class universal contexts everywhere.


def round0_block(target="", limit=10):
    """The doctrine the agent READS at round 0: live entries, strongest
    first, rendered as machine-checkable rules. Only entries whose
    context matches the target (empty/universal context = always) ride."""
    with _LOCK:
        t = (target or "").strip().lower()
        live = [e for e in _ENTRIES
                if e["context"].strip().lower() in _UNIVERSAL_CTX
                or (t and (e["context"].lower() in t
                           or _ctx_matches(e["context"], t)))]
        live.sort(key=lambda e: -e["score"])
        block = "\n".join(
            f"- ON {e['context'] or 'any target'}: {e['predicate']} "
            f"→ {e['where']}"
            + (f" (expected: {e['expected'][:100]})" if e["expected"] else "")
            + (f" [confidence {e['score']:.2f}, {e['worked']}✓/{e['failed']}✗]"
               if (e["worked"] or e["failed"]) else "")
            for e in live[:limit])
    return ("DOCTRINE (self-authored law — prior missions wrote these "
            "rules; they carry evidence):\n" + block) if block else ""


def _ctx_matches(ctx, target):
    """Fuzzy context match: domain suffixes and keywords."""
    if not ctx or not target:
        return False
    c = ctx.lower()
    t = target.lower()
    if c in t or t in c:
        return True
    # suffix family match (context "marketplace" matches target with
    # that keyword anywhere — the curated context vocab is words, not URLs)
    return bool(re.search(r"\b" + re.escape(c[:40]) + r"\b", t))


# ── 4.2: predicate termination (caldera Goal{trait,value,count}) ──────

def parse_goals(brief):
    """Extract countable goal predicates from a mission brief.

    Grammar honored: `trait: value` optionally followed by `xN` — and
    the explicit `Goal{trait: value xN}` caldera form. Loose natural
    language without the grammar yields no goals (honesty over
    hallucination). Reserved words never consume a following pair:
    'Goal: keys: admin x3' must yield keys=admin x3, not eat 'keys'
    as Goal's value and leave 'admin' orphaned.
    """
    goals = []
    if not isinstance(brief, str):
        return goals
    s = brief[:4000]
    # strip explicit Goal{...} wrappers first (caldera form) so the
    # inner pair parses cleanly
    s = re.sub(r"(?i)goal\s*\{([^}]*)\}", r" \1 ", s)
    s = re.sub(r"(?i)\bgoal\s*:", " ", s)     # 'Goal:' prefix noise
    for m in _GOAL_RE.finditer(s):
        trait = m.group("trait").lower()
        value = m.group("value").lower()
        if trait in ("trait", "value", "count", "goal", "goals"):
            continue      # literal grammar noise
        g = {"trait": trait, "value": value}
        g["count"] = int(m.group("count")) if m.group("count") else 1
        goals.append(g)
    return goals[:8]


def goal_progress(goals, blackboard_assets):
    """Count each goal against the live blackboard assets:
    Goal{trait, value, count} met when ≥ count assets whose value/
    props match the trait:value predicate. Returns per-goal status."""
    out = []
    for g in goals or []:
        trait, value, need = g.get("trait"), g.get("value"), g.get("count", 1)
        have = 0
        for a in (blackboard_assets or []):
            if not isinstance(a, dict):
                continue
            props = a.get("props") or {}
            v = str(a.get("value") or "").lower()
            if (props.get(trait) == value
                    or (value and value in v)):
                have += 1
        out.append({"goal": g, "have": have, "need": need,
                    "met": have >= need})
    return out


# ── 4.3: skip-taught doctrine ────────────────────────────────────────

# curated translation: skip category → rule template
_SKIP_RULES = {
    "unknown_tool": ("the model hallucinated '{detail}' — the arsenal "
                     "names are in the catalog; check names before calling",
                     "naming"),
    "quarantined": ("host went dark mid-campaign (3 transport deaths) — "
                    "verify host health before strikes",
                    "patience"),
    "rail_pivot": ("a stop rail forced a pivot — the wall was real; do "
                   "not re-attack the same surface with the same vector",
                   "wall-avoidance"),
    "scope_blocked": ("target drifted outside the operator's perimeter — "
                      "stay inside the sanctioned scope", "discipline"),
    "roe_blocked": ("rules of engagement forbade the strike — recon only, "
                    "record the finding without exploiting", "roe"),
    "prereq_missing": ("a required fact/slot was missing at call time — "
                        "recon the prerequisite first, then re-fire",
                        "sequencing"),
}


def skip_taught(skip_summary):
    """Autopsy feed: the skip ledger's summary (by_reason counts +
    example strings) becomes doctrine entries. Failures become rules.

    Shape honored (core/skip_ledger.summary()):
      {"total": n, "by_reason": {reason: count},
       "example": {reason: "tool: detail"}, "mission": id}
    """
    minted = []
    if not isinstance(skip_summary, dict):
        return minted
    counts = skip_summary.get("by_reason") or {}
    examples = skip_summary.get("example") or {}
    if not isinstance(counts, dict) or not isinstance(examples, dict):
        return minted
    for cat, n in counts.items():
        tpl, where = _SKIP_RULES.get(cat, (None, None))
        if not tpl or not n:
            continue
        example = str(examples.get(cat) or "")[:120]
        e = add_entry(
            predicate=tpl.format(detail=example or "a tool"),
            context="any-target",
            where=where,
            expected="skips of this class cost "
                     f"{n} calls last mission",
            origin="skip-autopsy",
            evidence={"category": cat, "count": n, "example": example})
        if e:
            minted.append(e)
    return minted


# ── 4.3b: win-taught doctrine (calib-A weakness fix) ──────────────────
# The autopsy minted only FAILURE rules; the self-discovered WINS
# (openapi.json pattern, X-Admin-Token grammar, forged grep weapons)
# minted nothing — asymmetric learning. mint_wins() scans the mission
# transcript for verifiable high-value patterns and mints them as
# doctrine entries so the next mission starts knowing them.

# verifiable win signatures: (regex over tool args+result, predicate,
#                             where-tool, expected)
# final-audit fix B2: every signature now anchors on SUCCESS-shaped
# evidence — a bare mention (a failed openapi pull, a plan sentence, a
# header NAME sighted) can no longer mint win-law. Cross-line slop is
# out: each sig must match inside a single line/entry.
_WIN_SIGNATURES = [
    # a 200 (or 403-gated-exists proof via X-Admin) openapi FETCH that
    # actually returned a schema body — "\"status\": 200" adjacency
    (r"openapi[._-]?json.{0,120}?\\?\"status\\?\"\s*:\s*(200|403)",
     "FastAPI/exposure plane: pull openapi.json FIRST (auto-published "
     "schema names every endpoint including admin ones)",
     "api_sweep"),
    # the H() builder actually LOCATED — hit-context (path:NNN or
    # match-line), not a bare header-name sighting
    (r"X-Admin-Token.{0,200}?(path|line|match|match_no|hit)",
     "the admin gate is a single shared-secret header (X-Admin-Token) "
     "found client-side in gate JS — extract the H() builder, not the "
     "login flow",
     "file_grep"),
    # a forged weapon that actually MINTED (ok:true right at the head)
    (r"forge_tool.{0,60}?\\?\"ok\\?\"\s*:\s*true",
     "when display truncation hides grammar, FORGE a grep/extraction "
     "weapon instead of re-pulling with data_extract",
     "forge_tool"),
]


def mint_wins(transcript):
    """Scan the mission transcript for self-discovered winning patterns.
    Deterministic regex over tool args + result strings; mints doctrine
    entries with origin 'win-taught'. Returns the minted entries."""
    minted = []
    try:
        blob = ""
        for kind, entry in (transcript or [])[:600]:
            _s = str(entry)
            # B2: failures never mint wins — skip error/refusal entries
            if kind == "error" or "TOOL ERROR" in _s[:200]:
                continue
            blob += _s[:1500] + "\n"
        blob = blob[:400000]
        for rx, predicate, where in _WIN_SIGNATURES:
            m = re.search(rx, blob, re.IGNORECASE | re.DOTALL)
            if m:
                e = add_entry(
                    predicate=predicate, context="any-target",
                    where=where,
                    expected="self-discovered pattern reproduced across "
                             "missions",
                    origin="win-taught",
                    evidence={"signature": rx[:80],
                              "hit": m.group(0)[:120]})
                if e:
                    minted.append(e)
    except Exception:
        pass
    return minted


# ── 4.4: self-verification (Bayesian, like the belief fusion) ────────

def report_use(entry_or_triple, worked):
    """The world's verdict on a doctrine entry: used-and-worked
    reinforces, used-and-failed decays. The score is the smoothed
    success RATE (Laplace: (worked+1)/(used+2)) blended with the prior
    — one failure on a fresh entry decays it gently (0.6 → 0.47), not
    to the graveyard; repeated failures converge below the retire
    threshold. Below the threshold the entry archives itself into the
    graveyard (auditable, never lost)."""
    with _LOCK:
        e = _find(entry_or_triple)
        if not e:
            return None
        e["used"] += 1
        if worked:
            e["worked"] += 1
        else:
            e["failed"] += 1
        # smoothed rate: (worked+1)/(used+2) — Laplace prior at 0.5
        rate = (e["worked"] + 1) / (e["used"] + 2)
        # blend with the mint prior: recent verdicts dominate slowly
        e["score"] = round(0.6 * rate + 0.4 * e["score"], 3)
        if e["score"] < _RETIRE_AT:
            _ENTRIES.remove(e)
            e["retired_ts"] = round(time.time(), 3)
            _GRAVEYARD.append(e)
            # persist the retire immediately (a mission crash between
            # here and the autopsy must not resurrect a dead rule)
            try:
                save()
            except Exception:
                pass
            return {"retired": True, "entry": e}
        return {"retired": False, "entry": e}


def _find(entry_or_triple):
    """Locate an entry: by dict identity, or by its (predicate, context,
    where) triple."""
    if isinstance(entry_or_triple, dict):
        for e in _ENTRIES:
            if e is entry_or_triple:
                return e
            if (e["predicate"] == entry_or_triple.get("predicate")
                    and e["context"] == entry_or_triple.get("context")
                    and e["where"] == entry_or_triple.get("where")):
                return e
        return None
    if isinstance(entry_or_triple, (tuple, list)) and len(entry_or_triple) >= 3:
        p, c, w = entry_or_triple[0], entry_or_triple[1], entry_or_triple[2]
        for e in _ENTRIES:
            if e["predicate"] == p and e["context"] == c and e["where"] == w:
                return e
    return None


# ── persistence ───────────────────────────────────────────────────────

def _file():
    return _DOCTRINE_FILE


def save():
    """Persist live + graveyard (ATOMIC — final-audit fix B3)."""
    try:
        os.makedirs(_DOCTRINE_DIR, exist_ok=True)
        with _LOCK:
            # B3: tmp-then-replace — a truncate-and-write interrupted
            # mid-dump left partial JSON; the next failed load() then
            # armed the NEXT save() to overwrite all prior law with an
            # empty state (permanent history destruction). Atomic now.
            _tmp = _file() + ".tmp"
            with open(_tmp, "w", encoding="utf-8") as f:
                json.dump({"entries": _ENTRIES, "graveyard": _GRAVEYARD},
                          f, ensure_ascii=False, indent=1)
            os.replace(_tmp, _file())
        return True
    except Exception:
        return False


_ENTRY_KEYS = ("predicate", "context", "where", "score",
               "used", "worked", "failed", "ts")


def _valid_entry(e):
    """B6: schema-validated load — one malformed entry used to crash the
    round0 sort (KeyError swallowed by a broad try) and silently disable
    the WHOLE doctrine for the mission."""
    try:
        return (isinstance(e, dict)
                and all(k in e for k in _ENTRY_KEYS)
                and isinstance(e["score"], (int, float)))
    except Exception:
        return False


def load():
    """Load the doctrine from disk (live + graveyard)."""
    try:
        with open(_file(), encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return False
        with _LOCK:
            _ENTRIES[:] = [e for e in (d.get("entries") or [])
                           if _valid_entry(e)][:_MAX_ENTRIES]
            # B8: keep the NEWEST retires (tail) — the head-truncation
            # dropped fresh graveyard law and persisted the loss.
            _GRAVEYARD[:] = [e for e in (d.get("graveyard") or [])
                             if _valid_entry(e)][-_MAX_ENTRIES:]
        return True
    except Exception:
        # B3: quarantine the corrupt file — a later save() must never
        # clobber the evidence of what happened.
        try:
            os.replace(_file(), _file() + ".corrupt")
        except Exception:
            pass
        return False


def autopsy(target, skip_summary=None, extra_entries=None, transcript=None):
    """The mission-end ritual: skip taxonomy → doctrine (4.3), win
    patterns → doctrine (4.3b), the agent's own report entries (4.1),
    persist. Returns the minted entries for the autopsy report."""
    minted = []
    try:
        minted.extend(skip_taught(skip_summary))
    except Exception:
        pass
    try:
        minted.extend(mint_wins(transcript))
    except Exception:
        pass
    for e in (extra_entries or []):
        try:
            m = add_entry(e.get("predicate", ""), e.get("context", ""),
                          e.get("where", ""), e.get("expected", ""),
                          origin=e.get("origin", "autopsy"),
                          evidence=e.get("evidence"))
            if m:
                minted.append(m)
        except Exception:
            pass
    save()
    return minted


def reset():
    """Test hygiene: clear live + graveyard."""
    with _LOCK:
        _ENTRIES.clear()
        _GRAVEYARD.clear()
