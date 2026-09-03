"""VOIDFORGE :: Tier G — the science engine test battery.

G1 hypothesis_test: structural diff, single-mutation apply, oracle logic,
   verdict matrix (violated/held × fired/silent/inconclusive), G4 hook.
G2 target_model: templatization, endpoint dedup, client-belief capture.
G3 differential_sweep: mutation axis apply, majority-diff oracle, science
   table shape, stop-on-hit economics.
G4 beliefs: record/revise (same claim re-test REVISES confidence, never
   stacks), recall ranking, prompt_block shape, retire.
G5 doctrine: rule 13 exists and names the engine.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "data", "learned", "beliefs_test.json")


# ── G1: the differential primitives ────────────────────────────────

def test_g1_structural_diff():
    from tools.hypothesis_test import _diff
    a = {"id": 1, "tier": "free", "paid": False, "items": [1, 2, 3]}
    b = {"id": 1, "tier": "free", "paid": True, "items": [1, 2]}
    d = _diff(a, b)
    paths = {p for p, _, _ in d}
    assert "paid" in paths and "items[]" in paths
    assert _diff(a, json.loads(json.dumps(a))) == []


def test_g1_mutation_applies_one_variable():
    from tools.hypothesis_test import _apply_mutation
    base = {"url": "https://x.io/api/checkout/{plan}",
            "headers": {"Authorization": "Bearer t"},
            "body": {"plan": "plus", "price": 2900}}
    m = _apply_mutation({"type": "body_param", "path": "price", "value": 1},
                        base)
    assert m["body"]["price"] == 1
    assert m["body"]["plan"] == "plus"          # untouched
    assert base["body"]["price"] == 2900        # baseline never mutated
    m2 = _apply_mutation({"type": "url", "path": "plan", "value":
                          "https://x.io/api/checkout/free"}, base)
    assert "{plan}" not in m2["url"]


def test_g1_oracle_matrix():
    from tools.hypothesis_test import _check_oracle
    resp = {"status": 200, "body": '{"tier": "pro", "ok": true}'}
    ok, _ = _check_oracle({"expect_status": 200, "expect_json_path": "tier",
                            "expect_value": "pro"}, resp)
    assert ok
    ok, _ = _check_oracle({"expect_contains": "pro"}, resp)
    assert ok
    ok, why = _check_oracle({"expect_status": 402}, resp)
    assert not ok and "status" in why
    bare, _ = _check_oracle({}, resp)
    assert bare is None    # no explicit signature → falls to differential


def test_g1_verdict_directions():
    # violated+fired=CONFIRMED (the finding); held+silent=CONFIRMED
    # (proven defense, dossier §1); both need a real differential.
    from tools.hypothesis_test import _check_oracle
    mutant = {"status": 200, "body": '{"paid": true}'}
    fired, _ = _check_oracle({"expect_json_path": "paid"}, mutant)
    silent, _ = _check_oracle({"expect_status": 402}, mutant)
    assert fired and not silent


def test_g1_registry_and_doctrine_wired():
    from tools import get
    t = get("hypothesis_test")
    assert t["danger"] == "network"
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "agent.py"),
               encoding="utf-8").read()
    assert "hypothesis_test IS THE CORE WEAPON" in src  # rule 13


# ── G2: the living target model ────────────────────────────────────

def test_g2_templatize():
    from core.target_model import _templatize
    assert _templatize("https://x.io/api/u/sess_3I8bLN3kKffTuYFrPJc40xkkSuc/t") \
        .endswith("/{ref}/t")
    assert "{uuid}" in _templatize("https://x.io/f/123e4567-e89b-12d3-a456-426614174000")
    assert "{id}" in _templatize("https://x.io/api/orders/998877")


def test_g2_ingest_and_grammar(tmp_path=None):
    from core.target_model import ingest, grammar_block, _path_for, DIR
    os.makedirs(DIR, exist_ok=True)
    host = "model-test-g2.invalid"
    p = _path_for(host)
    if os.path.exists(p):
        os.remove(p)
    ingest(host, "data_extract",
           '{"url": "https://api.' + host + '/v1/users/42"}')
    ingest(host, "js_mine_site",
           'const PRICE_TABLE = {"plus": 2900}; if (plan == "pro") tier="pro";')
    block = grammar_block(host)
    assert "TARGET MODEL" in block and "/v1/users/{id}" in block
    assert "INVARIANT" in block.upper()   # client belief captured from JS line
    os.remove(p)                         # cleanup


# ── G3: delegated iteration ─────────────────────────────────────────

def test_g3_apply_axis():
    from tools.differential_sweep import _apply
    base = {"url": "https://x.io/p/{SWEEP}", "headers": {},
            "body": {"a": {"b": 1}}}
    m = _apply(base, "url_path", "SWEEP", "42")
    assert m["url"].endswith("/p/42")
    m2 = _apply(base, "body_param", "a.b", 99)
    assert m2["body"]["a"]["b"] == 99
    assert base["body"]["a"]["b"] == 1   # base untouched
    m3 = _apply(base, "header", "X-Plan", "pro")
    assert m3["headers"]["X-Plan"] == "pro"


def test_g3_oracle_and_majority_sig():
    from tools.differential_sweep import _oracle_hit, _sig
    r_ok = {"status": 200, "body": '{"tier":"pro"}'}
    r_402 = {"status": 402, "body": '{"error":"payment required"}'}
    assert _oracle_hit({"expect_status": 402}, r_402)
    assert not _oracle_hit({"expect_status": 402}, r_ok)
    assert _sig(r_ok) != _sig(r_402)


def test_g3_registry_wired():
    from tools import get
    t = get("differential_sweep")
    assert t["danger"] == "network"
    assert "one round becomes 50 experiments" in t["desc"]


# ── G4: the belief ledger ───────────────────────────────────────────

def test_g4_record_revise_recall(tmp_path=None):
    import core.beliefs as B
    B.PATH = _T          # isolated ledger for the test
    if os.path.exists(_T):
        os.remove(_T)    # state-robust: no residue from failed prior runs
    host = "belief-test-g4.invalid"
    b1 = B.record(host, "the server re-validates the price_id on charge", "REFUTED",
                  direction="violated", evidence="mutant accepted price_id=1",
                  mission_id=1)
    assert b1 and b1["confidence"] > 0.5 and b1["n"] == 1
    # re-test of the SAME claim REVISES, never stacks
    b2 = B.record(host, "The server re-validates the PRICE_ID on charge!", "REFUTED",
                  direction="violated", mission_id=2)
    beliefs = B.recall(host)
    assert len([b for b in beliefs
                if "re-validates the price_id" in b["claim"].lower()]) == 1
    # a fresh CONFIRMED on the same claim walks confidence UP toward 1
    b3 = B.record(host, "the server re-validates the price_id on charge", "CONFIRMED",
                  direction="held", mission_id=3)
    assert b3["n"] == 3 and 0.0 < b3["confidence"] < 1.0
    blk = B.prompt_block(host)
    assert "SCIENCE LEDGER" in blk
    assert B.retire(host, b1["id"])
    if os.path.exists(_T):
        os.remove(_T)


# ── G5: doctrine + wiring ───────────────────────────────────────────

def test_g5_impact_first_doctrine():
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "agent.py"),
               encoding="utf-8").read()
    assert "13. IMPACT-FIRST HUNTING" in src
    assert "differential_sweep IS YOUR THROUGHPUT" in src
    # round-0 injections wired
    assert "_grammar_block" in src and "_belief_block" in src
    # tap feeds the model
    assert "_tm.ingest(" in src


def test_g5_round0_blocks_exist():
    from core.beliefs import prompt_block as bb
    from core.target_model import grammar_block as gb
    assert bb("no-such-host-g9.invalid") == ""   # empty = no block, honest
    assert gb("no-such-host-g9.invalid") == ""


# ── Tier G SELF-AUDIT — the hostile pass before commit ──────────────

def test_audit_A4_oracleless_never_refutes():
    """A4: no oracle signature + violated direction must NOT invent a
    verdict — REFUTED from silence was an inverted-logic lie."""
    from tools.hypothesis_test import _check_oracle
    fired, _ = _check_oracle({}, {"status": 200, "body": "x"})
    assert fired is None  # reserved: differential reported, verdict withheld


def test_audit_A5_stop_on_hit_implemented():
    """A5: stop_on_hit was declared in the schema but never honored."""
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "tools", "differential_sweep.py"),
               encoding="utf-8").read()
    assert "stop_on_hit and interesting" in src  # honored in the table loop


def test_audit_A6_majority_deviation_is_not_exploitable():
    """A6 (W1 discipline): a bare deviation (429 jitter, redirect noise)
    is a signal, never an exploitable verdict. The gate lives in the
    sweep runner: exploitable is claimed ONLY via has_explicit_oracle."""
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "tools", "differential_sweep.py"),
               encoding="utf-8").read()
    assert "has_explicit_oracle" in src
    assert 'exploitable = True if (has_explicit_oracle' in src
    assert "deviations are signals, not verdicts" in src


def test_audit_A3_url_mutation_without_slot_refuses():
    """A3: no {slot} in baseline.url → honest refusal, never a silent
    whole-url overwrite (a different experiment wearing one-variable
    clothes)."""
    from tools.hypothesis_test import _apply_mutation
    base = {"url": "https://x.io/checkout/plus", "headers": {}}
    m = _apply_mutation({"type": "url", "path": "plan", "value": "free"}, base)
    assert "_mutation_refused" in m and m["url"] == base["url"]


def test_audit_A8_no_netloc_no_ledger_write():
    """A8: an empty host must not pollute a shared 'unknown' bucket — the
    hook gates the write on a non-empty netloc."""
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "tools", "hypothesis_test.py"),
               encoding="utf-8").read()
    hook = src.split("G4 hook")[1][:800]
    assert "if _host:" in hook            # the gate is the contract
    assert ".hostname" in hook             # beliefs are per-HOST (no port)
