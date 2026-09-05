"""VOIDFORGE :: Ω1 world model (Phase 1 — the predictor).

The keystone organ. Law #1: SURPRISE IS THE SIGNAL — a predicted 200 is
worth zero; a prediction violated is worth a round. sqlmap taught the
calibration (learned false-signatures, not raw diffs), ffuf taught the
cascade (size→words→lines noise floors on semantically-loaded probes),
amass taught the TTL (the graph IS the cache, stale entries re-verify),
caldera taught the fail-closed slots (a step with an unresolved slot
DEFERS, never fires).

Five pieces:

1.1 PREDICTION CONTRACT — tools.execute() extracts `predict` from call
    args (the tool never sees it), freezes it pre-run, measures the
    delta post-run: {expected_status, expect_contains, sentinel}. The
    verdict (respected/violed/unmeasurable) + surprise score land in the
    model store; the agent's tool result carries the note.

1.2 CALIBRATED COMPARATOR — sqlmap's comparison.py, our shape: per
    endpoint, learn the FALSE-SIGNATURE (the ratio band of a junk
    response) instead of diffing against the original page; dynamicity
    spans (CSRF tokens, timestamps) marked between two clean fetches and
    REMOVED before any ratio; verdict by band: >0.98 same, <0.02 differ,
    else Δ vs the learned match-ratio.

1.3 CASCADE NOISE FLOORS — ffuf, our shape: per-host floors from
    semantically-loaded random probes (admin<rand>, .htaccess<rand>);
    whichever scalar (size/words/lines) survives K random inputs becomes
    the noise signature; a response matching the floor is noise, not a
    finding. WAF soft-block pages enter the floor (they carry the same
    words real fuzzing will use).

1.4 FAIL-CLOSED SLOTS — predict() with unresolved {slot} placeholders
    DEFERS (skip_ledger 'prereq_missing'), never fires half-rendered.

1.5 TTL'd ENTRIES — every entry (signature, floor, prediction verdict)
    carries a TTL; expired entries re-verify before use (amass: the
    graph is the cache).

Determinism (law #3): pure arithmetic + regex, no LLM calls inside the
model. The agent READS the surprise list; it never computes it.
"""
import difflib
import json
import re
import threading
import time
import urllib.parse

_LOCK = threading.Lock()
# kind -> {key -> {"value": any, "ts": float, "ttl": float}}
# kinds: "signature" (per-endpoint calibrated bands),
#        "floor" (per-host noise floors),
#        "markings" (per-endpoint dynamicity spans),
#        "prediction" (per-call verdicts, short TTL),
#        "delta" (per-endpoint last observed surprise)
_STORE = {}
_MAX_PER_KIND = 2048
_DEFAULT_TTL = 3600.0            # 1h: recon facts age, then re-verify
_PRED_TTL = 1800.0               # 30m: a prediction's verdict is fresh
_SURPRISE_CAP = 400              # bounded surprise memory per process

_MISS = object()                  # sentinel: key absent

_SLOT_RE = re.compile(r"\{[a-z][a-z0-9_]*\}", re.IGNORECASE)


# ── 1.5: TTL discipline (amass: the graph is the cache) ───────────────

def _get(kind, key):
    """TTL-aware read: expired entries are reaped (return None → caller
    re-verifies). Never mutates beyond the reap; thread-safe."""
    if not key:
        return None
    now = time.time()
    with _LOCK:
        e = (_STORE.get(kind) or {}).get(key)
        if not e:
            return None
        if now - e["ts"] > e["ttl"]:
            _STORE[kind].pop(key, None)
            return None
        return e["value"]


def _put(kind, key, value, ttl=None):
    if not key:
        return
    now = time.time()
    with _LOCK:
        d = _STORE.setdefault(kind, {})
        d[key] = {"value": value, "ts": now, "ttl": ttl or _DEFAULT_TTL}
        if len(d) > _MAX_PER_KIND:
            for k in sorted(d, key=lambda k: d[k]["ts"])[:len(d) - _MAX_PER_KIND]:
                d.pop(k, None)


def _entry_age(kind, key):
    with _LOCK:
        e = (_STORE.get(kind) or {}).get(key)
        return (time.time() - e["ts"]) if e else None


# ── 1.1: the prediction contract ──────────────────────────────────────

