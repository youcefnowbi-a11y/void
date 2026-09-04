"""Z-wave (audit 5) guards — exfil on transport, DB tight, verdicts survive."""
import os, sys, json, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_z1_1_z1_2_http_rides_transport():
    src = open("tools/data_exfil.py", encoding="utf-8").read()
    assert "from tools._transport import fetch" in src, \
        "_http must ride the hardened transport (Z1.2)"
    _body = src.split("def _http")[1].split("\ndef ")[0]
    assert "urllib.request.urlopen" not in _body, \
        "_http must not naked-urlopen anymore (Z1.1/Z1.2)"
    # the adapter's body cap is inherited from fetch (500KB), and the
    # pre-cooked wire carries W14 form encoding
    from unittest.mock import patch
    from tools import data_exfil
    sent = {}

    def fake_fetch(url, method="GET", headers=None, body=None,
                   timeout=25, use_cache=False):
        sent["body"] = body
        return {"status": 200, "body": "ok", "headers": {},
                "size": 2, "final_url": url}

    with patch("tools._transport.fetch", fake_fetch):
        data_exfil._http("https://t.example/api", method="POST",
                         body={"a": {"b": 1}}, content_type="form")
    assert b'a=%7B%22b%22%3A' in sent["body"], "W14 form contract held"


def test_z3_1_no_leaked_connections():
    src = open("core/state.py", encoding="utf-8").read()
    # every _conn() must be closed in a finally
    opens = src.count("c = _conn()")
    guards = src.count("finally:")
    assert opens <= guards + 1, \
        f"{opens} _conn() for only {guards} finally-guards — leaks remain"


def test_z3_2_verdict_survives_shrink():
    from core.state import _shrink_result
    # the REAL scenario: a JSON result where the verdict rides AFTER
    # 60KB of extracted rows — the old [:8000] cut killed it silently.
    rows = [{"id": i, "code": f"GC-XXXX-{i:04d}"} for i in range(1400)]
    txt = json.dumps({"rows": rows, "total": 900, "tool": "sqli_union_dump",
                      "exploitable": True, "summary": "verdict at tail"})
    assert len(txt) > 40000, "fixture must actually exceed the budget"
    shrunk = _shrink_result(txt)
    assert "exploitable" in shrunk, "verdict must survive the shrink (Z3.2)"
    d = json.loads(shrunk)  # the shrunk blob must stay PARSEABLE
    assert d.get("exploitable") is True
    # small results pass untouched
    assert _shrink_result('{"a": 1}') == '{"a": 1}'


def test_z2_1_unmade_connections_o1_pairs():
    from core.blackboard import Blackboard
    bb = Blackboard("zguard.example")
    for i in range(30):
        bb.add_asset("key", f"k{i}", confidence=0.9)
        bb.add_asset("endpoint", f"https://e{i}.example/x", confidence=0.9)
    for i in range(30):
        bb.link(f"key:k{i}", "auth", f"endpoint:https://e{i}.example/x")
    sug = bb.unmade_connections(limit=870)
    # 30x30=900 pairs, 30 linked -> 870 unlinked suggestions
    assert isinstance(sug, list) and len(sug) == 870
    assert all("suggestion" in s for s in sug)


def test_z4_1_belief_direction_updates_on_retest():
    import core.beliefs as B
    _old = B.PATH
    B.PATH = tempfile.mktemp(suffix=".json")
    try:
        # first record: REFUTED with default direction (the old bug froze it)
        B.record("zt.example", "rate limit enforced", "REFUTED")
        # re-test CONFIRMS the defense HELD — direction must update
        B.record("zt.example", "rate limit enforced", "CONFIRMED",
                 direction="held")
        b = B.recall("zt.example")[0]
        assert b["direction"] == "held", \
            f"re-test direction must override the stale default, got {b['direction']}"
    finally:
        B.PATH = _old
        if os.path.exists(B.PATH):
            os.remove(B.PATH)


def test_z4_2_upload_shell_marker_pair():
    src = open("tools/upload_shell.py", encoding="utf-8").read()
    assert "probe_shell" not in src, "identity no-op must be gone (Z4.2)"
    assert 'if m1 in (gbody or "") and (m2 in (gbody or "") or "uid=" in (gbody or ""))' in src, \
        "marker PAIR must gate verification (Z4.2)"


def test_z2_2_target_model_no_dead_loop():
    src = open("core/target_model.py", encoding="utf-8").read()
    assert "_ENDPOINT_RX.findall(text[:12000])" not in src, \
        "dead outer loop must be gone (Z2.2)"


def test_z5_3_skills_memoized():
    import core.skills as S
    a = S.list_skills()
    b = S.list_skills()
    assert a is b, "second call must hit the mtime memo (Z5.3)"


def test_z5_2_burn_none_host_safe():
    # RÉFUTÉ finding — but guard the contract anyway: burn() on an unseen
    # host must never crash.
    from core.op_identity import burn
    r = burn("never-seen-z.example")
    assert r["gen"] == 1 and r["host"] == "never-seen-z.example"
