"""VOIDFORGE :: transport wave2 tests — UA consistency (P3), proxy pool
(P1) + rotate-on-block (P2). Pure logic, no network."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import _transport as t


def test_ua_stable_per_host():
    a1 = t._ua_for("shop.example.com")
    a2 = t._ua_for("shop.example.com")
    assert a1 == a2 and a1 in t._UA_POOL          # deterministic, from the pool
    assert t._ua_for("other.example.com") in t._UA_POOL
    assert t._ua() == t._ua()                      # process-level frozen


def test_ua_pool_exists():
    assert len(t._UA_POOL) >= 3


def test_pool_empty_by_default():
    t._POOL.clear()
    t._POOL_LOADED[0] = True  # skip config load — simulate empty config
    assert t._pool_next() is None


def test_pool_rotation_and_health(tmp_path):
    t._POOL.clear()
    t._POOL_LOADED[0] = True
    t._POOL.extend([
        {"url": "http://p1:1", "fail_count": 0, "cooldown_until": 0.0},
        {"url": "http://p2:1", "fail_count": 0, "cooldown_until": 0.0},
    ])
    # least-failing first, exclusion honored
    first = t._pool_next()
    assert first in ("http://p1:1", "http://p2:1")
    nxt = t._pool_next(exclude={first})
    assert nxt != first
    # 3 fails -> cooldown -> excluded
    for _ in range(3):
        t._pool_mark(first, False)
    assert t._pool_next(exclude={nxt}) is None    # first is cooling, nxt excluded
    # success resets health
    t._POOL[1]["fail_count"] = 2
    t._pool_mark("http://p2:1", True)
    assert t._POOL[1]["fail_count"] == 0


def test_looks_blocked():
    assert t._looks_blocked("Access denied — Attention Required | Cloudflare")
    assert t._looks_blocked("Just a moment...")
    assert not t._looks_blocked("<html><body>Welcome to the shop</body></html>")
    assert not t._looks_blocked("")


def test_fetch_signature_backcompat():
    import inspect
    sig = inspect.signature(t.fetch)
    assert "url" in sig.parameters and "_proxy_tried" in sig.parameters
    # old callers (positional url/method/headers/body/timeout/use_cache/retries)
    # remain valid
    names = list(sig.parameters)
    assert names[:7] == ["url", "method", "headers", "body", "timeout",
                         "use_cache", "retries"]
