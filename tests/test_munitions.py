"""VOIDFORGE :: V1 munitions tests — payload_library + trajectory archive."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools as reg
reg.discover()


def test_payload_library_list():
    out = reg.execute("payload_library", {"op": "list"})
    assert "MUNITIONS DEPOT" in out
    assert "sqli" in out and "xss" in out


def test_payload_library_get_sqli():
    out = reg.execute("payload_library", {"op": "get", "vclass": "sqli", "limit": 60})
    assert "sqli" in out
    lines = [l for l in out.splitlines() if l and not l.startswith("[")]
    assert len(lines) >= 20  # real payloads served from disk
    assert "' OR" in out or "UNION" in out or "SLEEP" in out


def test_payload_library_unknown_class():
    out = reg.execute("payload_library", {"op": "get", "vclass": "definitely_not_real"})
    assert "UNKNOWN_CLASS" in out


def test_payload_library_dirs_uses_wordlists():
    out = reg.execute("payload_library", {"op": "get", "vclass": "dirs", "limit": 15})
    assert len(out) > 200  # SecLists content reached through the tool


def test_trajectory_record_and_insight():
    from core.trajectory import record, insight, _PATH
    if os.path.exists(_PATH):
        os.remove(_PATH)
    # mission 1: recon ok -> strike ok
    record(1, "test.local", "web_fingerprint", True, 1.2, round_num=1)
    record(1, "test.local", "sqli_probe_param", True, 0.9, round_num=2)
    # mission 2: same chain, strike fails
    record(2, "test.local", "web_fingerprint", True, 1.0, round_num=1)
    record(2, "test.local", "sqli_probe_param", False, 0.4, round_num=2)
    block = json.loads(insight(min_support=1))
    assert block["corpus_events"] >= 4
    tools = {t["tool"] for t in block["tool_reliability"]}
    assert "web_fingerprint" in tools and "sqli_probe_param" in tools
    chains = {(c["chain"], c["seen"]) for c in block["proven_chains"]}
    assert ("web_fingerprint -> sqli_probe_param", 2) in chains


def test_trajectory_never_raises_on_garbage():
    from core.trajectory import record
    record(None, None, None, None, None, round_num=None)  # must not raise


def test_fuzz_accepts_wordlist_param():
    t = reg.get("fuzz_attack_surface")
    assert "wordlist" in (t["params"].get("properties") or {})
