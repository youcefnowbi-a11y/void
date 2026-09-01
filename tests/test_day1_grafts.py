"""VOIDFORGE :: day-1 grafts tests — G11 evidence states, G12 typed chain
memory, G10 identical-call stop-condition."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trajectory import (evidence_state, record, chains, insight,
                             STATE_WEIGHT, _PATH)


def test_evidence_state_ladder():
    assert evidence_state("sqli_probe_param", False, "TOOL ERROR") == "attempted"
    assert evidence_state("sqli_probe_param", True, "2 réponses intéressantes") == "detected"
    assert evidence_state("jwt_forge_replay", True, "VERIFIED — panel reachable") == "confirmed"
    assert evidence_state("upload_webshell", True, "VERIFIED_ADMIN_TOKEN: abc") == "confirmed"
    assert evidence_state("cmd_exec_probe", True, "EXPLOITED: id=www-data") == "exploited"
    assert evidence_state("ssti_detect_rce", True, "RCE CONFIRMED via {{7*7}}") == "exploited"
    assert evidence_state("secret_scan", True, "EXFILTRATED .env to workspace") == "exploited"


def test_record_stores_state_and_chains_rank_by_best_state():
    if os.path.exists(_PATH):
        os.remove(_PATH)
    record(7, "t.local", "web_fingerprint", True, 1.0, round_num=1, state="detected")
    record(7, "t.local", "sqli_probe_param", True, 0.9, round_num=2, state="confirmed")
    record(8, "t.local", "web_fingerprint", True, 1.1, round_num=1, state="detected")
    record(8, "t.local", "sqli_probe_param", True, 0.8, round_num=2, state="exploited")
    ch = chains(min_support=1)
    top = ch[0]
    assert top["chain"] == "web_fingerprint -> sqli_probe_param"
    assert top["best_state"] == "exploited"  # the best PROVEN state wins ranking
    block = insight(min_support=1)
    assert "proven_chains" in block


def test_weight_order():
    assert STATE_WEIGHT["attempted"] < STATE_WEIGHT["detected"] \
        < STATE_WEIGHT["confirmed"] < STATE_WEIGHT["exploited"]


def test_g10_marker_exists_in_doctrine_flow():
    # the persistence protocol lives in the mission message (run()), the G10
    # marker in the tool pacing — verify both strings compile into agent.py
    import core.agent  # noqa: F401  (import-time syntax check is the point)
    import inspect
    src = inspect.getsource(core.agent)
    assert "G10 STOP-CONDITION" in src
    assert "AGENT PERSISTENCE PROTOCOL" in src
