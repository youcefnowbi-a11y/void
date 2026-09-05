"""VOIDFORGE :: OOB proof lane — the callback oracle (nuclei interactsh
architecture, self-hosted).

The problem it solves: blind vulnerability classes (SSRF, blind RCE, XXE,
blind SQLi exfil) produce ZERO differential in the HTTP response. A verdict
on those classes is a GUESS. This lane converts the guess into proof:

1. A probe asks for a unique interaction URL (`oob_url("ssrf")` →
   `<token>.oob.<domain>`). The token is deterministic per (host, channel).
2. Before the request fires, the detection predicate is FROZEN
   (`register(tag, predicate, context)`) — like nuclei's RequestEvent
   freezing Event+Operators before the wire.
3. When the target's runtime makes contact (DNS lookup, HTTP hit on our
   poll endpoint, or a manual `oob_poll` call in tests / relay setups), the
   stored predicate re-fires with the interaction injected
   (`process_interaction`), and the verdict carries
   `proof: oob_callback(protocol, ts)`.

Without the callback, a blind finding stays a HYPOTHESIS (Ω2 law #2).
The lane is fully functional OFFLINE: no domain configured → `oob_url`
returns an internal token that tools still embed (payloads remain
honest), `register` still defers, and `process_interaction` can be driven
by tests or a relay. With a domain + poll endpoint configured
(config/oob.yaml), the same code becomes a live oracle.

API:
    oob_url(tag, host)       -> "<tok>.oob.domain" or "<tok>.oob.internal"
    register(tag, host, predicate, context)  -> freeze pre-send
    process_interaction(token, protocol, details) -> re-fire predicate
    poll()                   -> drain callbacks (HTTP poll endpoint / relay)
    pending(tag, host)       -> has a frozen predicate not yet answered?
    receipt(tag, host)       -> the proof object once answered (or None)
"""
import json
import os
import re
import threading
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_HERE, os.pardir, "config", "oob.yaml")

_LOCK = threading.Lock()
# token -> {"predicate": fn, "context": dict, "ts": float, "tag": str,
#           "host": str}
_PENDING = {}
# (tag, host) -> proof object: {"proof": "oob_callback", "protocol": str,
#                               "ts": float, "details": str, "token": str}
_RECEIPTS = {}
_MAX_AGE = 3600.0          # frozen predicates expire after 1h
_MAX_ENTRIES = 2048         # LRU-ish bound (nuclei's CacheSize discipline)

_CFG = {"loaded": False, "domain": "", "poll_url": "", "poll_interval": 30.0}


