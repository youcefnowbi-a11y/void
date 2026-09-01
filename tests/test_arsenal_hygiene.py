"""VOIDFORGE :: arsenal hygiene tests — purge verification + phase guide.
The phase guide exists to break the 'same 6-8 tools every mission' bias."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import DOCTRINE


def _registry_names():
    from tools import discover, all_tools
    discover()
    return {t["name"] for t in all_tools()}


def test_purged_forged_gone():
    names = _registry_names()
    dead = ["forged_noop", "forged_nodesc_test", "forged_forged_upper",
            "forged_scope_guard", "forged_scope_guard_v2",
            "forged_env_explore", "forged_env_explore2",
            "forged_param_schema_test", "forged_persistence_ping",
            "forged_read_report", "forged_read_reports",
            "forged_read_last_report", "forged_list_missions",
            "forged_admin_token_brute", "forged_admin_token_brute2",
            "forged_admin_token_brute3"]
    for n in dead:
        assert n not in names, n


def test_kept_forged_alive():
    names = _registry_names()
    for n in ("forged_admin_token_brute_v4", "forged_http_request",
              "forged_invoice_dumper", "forged_siwx_signer"):
        assert n in names, n


def test_phase_guide_present():
    assert "PHASE GUIDE" in DOCTRINE
    assert "REPETITION RULE" in DOCTRINE


def test_phase_guide_tools_exist():
    names = _registry_names()
    m = re.search(r"PHASE GUIDE.*?TOOL SELECTION RULES", DOCTRINE, re.S)
    assert m, "phase guide block missing"
    bench = m.group(0)
    # every bench line references REAL registry tools (spot the 4 phases)
    for sentinel in ("web_fingerprint", "api_sweep", "sqli_union_dump",
                     "evidence_pack", "crash_triage_next"):
        assert sentinel in bench
    # at least 50 distinct registry names appear in the guide
    tokens = set(re.findall(r"\b[a-z][a-z0-9_]{2,}\b", bench))
    hits = sum(1 for n in names if n in tokens)
    assert hits >= 50, hits


def test_arsenal_size_and_discover_idempotent():
    # L'arsenal est VIVANT: la stratège forge pendant les campagnes (siwx_,
    # diag_... apparu en live). Donc: plancher fixe (93 core + forgés gardés),
    # PAS de plafond, et idempotence discover() x3 dans le même process.
    from tools import discover as _d, all_tools as _all
    _d()
    n1 = len(_all())
    _d()
    _d()
    n2 = len(_all())
    assert n1 == n2, (n1, n2)
    assert n1 >= 93, n1
