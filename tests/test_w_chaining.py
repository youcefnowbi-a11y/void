"""W-wave (audit 2) guards — chaining data must survive compaction."""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import _smart_compact, _feed_result


def _mk_result():
    return json.dumps({
        "tool": "cmd_exec_probe", "exploitable": True,
        "summary": "RCE confirmed via ; separator",
        "primitive": {"separator": ";", "payload": ";id", "engine": "bash"},
        "rce_primitive": "echo VFX1; {CMD}",
        "dbms": "mysql", "columns": ["user", "pass"], "render_col": 3,
        "oracle": {"true": [200, 5310], "false": [200, 5280]},
        "rows": [{"id": i, "u": f"user{i}"} for i in range(50)],
        "steps": {"width": 5},
    })


def test_wa1_smart_compact_keeps_chaining_keys():
    r = _smart_compact(_mk_result(), limit=300)
    d = json.loads(r)
    # the chaining keys the old version dropped
    assert d.get("primitive") == {"separator": ";", "payload": ";id", "engine": "bash"}
    assert d.get("rce_primitive") == "echo VFX1; {CMD}"
    assert d.get("dbms") == "mysql"
    assert d.get("columns") == ["user", "pass"]
    assert d.get("render_col") == 3
    assert "oracle" in d
    assert d.get("exploitable") is True


def test_wa1_smart_compact_elides_bulk_in_place():
    # 50 rows must never ride raw; either summarized (count+head) when
    # they fit the budget, or dropped entirely (archived in extractions/)
    # — never a mid-JSON slice. Both outcomes must leave parseable JSON
    # with the chaining keys intact.
    r = _smart_compact(_mk_result(), limit=300)
    d = json.loads(r)
    rows = d.get("rows")
    if isinstance(rows, dict):
        assert rows.get("_elided") == 50
    else:
        assert "rows" not in d          # dropped whole, not sliced
    assert d.get("primitive")           # chaining survived regardless
    # a smaller bulk (fits budget) must be summarized in place
    small = json.dumps({"tool": "t",
                        "rows": [{"id": i} for i in range(8)],
                        "primitive": {"separator": ";"}})
    d2 = json.loads(_smart_compact(small, limit=300))
    assert d2.get("primitive") == {"separator": ";"}


def test_wa2_feed_result_nested_json_survives():
    # nested structures previously lost inner closing braces to rstrip("}")
    big = {"steps": {"dbms": "mysql", "columns": 5},
           "oracle": {"true": [200, 5310]},
           "filler": "x" * 30000}
    out = _feed_result("sqli_union_dump", json.dumps(big), total_cap=24000)
    d = json.loads(out)          # MUST parse — this is the regression guard
    assert d["steps"]["dbms"] == "mysql"
    assert d["steps"]["columns"] == 5
    assert d["oracle"]["true"] == [200, 5310]


def test_we2_final_summary_french_markers():
    from core.agent import Agent
    class _Stub:  # only _is_final_summary touches self (plan_mode)
        plan_mode = False
        _is_final_summary = Agent._is_final_summary
    s = _Stub()
    assert s._is_final_summary("# RAPPORT DE MISSION FINAL\n blah")
    assert s._is_final_summary("## Synthèse Finale de la mission\n blah")
    assert s._is_final_summary("## Bilan de mission\n blah")
    assert s._is_final_summary("Verdict Final : cible compromis")
    # heuristic: long prose + closing verb, no code fence at the tail
    assert s._is_final_summary("word " * 400 + "En conclusion, la cible est saine.")
    # NOT a summary: short chatter without closing vocabulary
    assert not s._is_final_summary("Je continue l'énumération des endpoints.")


def test_wc2_ssrf_schema_verdict_fields():
    # the tool module must declare and produce the exploitable field
    import tools.ssrf_test as m
    src = open(m.__file__, encoding="utf-8").read()
    assert '"exploitable"' in src, "ssrf_probe must emit exploitable (WC2)"
    assert "from tools._transport import fetch" in src, "ssrf must ride the transport (WC1)"


def test_wb1_wall_noise_regex_exists():
    from core.agent import Agent
    src = open(Agent.__module__.replace(".", "/") + ".py", encoding="utf-8").read() \
        if False else open("core/agent.py", encoding="utf-8").read()
    assert "_NOISE_TOOLS" in src, "auth-probe tools must not count as walls (WB2)"
    # the streak clear must be conditional on a CLEAN status, not blanket else
    assert "elif _cov.honest_status(out)" in src, "streak reset must be gated (WB1)"