def parse_prediction(args):
    """Extract + validate the `predict` dict from call args. Returns
    (prediction, clean_args) — the tool receives clean_args (it never
    sees the prediction). Invalid shapes are dropped with None (the call
    fires unmeasured — a bad prediction must never block a strike)."""
    if not isinstance(args, dict) or "predict" not in args:
        return None, args
    args = dict(args)
    p = args.pop("predict", None)
    if not isinstance(p, dict):
        return None, args
    # normalize the contract
    pred = {}
    es = p.get("expected_status")
    if isinstance(es, int) and 100 <= es <= 599:
        pred["expected_status"] = es
    elif isinstance(es, (list, tuple)) and all(
            isinstance(x, int) and 100 <= x <= 599 for x in es):
        pred["expected_status"] = [int(x) for x in es]
    ec = p.get("expect_contains")
    if isinstance(ec, str) and ec.strip():
        pred["expect_contains"] = ec.strip()[:120]
    elif isinstance(ec, (list, tuple)) and all(
            isinstance(x, str) for x in ec):
        pred["expect_contains"] = [str(x)[:120] for x in ec]
    sentinel = p.get("sentinel")
    if isinstance(sentinel, str) and sentinel.strip():
        pred["sentinel"] = sentinel.strip()[:120]
    # fail-closed slots (1.4): a prediction carrying unresolved {slots}
    # DEFERS — measuring against a half-rendered expectation is noise.
    blob = " ".join(str(v) for v in pred.values())
    if _SLOT_RE.search(blob):
        return {"deferred": "unresolved-slot"}, args
    if not pred:
        return None, args
    return pred, args


def freeze(tool, args, pred):
    """Record the frozen prediction pre-run (context for the verdict)."""
    key = _pred_key(tool, args)
    _put("prediction", key, {"pred": pred, "tool": tool,
                             "url": _first_url(args)},
         ttl=_PRED_TTL)
    return key


def measure(tool, args, pred, out):
    """Post-run: measure the delta between the frozen prediction and the
    real output. Returns the verdict dict (deterministic, LLM-free):

    {"verdict": "respected"|"violated"|"partial"|"unmeasured",
     "surprise": 0.0..1.0, "expected": ..., "observed": ...,
     "notes": [specific contradictions]}

    surprise 0.0 = the world behaved exactly as modeled (no information),
    1.0 = the model was maximally wrong (maximum information).
    """
    notes = []
    if not pred or not isinstance(pred, dict):
        return {"verdict": "unmeasured", "surprise": 0.0, "notes": []}
    s = str(out or "")
    # status: find status-like ints in the tool JSON output
    # final-audit fix B4: scan the WHOLE string — the 60k window was a
    # keyhole (the pre-cap output arrives here raw): a match past 60k
    # was invisible → "no status" → fake violations on big outputs.
    # findall is linear and cheap; no window needed.
    sts = [int(m) for m in re.findall(
        r'"status(?:_code)?"\s*:\s*(-?\d+)', s)]
    sts = [x for x in sts if 100 <= x < 600]
    exp_st = pred.get("expected_status")
    st_ok = None
    if exp_st is not None:
        if not sts:
            st_ok = None      # no observable status → unmeasured on axis
            notes.append("status axis unmeasurable (no status in output)")
        else:
            want = exp_st if isinstance(exp_st, list) else [exp_st]
            # multi-status outputs (ssrf_probe, dir_brute): the prediction
            # is satisfied if ANY observed status matches the expectation
            # — an expected-200 probe whose payload 403s mid-list is
            # still fundamentally a responding surface. ALL-miss = the
            # real violation. The CHECK scans every status found (a
            # 30-status output must not fake a violation because the
            # match sits at index 12); only the NOTE is display-bounded.
            st_ok = any(x in want for x in sts)
            if not st_ok:
                notes.append(f"expected status {want}, observed {sts[:8]}")
    # expect_contains
    ec = pred.get("expect_contains")
    ec_ok = None
    if ec is not None:
        wants = [ec] if isinstance(ec, str) else list(ec)
        hits = {w: (w in s) for w in wants}
        ec_ok = all(hits.values())
        for w, h in hits.items():
            if not h:
                notes.append(f"expected '{w[:40]}' in output, absent")
    # sentinel (must-fire marker)
    sent = pred.get("sentinel")
    sent_ok = None
    if sent is not None:
        sent_ok = sent in s
        if not sent_ok:
            notes.append(f"sentinel '{sent[:40]}' never appeared")
    # compose: measured axes only; all-respected = 0 surprise,
    # any violation = surprise proportional to axes violated
    axes = [x for x in (st_ok, ec_ok, sent_ok) if x is not None]
    if not axes:
        v = "unmeasured"
        surprise = 0.0
    elif all(axes):
        v = "respected"
        surprise = 0.0
    elif not any(axes):
        v = "violated"
        surprise = 1.0
    else:
        v = "partial"
        surprise = round(axes.count(False) / len(axes), 2)
    verdict = {"verdict": v, "surprise": surprise,
               "expected": {"status": exp_st, "contains": ec, "sentinel": sent},
               "observed": {"statuses": sts[:3]},
               "notes": notes[:6]}
    # archive the surprise delta per-endpoint (the agent's round-0 map)
    key = _endpoint_of(args) or "unknown"
    with _LOCK:
        deltas = _STORE.setdefault("delta", {})
        # bounded ring of surprises per endpoint
        ring = deltas.get(key)
        if not isinstance(ring, list):
            ring = []
            deltas[key] = ring
        ring.append({"ts": time.time(), "tool": tool,
                     "verdict": v, "surprise": surprise,
                     "notes": notes[:2]})
        if len(ring) > _SURPRISE_CAP // 16:
            ring.pop(0)
        if len(deltas) > 256:
            for k in sorted(deltas, key=lambda k: (deltas[k] or [{"ts": 0}])[-1].get("ts", 0))[:len(deltas) - 256]:
                deltas.pop(k, None)
    return verdict


