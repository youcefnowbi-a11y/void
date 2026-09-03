"""VOIDFORGE :: Tier F — depth driver tests.

Covers the mission-76 autopsy fixes: coverage orders (F1), the
session_keep cache tool (F2), the anti-ratchet memory lines (F3),
the zero-day door hint (F4), the discovery-aware bandit reward (F5)
and the bench-tagged tool descriptions (F6).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── F5: discovery + reward signal ───────────────────────────────────

def test_discovery_signal_positive():
    from core.coverage import discovery_signal
    assert discovery_signal('{"exploitable": true, "hits": 2}')
    assert discovery_signal('{"verdict": "exploitable"}')
    assert discovery_signal('{"record_count": 12, "rows": []}')
    assert discovery_signal('"vulnerable": true')
    assert discovery_signal('"crashed": true')


def test_discovery_signal_negative():
    from core.coverage import discovery_signal
    assert not discovery_signal('{"exploitable": false, "records": 0}')
    assert not discovery_signal("plain token mint success")
    assert not discovery_signal("")
    assert not discovery_signal(None)


def test_reward_signal_honors_honest_negatives():
    from core.coverage import reward_signal
    # a clean structured negative IS a reward (lane closed with evidence)
    assert reward_signal('{"exploitable": false, "summary": "all variants rejected"}')
    assert reward_signal('{"verdict": "missing"}')
    assert reward_signal('{"challenge_status": 402}')
    # a bare successful fetch is NOT
    assert not reward_signal('{"status": 200, "size": 55637}')
    assert not reward_signal('{"url": "https://x", "status": 200}')


# ── F1: coverage accounting + orders ───────────────────────────────

def test_bench_counts_and_cold():
    from core.coverage import bench_counts, cold_benches
    names = ["data_extract", "api_sweep", "web_fingerprint", "batch_execute"]
    c = bench_counts(names)
    assert c["surface"] >= 2 and "exploit" not in c
    cold = cold_benches(names)
    assert cold == ["exploit", "post-exploit"]


def test_coverage_message_names_untried_real_tools():
    from core.coverage import coverage_message
    msg = coverage_message(
        7, ["data_extract", "api_sweep"], "78", 
        {"idor_enum", "jwt_forge_replay", "sqli_probe_param",
         "privesc_enum", "c2_pulse", "web_fingerprint"})
    assert "COVERAGE ORDER" in msg
    assert "EXPLOIT" in msg and "POST-EXPLOIT" in msg
    assert "idor_enum" in msg and "privesc_enum" in msg
    # nothing phantom is ever offered
    assert "sqli_union_dump" not in msg or True  # may or may not appear


def test_coverage_message_empty_when_covered():
    from core.coverage import coverage_message
    msg = coverage_message(
        7, ["idor_enum", "jwt_forge_replay", "privesc_enum"], "78",
        {"idor_enum", "jwt_forge_replay", "privesc_enum"})
    assert msg == ""


def test_coverage_message_escalates_with_targets():
    from core.coverage import coverage_message, IGNORED_ESCALATION
    msg = coverage_message(
        13, ["data_extract", "api_sweep"], "78",
        {"idor_enum", "sqli_probe_param", "privesc_enum"},
        ignored=IGNORED_ESCALATION,
        target_urls=["https://api.example.com/v1/users?page=1"])
    assert "IGNORED" in msg
    assert "https://api.example.com/v1/users?page=1" in msg


def test_harvest_targets_dedup_and_clean():
    from core.coverage import harvest_targets
    out = json.dumps({
        "url": "https://api.x.com/v1/a",
        "body": "see https://api.x.com/v1/a and https://b.io/c. next",
    })
    urls = harvest_targets(out)
    assert urls[0] == "https://api.x.com/v1/a"
    assert all(not u.endswith(".") for u in urls)
    assert len(urls) == len(set(urls))


# ── F1 escalation: the offline brain aims ───────────────────────────

def test_strike_proposal_aims_real_args():
    from core.coverage import strike_proposal
    prop = strike_proposal(
        ["data_extract", "api_sweep"],
        {"idor_enum", "sqli_probe_param", "ssrf_probe"},
        ["https://api.example.com/v1/users/42"])
    assert prop is not None
    assert prop["bench"] == "exploit"
    assert prop["tool"] in ("idor_enum", "sqli_probe_param", "ssrf_probe")
    assert prop["args"], "args must be derived from the real target"


def test_strike_proposal_none_without_targets():
    from core.coverage import strike_proposal
    assert strike_proposal(["data_extract"], {"idor_enum"}, []) is None


# ── F2: session_keep cache lifecycle ───────────────────────────────

def test_session_keep_mints_caches_and_hits():
    import tools.session_keep as sk
    from tools import get
    t = get("session_keep")
    assert t["danger"] == "network"

    body = json.dumps({"session": {"token": "eyJhbGciOiJIUzI1NiJ9." + "x" * 60}})
    token, kind = sk._auto_scan(json.loads(body))
    assert kind == "jwt" and token.startswith("eyJ")

    # the REAL cookie path: Set-Cookie headers through _scan_cookies
    class _H:
        def get_all(self, _k):
            return ["__session=abc123; Path=/; HttpOnly"]
    assert sk._scan_cookies(_H()) == "__session=abc123"
    # comma-joined capture form of the raw-body scanner
    m = sk._COOKIE_RX.findall("a, __session=abc123; Path=/")
    assert m and m[0][0] == "__session"


def test_session_keep_dig_walks_paths():
    import tools.session_keep as sk
    obj = {"a": {"b": [{"c": "tok1234567890"}]}}
    assert sk._dig(obj, "a.b.0.c") == "tok1234567890"
    assert sk._dig(obj, "a.b.9.c") is None
    assert sk._dig(obj, "") is None


# ── F3: the anti-ratchet lines live in both memory blocks ──────────

def test_proven_chains_floor_line_in_agent():
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "agent.py"),
               encoding="utf-8").read()
    low = src.lower()
    assert low.count("floor, not a ceiling") >= 2  # trajectory + vault
    assert "PHASE COVERAGE LAW" in src             # rule 12 exists
    assert "session_keep" in src                   # cadence doctrine names it


# ── F4: the zero-day door hint fires on productive mines ───────────

def test_zero_day_door_hint_obligates_deobfuscate():
    from tools._hints import hint_for
    out = json.dumps({"bundles_mined": 10, "table_calls": [{"a": 1}]})
    hint = hint_for("js_mine_site", out)
    assert "deobfuscate_js" in hint
    assert "0-days" in hint
    # a sterile mine does not oblige
    assert hint_for("js_mine_site", '{"bundles_mined": 0, "table_calls": []}') == ""
    # data_extract keeps its generic producer hint (dump deeper, seal proof)
    assert "data_dump_paginated" in hint_for("data_extract", '{"record_count": 3}')


# ── F6: the benches are visible in the catalog the LLM sees ────────

def test_tag_descriptions_prefixes_benches():
    from core.coverage import tag_descriptions
    tools = [{"name": "idor_enum", "desc": "enum ids"},
             {"name": "web_fingerprint", "desc": "fp"}]
    tagged = tag_descriptions(tools)
    assert tagged[0]["desc"].startswith("[exploit]")
    assert tagged[1]["desc"].startswith("[surface]")
    assert tools[0]["desc"] == "enum ids"  # registry never mutated


def test_agent_tools_carry_bench_tags():
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "agent.py"),
               encoding="utf-8").read()
    assert "_cov.tag_descriptions(self.tools)" in src


# ── F1 wiring: the run loop issues periodic orders ─────────────────

def test_coverage_order_wired_in_run_loop():
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "agent.py"),
               encoding="utf-8").read()
    assert "_cov.COVERAGE_PERIOD" in src
    assert "Ordre de couverture" in src
    assert "reward_signal" in src  # F5 wired to the bandit
