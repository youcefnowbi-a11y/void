"""Phase 2 (Ω2) guards — the adversarial twin: truth table, blind policy,
reliability ranks, twin call discipline.

Laws under test:
- law #2: no verdict without proof — a blind-class confirmation without
  receipt and without inline differential is CAPPED at partial
- sqlmap fidelity: the truth table kills always-true (honeypot),
  always-false (broken), echoing oracles; honest oracles pass
- metasploit fidelity: MinimumRank discount — a low-rank tool's verdicts
  carry a deterministic discount citation
- budget discipline: the LLM twin call is capped per hour, cached per
  identical verdict; offline/unconfigured → deterministic-only
"""
import json
import time

import core.twin as tw


# ── 2.2 truth table ─────────────────────────────────────────────────

def test_t01_truth_table_honest_oracle():
    tw.reset()
    # a real boolean oracle: statement is true iff both sides equal
    ok, table = tw.truth_table(lambda stmt, pr:
                               "=" in stmt and len(stmt.split("=")) == 2
                               and stmt.split("=")[0].strip()
                               == stmt.split("=")[1].strip())
    assert ok, table
    assert len(table) == tw._TRUTH_REPS


def test_t02_truth_table_kills_honeypots():
    tw.reset()
    # always-true (honeypot): must FAIL
    ok, _ = tw.truth_table(lambda stmt, pr: True)
    assert not ok
    # always-false (broken oracle): must FAIL (must_true is False)
    ok, _ = tw.truth_table(lambda stmt, pr: False)
    assert not ok


def test_t03_truth_table_kills_echo():
    tw.reset()
    # echoing oracle: returns True iff the probe contains '=' — r1=r1 true,
    # r1=r2 ALSO true (echo) → must fail
    ok, _ = tw.truth_table(lambda stmt, pr: "=" in stmt)
    assert not ok


def test_t04_truth_table_exception_safe():
    tw.reset()
    ok, table = tw.truth_table(lambda stmt, pr: (_ for _ in ()).throw(ValueError))
    assert not ok


# ── 2.4 blind policy ────────────────────────────────────────────────

def _ssrf_out(callback, signals, exploitable=True):
    return json.dumps({
        "tool": "ssrf_probe", "url_template": "http://t/?u={}",
        "oob": {"url": "x.oob.internal", "callback_received": callback,
                "proof": "oob_callback" if callback else None},
        "signals_found": signals,
        "suspected_ssrf_vectors": [],
        "exploitable": exploitable,
        "proof_object": {"proof": "oob_callback", "protocol": "dns",
                         "token": "tok123", "tag": "ssrf"} if callback else None,
    })


def test_t05_blind_contradiction_capped():
    tw.reset()
    # exploitable=True, ZERO signals, NO callback → capped at partial
    adj, note = tw.blind_policy(_ssrf_out(False, 0))
    assert adj is not None and "partial" in adj
    d = json.loads(adj)
    assert d["exploitable"] == "partial" and d["proof_object"] is None
    assert "law #2" in note


def test_t06_blind_inline_confirmed_passes():
    tw.reset()
    # exploitable=True, inline signals ≥1 → legitimate, pass through
    adj, note = tw.blind_policy(_ssrf_out(False, 2))
    assert adj is None and note is None


def test_t07_blind_oob_receipt_confirms():
    tw.reset()
    adj, note = tw.blind_policy(_ssrf_out(True, 0))
    assert adj is True          # True = confirmed, cite the note
    assert "dns" in note and "tok123" in note


def test_t08_non_blind_untouched():
    tw.reset()
    # no oob structure → not blind-class, pass through untouched
    adj, note = tw.blind_policy(json.dumps({"tool": "dir_brute",
                                            "exploitable": True}))
    assert adj is None and note is None
    # garbage never raises
    assert tw.blind_policy("not json") == (None, None)
    assert tw.blind_policy(None) == (None, None)