def prediction_note(verdict):
    """The tool-result note the agent reads (deterministic phrasing)."""
    if not verdict or verdict.get("verdict") == "unmeasured":
        return ""
    v = verdict["verdict"]
    if v == "respected":
        return ("\n\n[Ω1/PREDICT ✓] Le monde a obéi au modèle "
                "(0 surprise — cette voie n'a plus d'information à donner).")
    if v == "partial":
        return (f"\n\n[Ω1/PREDICT ◐] Prédiction PARTIELLEMENT violée "
                f"(surprise {verdict['surprise']:.2f}): "
                + "; ".join(verdict.get("notes") or []) + ". "
                "L'écart est le signal — investigue CE delta.")
    return ("\n\n[Ω1/PREDICT ✗ VIOLÉ] Le modèle mental était FAUX ici "
            f"(surprise {verdict['surprise']:.2f}): "
            + "; ".join(verdict.get("notes") or [])
            + ". C'est exactement là que vivent les exploits — creuse.")


def surprise_digest(limit=12):
    """Round-0/round-summary digest: the endpoints where the model was
    wrong, freshest first. The mission's true to-do list."""
    with _LOCK:
        out = []
        for ep, ring in sorted((_STORE.get("delta") or {}).items(),
                               key=lambda kv: -(kv[1][-1]["ts"] if kv[1] else 0)):
            viol = [r for r in ring if r["verdict"] in ("violated", "partial")]
            if viol:
                out.append({"endpoint": ep, "violations": len(viol),
                            "last": viol[-1]["notes"],
                            "last_tool": viol[-1]["tool"]})
        return out[:limit]


# ── 1.2: calibrated comparator (sqlmap comparison.py, our shape) ─────

_DIFF_TOL = 0.05        # sqlmap DIFF_TOLERANCE
_LO = 0.02              # sqlmap LOWER_RATIO_BOUND
_HI = 0.98              # sqlmap UPPER_RATIO_BOUND
_MARK_MIN = 20          # sqlmap DYNAMICITY_BOUNDARY_LENGTH * 2 (block cut)


def _quick_ratio(a, b):
    if not a or not b:
        return 0.0 if (a or b) else 1.0
    return difflib.SequenceMatcher(None, a, b).quick_ratio()


def learn_markings(endpoint, body_a, body_b):
    """Two CLEAN fetches of the same page → mark the dynamic spans (CSRF
    tokens, timestamps, nonces). Stored as (prefix, suffix) anchors;
    remove_markings() splices matching spans out of any later body."""
    a, b = str(body_a or ""), str(body_b or "")
    if not a or not b:
        return []
    sm = difflib.SequenceMatcher(None, a, b)
    marks = []
    for blk in sm.get_matching_blocks():
        if blk.size <= _MARK_MIN:
            continue
        # anchor pair: the stable text AROUND the change zone
        pre = a[max(0, blk.a - 24):blk.a]
        suf = a[blk.a + blk.size:blk.a + blk.size + 24]
        if pre or suf:
            marks.append((pre, suf))
    if marks:
        _put("markings", endpoint, marks[:64])
    return marks[:64]


