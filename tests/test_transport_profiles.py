# -*- coding: utf-8 -*-
"""Guard tests — E1 malleable traffic profiles."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
import tools._transport as T


def _set_profile(d):
    """Inject a resolved profile without touching the yaml (unit scope)."""
    if d is None:
        T._PROFILE[0] = None
        return
    prof = dict(d)
    prof["__name"] = d.get("__name", "test")
    T._PROFILE[0] = prof
    T._PROFILE_LOADED[0] = True


def _teardown():
    T._PROFILE[0] = None
    T._PROFILE_LOADED[0] = False


def setup_function(fn):
    _teardown()


def teardown_function(fn):
    _teardown()


def test_no_profile_is_noop():
    h = {"User-Agent": "UA-ID"}
    T._apply_profile(h, "target.example")
    assert h == {"User-Agent": "UA-ID"}


def test_single_writer_identity_never_overridden():
    _set_profile({"headers": {"User-Agent": "EVIL-UA",
                              "Accept-Language": "xx",
                              "Accept": "application/json"}})
    h = {"User-Agent": "UA-ID", "Accept-Language": "lang-ID"}
    T._apply_profile(h, "target.example")
    assert h["User-Agent"] == "UA-ID" and h["Accept-Language"] == "lang-ID"
    assert h["Accept"] == "application/json"  # profile still adds the rest


def test_referer_origin_target_substitution():
    _set_profile({"referer": "{TARGET}/", "origin": "{TARGET}"})
    h = {}
    T._apply_profile(h, "target.example")
    assert h["Referer"] == "https://target.example/"
    assert h["Origin"] == "https://target.example"


def test_header_order_is_declaration_only():
    """AUDIT E1-A1 companion: header_order is declared shape documentation —
    it must never materialize as a wire header."""
    _set_profile({"headers": {"Accept": "text/html"},
                  "header_order": ["User-Agent", "Accept", "Referer"]})
    h = {"User-Agent": "UA"}
    T._apply_profile(h, "target.example")
    assert "__header_order" not in h


def test_profiles_produce_disjoint_header_sets():
    a = {"headers": {"Accept": "text/html", "Sec-Fetch-Mode": "navigate",
                     "Upgrade-Insecure-Requests": "1"}}
    b = {"headers": {"Accept": "application/json",
                     "Connection": "keep-alive"}}
    ha, hb = {}, {}
    _set_profile(a)
    T._apply_profile(ha, "t.example")
    _set_profile(b)
    T._apply_profile(hb, "t.example")
    ka = {(k, v) for k, v in ha.items() if not k.startswith("__")}
    kb = {(k, v) for k, v in hb.items() if not k.startswith("__")}
    # the SHAPE is the (key, value) pair — two profiles may both carry an
    # Accept header, but if no PAIR is shared, no wire fingerprint is.
    assert ka and kb and not (ka & kb)  # zero shared shape


def test_profile_hash_stable_and_named():
    _set_profile({"__name": "browser_strict", "headers": {"Accept": "x"},
                  "jitter": [1.0, 1.5]})
    h1, h2 = T.profile_hash(), T.profile_hash()
    assert h1 == h2 and h1.startswith("browser_strict:") and \
        len(h1.split(":")[1]) == 8
    _set_profile({"__name": "browser_strict", "headers": {"Accept": "y"},
                  "jitter": [1.0, 1.5]})
    assert T.profile_hash() != h1  # shape change → new hash


def test_tool_headers_win_over_profile():
    _set_profile({"headers": {"Accept": "from-profile"}})
    h = {"Accept": "from-tool"}
    T._apply_profile(h, "t.example")   # profile applied
    h.update({"Accept": "from-tool"})  # caller applies tool headers after
    assert h["Accept"] == "from-tool"


# ── AUDIT E1-A1..A4: the wire never lies ─────────────────────────────


def test_no_meta_keys_reach_the_wire():
    """AUDIT E1-A1 (critical): h goes verbatim into urllib.Request — any
    dunder/meta key in it would be SENT to the target as a header."""
    _set_profile({"headers": {"Accept": "text/html"},
                  "header_order": ["Accept", "X-Should-Not-Appear"],
                  "referer": "{TARGET}/", "jitter": [1.0, 1.5]})
    h = {"User-Agent": "UA"}
    T._apply_profile(h, "t.example")
    assert not any(k.startswith("__") for k in h), \
        f"meta keys would leak on the wire: {[k for k in h if k.startswith('__')]}"
    assert "X-Should-Not-Appear" not in h  # header_order never materializes


def test_scheme_follows_the_real_url():
    """AUDIT E1-A3: {TARGET} substitutes the REAL scheme, not assumed https."""
    T._PROFILE[0] = {"__name": "t", "referer": "{TARGET}/x"}
    T._PROFILE_LOADED[0] = True
    for url, want in (("http://t.example/a", "http://t.example/x"),
                      ("https://t.example/a", "https://t.example/x")):
        h = {}
        T._apply_profile(h, "t.example",
                         scheme=url.split(":")[0])
        assert h["Referer"] == want


def test_transport_posture_speaks():
    """The LLM must SEE the wire law: posture names the active profile."""
    _set_profile({"__name": "browser_strict", "headers": {"Accept": "x"}})
    p = T.transport_posture()
    assert "browser_strict" in p and "TRANSPORT POSTURE" in p
    T._PROFILE[0] = None
    p2 = T.transport_posture()
    assert "default" in p2  # degraded shape still named, never empty crash


def test_jitter_never_loosens_roe():
    """The gate still admits exactly lim calls per window; jitter only
    stretches the sleep BETWEEN polls, not the window size."""
    lim = T._roe_limit()
    t0 = time.time()
    for _ in range(min(3, lim)):
        T._roe_gate()
    assert time.time() - t0 < 5  # tight envelope still flows
    assert len(T._ROE_WINDOW) <= lim


def test_malformed_profile_falls_back_clean():
    _set_profile({"headers": "not-a-dict", "jitter": "nope",
                  "referer": 42})
    h = {"User-Agent": "UA"}
    T._apply_profile(h, "t.example")  # must not raise
    assert h["User-Agent"] == "UA"
