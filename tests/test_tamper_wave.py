"""VOIDFORGE :: V2 tamper-wave tests — sqli_tamper_chain, vf_template_scan,
httpx_sweep. Pure logic tested offline (no network in tests)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools as reg
reg.discover()

from tools.sqli_tamper import TAMPERS
from tools.template_scan import load_templates, evaluate, _join


def test_tamper_transforms():
    assert TAMPERS["space2comment"]("' UNION SELECT a") == "'/**/UNION/**/SELECT/**/a"
    assert TAMPERS["space2plus"]("' AND 1=1") == "'+AND+1=1"
    assert TAMPERS["double_encode"]("' ") == "%2527%2520"  # %25 = % double-encodé
    assert TAMPERS["quotes_to_double"]("'admin'") == '"admin"'
    assert TAMPERS["prefix_comment"]("UNION SELECT 1").startswith("/*!50000")
    # deterministic case randomizer
    assert TAMPERS["case_random"]("UNION") == TAMPERS["case_random"]("UNION")


def test_tamper_chain_registered_and_schema():
    t = reg.get("sqli_tamper_chain")
    assert t["name"] == "sqli_tamper_chain"
    assert set(t["params"]["required"]) == {"url", "param"}


def test_template_pack_loads():
    tpls = load_templates(None)
    ids = {t["id"] for t in tpls}
    assert "git-config-leak" in ids and "env-file-leak" in ids
    assert len(tpls) >= 10
    # severity present everywhere
    assert all("info" in t and "severity" in (t["info"] or {}) for t in tpls)


def test_template_filter_by_id():
    tpls = load_templates("git-config-leak")
    assert [t["id"] for t in tpls] == ["git-config-leak"]


def test_matcher_evaluation():
    and_m = [{"type": "status", "status": [200]},
             {"type": "word", "words": ["[core]"]}]
    assert evaluate(and_m, "and", 200, "[core]\n\tbare = true")
    assert not evaluate(and_m, "and", 200, "nothing here")
    assert evaluate(and_m, "or", 404, "welcome to [core] config")  # or: un seul match suffit
    assert not evaluate(and_m, "or", 404, "nothing here")
    reg_m = [{"type": "regex", "regex": ["(?m)^[A-Z_]+="]}]
    assert evaluate(reg_m, "and", 200, "DB_PASSWORD=hunter2")
    assert not evaluate(reg_m, "and", 404, "forbidden")
    all_word = [{"type": "word", "words": ["login", "admin"], "condition": "all"}]
    assert evaluate(all_word, "and", 200, "login admin")
    assert not evaluate(all_word, "and", 200, "login only")


def test_template_join_urls():
    assert _join("http://t.local/sub", "/.env") == "http://t.local/.env"
    assert _join("https://t.local", "") == "https://t.local/"


def test_httpx_normalize_and_candidates():
    from tools.httpx_sweep import normalize_hosts, build_candidates
    hs = normalize_hosts("http://a.com, b.com\nc.com:8080, a.com")
    assert hs == ["a.com", "b.com", "c.com"]
    c = build_candidates(["a.com"], [80, 443])
    assert c == ["http://a.com/", "https://a.com/"]
    c2 = build_candidates(["b.com"], [8080])
    assert c2 == ["http://b.com:8080/"]


def test_httpx_and_template_registered():
    assert reg.get("httpx_sweep")["name"] == "httpx_sweep"
    assert reg.get("vf_template_scan")["name"] == "vf_template_scan"