def remove_markings(endpoint, body):
    """Splice learned dynamic spans out of a body (pre-comparison)."""
    marks = _get("markings", endpoint)
    if not marks:
        return str(body or "")
    s = str(body or "")
    for pre, suf in marks:
        if not pre or not suf:
            continue
        i = s.find(pre)
        if i < 0:
            continue
        j = s.find(suf, i + len(pre))
        if j > i:
            s = s[:i + len(pre)] + s[j:]
    return s


def calibrated_verdict(endpoint, page, template, learn=True):
    """sqlmap's ratio oracle: compare against the LEARNED false-signature
    band, not the original page. First call with a mid-band ratio LEARNS
    the match-ratio (the false-response signature); later calls ask
    whether the delta exceeds tolerance.

    Returns "same" | "differs" | None (unmeasurable).
    """
    page = remove_markings(endpoint, page)
    template = remove_markings(endpoint, template)
    if page == template:
        return "same"
    if not page or not template:
        return None
    if max(len(page), len(template)) > 10_000_000:
        # sqlmap MAX_DIFFLIB_SEQUENCE_LENGTH: length-ratio fallback
        r = min(len(page), len(template)) / max(len(page), len(template))
    else:
        r = _quick_ratio(page, template)
    if r > _HI:
        return "same"
    if r < _LO:
        return "differs"
    # mid-band: the learned match-ratio decides (sqlmap kb.matchRatio)
    mr = _get("signature", endpoint)
    if mr is None:
        if learn:
            _put("signature", endpoint, r)
        return "differs" if r < 0.5 else "same"
    # final-audit fix B7: abs() both ways — a page LESS similar than the
    # learned junk band is ALSO a difference (the one-sided test called
    # it "same", blinding the sqli differential from one whole side).
    return "differs" if abs(r - mr) > _DIFF_TOL else "same"


# ── 1.3: cascade noise floors (ffuf, our shape) ───────────────────────

def noise_floor(host, samples, min_samples=3):
    """From K semantically-loaded probe responses (each a dict with
    size/words/lines or a body str), derive the per-host noise floor:
    the scalars that stay IDENTICAL across all samples are the floor
    (a wildcard/soft-block signature). Returns the floor dict or None."""
    if not isinstance(samples, list) or len(samples) < min_samples:
        return None
    feats = []
    for s in samples:
        if isinstance(s, dict):
            feats.append({
                "size": s.get("size"),
                "words": s.get("words"),
                "lines": s.get("lines"),
                "status": s.get("status"),
            })
        elif isinstance(s, str):
            body = s
            feats.append({
                "size": len(body),
                "words": len(body.split()),
                "lines": body.count("\n") + 1,
                "status": None,
            })
        else:
            return None
    floor = {}
    for k in ("size", "words", "lines", "status"):
        vals = {f[k] for f in feats if f[k] is not None}
        if len(vals) == 1 and None not in vals:
            floor[k] = vals.pop()
    if not floor:
        return None
    _put("floor", host, floor)
    return floor


def is_noise(host, size=None, words=None, lines=None, status=None):
    """Does a candidate response match the learned floor? (ffuf: the
    calibrated filter — matching ALL floor scalars = noise, not a find.)"""
    floor = _get("floor", host)
    if not floor:
        return False
    cand = {"size": size, "words": words, "lines": lines, "status": status}
    checks = 0
    for k, v in floor.items():
        cv = cand.get(k)
        if cv is None:
            continue
        if cv != v:
            return False
        checks += 1
    return checks > 0 and checks >= len(floor) - 1


# ── helpers ───────────────────────────────────────────────────────────

def _pred_key(tool, args):
    """Stable, crash-proof: json-serialize sorted args (nested dicts OK)."""
    try:
        blob = json.dumps(args or {}, sort_keys=True, default=str)[:400]
    except Exception:
        blob = str(args)[:400]
    return f"{tool}:{hash(blob) & 0xFFFFFFFFFFFFFF:x}"


def _first_url(args):
    if isinstance(args, dict):
        for v in args.values():
            # final-audit fix B10: case-insensitive scheme — "HTTP://"
            # used to key "unknown" and merge its surprises into one ring
            if isinstance(v, str) and v[:4].lower() == "http":
                return v[:200]
    return None


def _endpoint_of(args):
    u = _first_url(args)
    if not u:
        return None
    try:
        p = urllib.parse.urlsplit(u)
        return (p.netloc or "unknown").lower() + (p.path or "")[:80]
    except Exception:
        return None


def reset():
    """Test hygiene / process reset."""
    with _LOCK:
        _STORE.clear()
