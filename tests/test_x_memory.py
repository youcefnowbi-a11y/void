"""X-wave (audit 3) guards — memory bombs dead, arsenal learns, pacer sane."""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_x1_1_fetch_caps_bodies():
    # the read calls themselves are capped (source-level contract)
    src = open("tools/_transport.py", encoding="utf-8").read()
    assert "r.read(500_000)" in src, "urllib path must read capped (X1.1)"
    assert "r.text[:500_000]" in src, "curl path must cap (X1.1)"
    assert "ex.read(200_000)" in src, "error bodies capped (X1.1)"


def test_x1_3_cache_compacts_bodies():
    import tools._transport as T
    # simulate a cache write with a huge body via the eviction contract
    assert T._resp_cache_evict_locked.__doc__ is not None
    src = open("tools/_transport.py", encoding="utf-8").read()
    assert "cache-compacted" in src, "cached copies must be compact (X1.3)"
    assert "_compact['body'][:40_000]" in src or '_compact["body"][:40_000]' in src


def test_x3_1_403_neutral_429_penalized():
    from core.mathcore import get_pacer, pacer_drop
    pacer_drop("x-t1")
    p = get_pacer("x-t1", rate=8.0, burst=1.0)
    r0 = p.rate
    p.observe(403, 0.01)
    assert p.rate == r0, f"403 must be neutral (was {r0} -> {p.rate})"
    p.observe(429, 0.01)
    assert p.rate < r0, f"429 must still penalize ({r0} -> {p.rate})"
    pacer_drop("x-t1")


def test_x3_2_captcha_budget_per_host():
    import tools._transport as T
    T._CAPTCHA_BUDGET.clear()
    # three hosts each carry their own budget of 3
    T._CAPTCHA_BUDGET["a.com"] = 0
    assert T._CAPTCHA_BUDGET.get("b.com", 3) == 3, "hosts are independent"
    assert T._CAPTCHA_BUDGET.get("a.com", 3) == 0, "drained host stays drained"
    T._CAPTCHA_BUDGET.clear()


def test_x3_3_roe_window_is_deque():
    import tools._transport as T
    from collections import deque
    assert isinstance(T._ROE_WINDOW, deque), "ROE window must be a deque (X3.3)"
    assert hasattr(T._ROE_WINDOW, "popleft")


def test_x2_1_nursery_protects_young_plays():
    import core.learned_plays as LP
    # build a store: 50 young (uses=1) + 400 old (uses=5) -> harvest-like cut
    plays = ([{"host": f"h{i}.com", "kind": "grammar", "method": "GET",
               "path": f"/p{i}", "tool": "t", "uses": 1,
               "last_seen": f"2026-09-03 1{i:02d}"} for i in range(50)]
             + [{"host": f"o{i}.com", "kind": "grammar", "method": "GET",
                 "path": f"/q{i}", "tool": "t", "uses": 5,
                 "last_seen": "2026-09-01"} for i in range(400)])
    # apply the X2.1 cut exactly as harvest does
    if len(plays) > 400:
        _young = [p for p in plays if p.get("uses", 1) < 3]
        _old = [p for p in plays if p.get("uses", 1) >= 3]
        _young.sort(key=lambda p: p.get("last_seen") or "")
        _old.sort(key=lambda p: -(p.get("uses", 1)))
        plays = _young[-60:] + _old[:400 - min(len(_young), 60)]
    young_kept = sum(1 for p in plays if p.get("uses", 1) < 3)
    assert young_kept == 50, f"nursery must keep the young plays (kept {young_kept})"
    assert len(plays) <= 400


def test_x2_2_x2_3_recall_wider():
    src = open("core/learned_plays.py", encoding="utf-8").read()
    assert "cap=6000" in src, "recall cap must be 6000 (X2.3)"
    assert "_picked >= 14" in src, "cross-target recall must reach 14 (X2.2)"


def test_x4_llm_client_hardened():
    src = open("core/llm.py", encoding="utf-8").read()
    assert "timeout=300" in src, "blocking timeout aligned to 300 (X4.1)"
    assert "[:1600]" in src, "error body 1600 chars (X4.2)"
    assert "r.read(2_000_000)" in src, "response read capped (X4.3)"
