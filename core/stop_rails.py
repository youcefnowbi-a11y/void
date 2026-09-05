"""VOIDFORGE :: mission stop rails (Phase 0.2 — ffuf discipline).

ffuf's lesson (audit): a scanner that grinds a closed door is spending
budget on noise AND advertising itself. ffuf aborts when >95% of 50+
responses are 403 and when >20% are 429. A mission agent doesn't abort —
it PIVOTS. These rails convert those ratios into a system event the
agent's next round must obey:

- wall_403 : ≥95% of the last ≥50 observed statuses are 403 → the host is
  WAF-walled; grinding more probes burns rounds and flags us.
- rate_429 : ≥20% of the last ≥50 observed statuses are 429 → the pacer
  is losing; back off / rotate identity / slow down.

Design rules (inherited):
- WB2 lesson: tools that EXPECT 401/403 as data (auth probes, idor,
  endpoint oracles, WAF detection itself) are EXEMPT — their blocked
  responses are findings, not walls.
- Deterministic (law #3): pure arithmetic over a bounded window; the
  LLM is never asked to count.
- Non-destructive reads: verdict() never mutates; delivery bookkeeping
  is explicit (deliver()) so the same rail doesn't nag every round.
- Rearm: a delivered rail re-arms when its share falls below half the
  threshold (the wall got solved or the target changed shape).
"""
import re
import threading
import collections

# tools whose 40x responses are DATA, not walls (WB2 exemption list,
# kept in sync with agent.py's wall-breaker noise tools)
_NOISE_TOOLS = re.compile(
    r"(?i)(auth_state|endpoint_oracle|idor|param_brute|"
    r"api_sweep|fuzz_|crash_triage|secret_scan|js_mine|"
    r"har_|wayback|cisa_kev|waf_detect|nvd_search)")

# both spellings our fleet emits (transport "status", nuclei-style
# "status_code") — wave-2-B fix: batch_execute embeds inner results as
# JSON-escaped strings (\"status\": 403), so the escaped form is
# first-class now. Rails must see through the envelope.
_STATUS_RE = re.compile(r'\\?"status(?:_code)?\\?"\s*:\s*(-?\d+)')

_LOCK = threading.Lock()
_WINDOW = collections.deque(maxlen=400)     # bounded response memory
_DELIVERED = {}                             # rail -> share when delivered
_MIN_N = 50                                 # ffuf: rails arm at 50+ responses
_WALL_SHARE = 0.95                           # ffuf: >95% 403 = wall
_RATE_SHARE = 0.20                           # ffuf: >20% 429 = rate wall


def observe(name, out):
    """Feed the window: every status code found in a tool's JSON output
    is one observed response (per-payload statuses each count — ffuf
    semantics). Noise tools are exempt (their 40x are probe data).
    Transport-dead statuses (-1, 0) are the circuit breaker's domain,
    not ours. Never raises."""
    try:
        if not out or _NOISE_TOOLS.search(name or ""):
            return
        found = _STATUS_RE.findall(str(out)[:200_000])
        if not found:
            return
        entries = [int(s) for s in found if 100 <= int(s) < 600]
        if not entries:
            return
        with _LOCK:
            _WINDOW.extend((name, s) for s in entries)
    except Exception:
        pass


def _shares_locked():
    n = len(_WINDOW)
    if n < _MIN_N:
        return n, 0.0, 0.0
    c403 = sum(1 for _, s in _WINDOW if s == 403)
    c429 = sum(1 for _, s in _WINDOW if s == 429)
    return n, c403 / n, c429 / n


def pending():
    """Is a rail armed (threshold met) and not yet delivered?
    Returns None or {"rail": "wall_403"|"rate_429", "share": float,
    "n": int}. Non-destructive. NOTE: share is RAW (full precision) —
    deliver() must receive this exact value; rounding here would break
    the delivered-at-share comparison (0.983 delivered vs 0.98333 live
    re-arms forever). Display rounds, bookkeeping doesn't."""
    with _LOCK:
        n, s403, s429 = _shares_locked()
        out = None
        if s403 >= _WALL_SHARE and _DELIVERED.get("wall_403", 0.0) < s403:
            out = {"rail": "wall_403", "share": s403, "n": n}
        elif s429 >= _RATE_SHARE and _DELIVERED.get("rate_429", 0.0) < s429:
            out = {"rail": "rate_429", "share": s429, "n": n}
        # rearm check: delivered rail whose share collapsed → forget it
        for rail, thr in (("wall_403", _WALL_SHARE),
                          ("rate_429", _RATE_SHARE)):
            share = s403 if rail == "wall_403" else s429
            if rail in _DELIVERED and share < thr / 2:
                _DELIVERED.pop(rail, None)
        return out


def deliver(rail, share):
    """Mark a rail as delivered at this share; it re-arms only if the
    share climbs higher (new, worse wall) or collapses (rearm path)."""
    with _LOCK:
        _DELIVERED[rail] = share


def reset():
    """New mission → fresh window, no delivery memory."""
    with _LOCK:
        _WINDOW.clear()
        _DELIVERED.clear()


def stats():
    """Introspection for the report/tests: window size + shares."""
    with _LOCK:
        n, s403, s429 = _shares_locked()
        return {"n": n, "share_403": round(s403, 3), "share_429": round(s429, 3),
                "min_n": _MIN_N, "delivered": dict(_DELIVERED)}