def _cfg():
    if _CFG["loaded"]:
        return _CFG
    domain = ""
    poll_url = ""
    poll_interval = 30.0
    try:
        import yaml
        with open(_CFG_PATH, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        domain = str((d.get("oob") or {}).get("domain") or "")
        poll_url = str((d.get("oob") or {}).get("poll_url") or "")
        poll_interval = float((d.get("oob") or {}).get("poll_interval") or 30.0)
    except Exception:
        pass
    _CFG.update(loaded=True, domain=domain, poll_url=poll_url,
                poll_interval=poll_interval)
    return _CFG


def _token(tag, host):
    """Deterministic, collision-safe interaction token per (tag, host).

    Not a secret — it is a correlation ID. Determinism means a mission
    re-running a probe re-uses the same token and finds its own frozen
    predicate again instead of minting parallel orphans.
    """
    import hashlib
    raw = f"vf-oob-v1:{tag}:{(host or '').lower()}".encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def _evict_locked(now):
    """Bound memory: drop expired entries; when over cap drop oldest."""
    for k in [k for k, v in _PENDING.items() if now - v["ts"] > _MAX_AGE]:
        _PENDING.pop(k, None)
    if len(_PENDING) > _MAX_ENTRIES:
        for k in sorted(_PENDING, key=lambda k: _PENDING[k]["ts"])[:len(_PENDING) - _MAX_ENTRIES]:
            _PENDING.pop(k, None)
    if len(_RECEIPTS) > _MAX_ENTRIES:
        for k in sorted(_RECEIPTS, key=lambda k: _RECEIPTS[k]["ts"])[:len(_RECEIPTS) - _MAX_ENTRIES]:
            _RECEIPTS.pop(k, None)


def oob_url(tag, host=""):
    """The interaction URL to embed in payloads. Offline mode returns an
    internal token URL so payloads stay honest and testable; configured
    mode returns the live callback domain."""
    tok = _token(tag, host)
    dom = _cfg()["domain"]
    return f"{tok}.oob.{dom}" if dom else f"{tok}.oob.internal"


def register(tag, host, predicate, context=None):
    """Freeze a detection predicate BEFORE the request fires (nuclei's
    RequestEvent: Event+Operators handed to the OOB client pre-send).

    predicate: callable(interaction: dict) -> bool  — re-fired on callback
    with {"protocol", "raw", "remote", "ts", "token"}. Must be cheap and
    exception-safe; exceptions count as False, never crash the caller.
    """
    tok = _token(tag, host)
    now = time.time()
    with _LOCK:
        # insert FIRST, evict after: evict-before-insert leaves a steady
        # state of cap+1; post-insert eviction keeps the hard bound, and
        # the fresh entry (ts=now) is never the oldest so never reaped.
        _PENDING[tok] = {"predicate": predicate, "context": dict(context or {}),
                         "ts": now, "tag": tag, "host": host or ""}
        _evict_locked(now)
    return tok


def pending(tag, host):
    """Is a frozen predicate waiting for its callback?"""
    with _LOCK:
        return _token(tag, host) in _PENDING


def receipt(tag, host):
    """The proof object once the callback landed (or None)."""
    with _LOCK:
        return _RECEIPTS.get((tag, host or ""))


def process_interaction(token, protocol, details=""):
    """A callback landed (poll endpoint, relay, or test driver). Re-fire
    the frozen predicate (nuclei's processInteractionForRequest: inject
    interaction fields, re-execute the stored Operators).

    Returns the proof object if the predicate passes, else None. A token
    with no frozen predicate is ignored (late stragglers after eviction).
    """
    now = time.time()
    with _LOCK:
        frozen = _PENDING.get(token)
        _evict_locked(now)
        if not frozen:
            return None
        inter = {"protocol": str(protocol or "")[:40],
                 "raw": str(details or "")[:400],
                 "remote": "", "ts": now, "token": token}
        try:
            ok = bool(frozen["predicate"](inter))
        except Exception:
            ok = False
        if not ok:
            # nuclei semantics: a failed interaction does NOT consume the
            # pending correlation — the next interaction (e.g. the real
            # DNS exfil after a WAF's http health-check) re-fires.
            return None
        _PENDING.pop(token, None)
        proof = {"proof": "oob_callback", "protocol": inter["protocol"],
                 "ts": now, "details": inter["raw"][:200],
                 "token": token, "tag": frozen["tag"],
                 "host": frozen["host"]}
        _RECEIPTS[(frozen["tag"], frozen["host"])] = proof
        return proof


def poll():
    """Drain callbacks: HTTP poll endpoint configured → GET poll_url,
    expect a JSON array of {token|unique_id, protocol, raw|detail}. Any
    interaction found is pushed through process_interaction. Returns the
    number of proofs minted this poll (0 offline)."""
    url = _cfg()["poll_url"]
    if not url:
        return 0
    proofs = 0
    try:
        r = urllib.request.urlopen(url, timeout=15)
        data = json.loads(r.read(200_000).decode(errors="replace"))
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            tok = str(item.get("token") or item.get("unique_id") or "")
            if not tok:
                continue
            proto = item.get("protocol") or "dns"
            raw = str(item.get("raw") or item.get("detail") or item.get(
                "full-id") or "")
            if process_interaction(tok, proto, raw):
                proofs += 1
    except Exception:
        return proofs
    return proofs


def embed_hint(tag, host=""):
    """A payload hint line for tools: the URL to embed + the frozen tag, so
    the tool's JSON output carries the correlation for the agent to check
    `receipt()` later."""
    return {"url": oob_url(tag, host), "tag": tag,
            "proof_pending": pending(tag, host)}


# ── the tool-side hook: verdict upgrade ──────────────────────────────
def confirm_blind(tag, host, base_verdict):
    """Ω2 law: a BLIND verdict is CONFIRMED only with the callback. Call
    after poll() — upgrades {exploitable: true, blind: true} with
    proof, or downgrades to hypothesis with proof: None visible."""
    rec = receipt(tag, host)
    if rec:
        out = dict(base_verdict or {})
        out["proof"] = rec
        out["confirmed_blind"] = True
        return out
    out = dict(base_verdict or {})
    out["confirmed_blind"] = False
    out["proof"] = None
    return out