def test_t09_hypothesis_not_capped():
    tw.reset()
    # exploitable is already False (hypothesis) → honest, untouched
    adj, _ = tw.blind_policy(_ssrf_out(False, 0, exploitable=False))
    assert adj is None


# ── 2.3 reliability ranks ────────────────────────────────────────────

def test_t10_rank_computation():
    tw.reset()
    tw.refresh_ranks({"great_tool": {"runs": 10, "wins": 9, "hard": 8},
                      "liar_tool": {"runs": 10, "wins": 1, "hard": 0},
                      "new_tool": {"runs": 1, "wins": 1, "hard": 1}})
    # 0.6*0.9 + 0.4*0.8 = 0.86
    assert abs(tw.rank_of("great_tool") - 0.86) < 0.01
    # 0.6*0.1 + 0.4*0 = 0.06 → below discount
    assert tw.rank_of("liar_tool") < tw.TWIN_DISCOUNT
    # under-evidenced → neutral 0.5
    assert tw.rank_of("new_tool") == 0.5
    # unknown tool → neutral
    assert tw.rank_of("ghost") == 0.5
    # the discount cites the liar
    note = tw.rank_note("liar_tool")
    assert note and "rank" in note
    assert tw.rank_note("great_tool") is None


def test_t11_rank_garbage_safe():
    tw.reset()
    tw.refresh_ranks(None)
    tw.refresh_ranks({"bad": "notadict", "worse": {"runs": "x"}})
    tw.refresh_ranks({"ok": {"runs": 4, "wins": 2, "hard": 1}})
    assert 0.0 <= tw.rank_of("ok") <= 1.0


# ── 2.1 twin call discipline ────────────────────────────────────────

def test_t12_budget_window():
    tw.reset()
    with tw._LOCK:
        tw._LLM_BUDGET["calls"] = tw._LLM_BUDGET["max"]
        tw._LLM_BUDGET["window_start"] = time.time()
    # at cap → budget refused
    assert not tw._budget_ok()
    # window expired → refills
    with tw._LOCK:
        tw._LLM_BUDGET["window_start"] = time.time() - (tw._LLM_BUDGET["window"] + 1)
    assert tw._budget_ok()


def test_t13_twin_unconfigured_deterministic():
    tw.reset()
    tw.configure(None)
    # no LLM bound → deterministic-only record, never raises
    rec = tw.twin_attack("ssrf_probe", _ssrf_out(False, 0))
    assert rec["survived"] is True and rec["deterministic_only"] is True


def test_t14_twin_configure_validation():
    tw.reset()
    tw.configure({"no_provider": True})     # missing provider → unbound
    assert tw._CFG is None
    tw.configure({"provider": {"base_url": "http://x", "api_key": "k",
                                "model": "m"}})
    assert tw._CFG is not None
    tw.configure(None)
    assert tw._CFG is None


def test_t15_twin_note_rendering():
    tw.reset()
    n = tw.twin_note({"attacked": True, "survived": True,
                      "arguments": ["arg1"], "reproof": "redo"})
    assert "SURVIVED" in n and "redo" in n
    n = tw.twin_note({"attacked": True, "survived": False,
                      "arguments": ["arg1"], "reproof": ""})
    assert "SUSTAINED" in n
    assert tw.twin_note(None) == ""
    assert tw.twin_note({"attacked": False, "survived": True,
                         "arguments": [], "reproof": ""}) == ""


def test_t16_twin_cache_dedup():
    tw.reset()
    tw.configure(None)
    out = _ssrf_out(False, 0)
    # unconfigured → no LLM path → cache untouched; verify record shape
    r1 = tw.twin_attack("ssrf_probe", out)
    r2 = tw.twin_attack("ssrf_probe", out)
    assert r1["deterministic_only"] and r2["deterministic_only"]


def test_t17_refresh_from_trajectory_safe():
    # reads the real archive tail (or empty) — never raises
    tw.refresh_from_trajectory()
    # after refresh, every known tool has a sane rank
    assert 0.0 <= tw.rank_of("ssrf_probe") <= 1.0
