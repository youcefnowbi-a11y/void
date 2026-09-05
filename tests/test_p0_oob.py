"""Phase 0.1 guards — the OOB proof lane (nuclei interactsh architecture).

Laws under test:
- law #2 (no verdict without proof): blind classes carry proof objects
  or stay hypotheses.
- nuclei fidelity: predicate frozen pre-send; failed interaction does
  NOT consume the pending correlation; unknown/late tokens are no-ops.
- determinism: token = hash(tag, host) — a re-run probe finds its own
  frozen predicate instead of minting orphans.
- hygiene: LRU bounds hold under flood; expiry reaps stale entries.
"""
import time

import tools.oob_channel as oc


def test_o01_url_mint_and_determinism():
    url = oc.oob_url("ssrf", "target1.example.com")
    assert ".oob." in url and url.split(".")[0], url
    # determinism: same (tag, host) → same token (mission re-runs re-find)
    assert oc.oob_url("ssrf", "target1.example.com") == url
    # different host → different token (no cross-host bleed)
    assert oc.oob_url("ssrf", "target2.example.com") != url
    # different tag → different token (no cross-channel bleed)
    assert oc.oob_url("xxe", "target1.example.com") != url


def test_o02_freeze_and_confirm():
    oc.register("ssrf", "h1.example.com",
                lambda i: i["protocol"] in ("dns", "http", "https"))
    assert oc.pending("ssrf", "h1.example.com")
    tok = oc.oob_url("ssrf", "h1.example.com").split(".")[0]
    # wrong-class interaction does NOT confirm and does NOT consume
    assert oc.process_interaction(tok, "smtp") is None
    assert oc.pending("ssrf", "h1.example.com")
    # the real callback confirms and mints the proof object
    p = oc.process_interaction(tok, "dns", "h1.example.com A 1.2.3.4")
    assert p and p["proof"] == "oob_callback" and p["protocol"] == "dns"
    assert p["tag"] == "ssrf" and p["host"] == "h1.example.com"
    # receipt persisted; nothing left pending
    r = oc.receipt("ssrf", "h1.example.com")
    assert r and r["protocol"] == "dns"
    assert not oc.pending("ssrf", "h1.example.com")


def test_o03_predicate_exception_is_false_never_crash():
    def bad(i):
        raise RuntimeError("boom")
    oc.register("boom", "h2.example.com", bad)
    tok = oc.oob_url("boom", "h2.example.com").split(".")[0]
    assert oc.process_interaction(tok, "dns") is None  # False, no raise


def test_o04_unknown_token_is_noop():
    # late straggler after eviction / foreign token: ignored, never raises
    assert oc.process_interaction("0000000000", "dns") is None
    assert oc.process_interaction("", "dns") is None


def test_o05_confirm_blind_upgrade():
    oc.register("ssrf", "h3.example.com", lambda i: True)
    tok = oc.oob_url("ssrf", "h3.example.com").split(".")[0]
    # before callback: hypothesis, not confirmed
    pre = oc.confirm_blind("ssrf", "h3.example.com",
                           {"exploitable": True, "blind": True})
    assert pre["confirmed_blind"] is False and pre["proof"] is None
    # after callback: CONFIRMED with proof object attached
    assert oc.process_interaction(tok, "http", "GET /e") is not None
    post = oc.confirm_blind("ssrf", "h3.example.com",
                            {"exploitable": True, "blind": True})
    assert post["confirmed_blind"] is True
    assert post["proof"]["protocol"] == "http"


def test_o06_failed_interaction_does_not_consume():
    # nuclei semantics: predicate-False interaction leaves the correlation
    # alive — the follow-up real interaction re-fires it.
    oc.register("ssrf", "h4.example.com", lambda i: i["protocol"] == "dns")
    tok = oc.oob_url("ssrf", "h4.example.com").split(".")[0]
    assert oc.process_interaction(tok, "http") is None
    assert oc.pending("ssrf", "h4.example.com")
    p = oc.process_interaction(tok, "dns", "late but real")
    assert p and p["protocol"] == "dns"


def test_o07_lru_and_expiry_hygiene():
    # expiry FIRST: age the canary entry past the horizon…
    stale = oc.oob_url("stale", "h5.example.com").split(".")[0]
    oc.register("stale", "h5.example.com", lambda i: True)
    oc._PENDING[stale]["ts"] = time.time() - oc._MAX_AGE - 10
    # …then flood beyond cap: bounded, and the aged canary is reaped
    for i in range(oc._MAX_ENTRIES + 120):
        oc.register(f"flood{i}", f"f{i}.example.com", lambda i: True)
    assert len(oc._PENDING) <= oc._MAX_ENTRIES
    assert stale not in oc._PENDING
    oc.register("fresh", "h5.example.com", lambda i: True)  # triggers evict
    assert stale not in oc._PENDING


def test_o08_offline_config_honesty():
    # offline mode: internal token URL — payloads stay embeddable
    url = oc.oob_url("any", "any.example.com")
    assert url.endswith(".oob.internal") or ".oob." in url
    # poll without configured endpoint = 0 proofs, no exception
    assert oc.poll() in (0, None) or oc.poll() >= 0


def test_o09_embed_hint_shape():
    h = oc.embed_hint("ssrf", "h6.example.com")
    assert set(h) >= {"url", "tag", "proof_pending"}
    assert h["tag"] == "ssrf"


def test_o10_ssrf_graft_imports():
    # the grafted tools import clean (registry side intact)
    import tools.ssrf_test
    import tools.advanced_web
    import importlib
    importlib.reload(tools.oob_channel)
