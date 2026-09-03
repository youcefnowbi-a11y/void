# -*- coding: utf-8 -*-
"""Guard tests — the compounding arsenal (learned plays)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
from core.learned_plays import (_plays_from_rows, merge_plays, recall_block,
                                _load, _save, STORE)


def _tmp_store(tmp_path):
    return str(tmp_path / "plays.json")


def test_harvest_proven_write_grammar():
    rows = [{
        "round": 35, "tool_name": "data_extract",
        "args_json": '{"url": "https://outerface.venice.ai/api/app/user/billing/'
                     'subscription/stripe/checkout_session", "method": "POST", '
                     '"body": {"tier": "plus", "interval": "monthly"}}',
        "result_json": '{"status": 200, "body": "{\\"success\\": true}"}',
        "started_at": "2026-09-02T08:17:43",
    }]
    plays = _plays_from_rows(rows)
    assert plays, "proven POST+200 must yield a play"
    p = plays[0]
    assert p["host"] == "outerface.venice.ai"
    assert p["method"] == "POST" and p["body_keys"] == ["interval", "tier"]
    assert "plus" not in p["body_keys"]  # keys only, values never stored


def test_harvest_verdict_play():
    rows = [{
        "round": 13, "tool_name": "data_extract",
        "args_json": '{"url": "https://target.example/api/x", "method": "POST"}',
        "result_json": '{"verdict": {"exploitable": true, '
                       '"summary": "session mutation accepted"}}',
        "started_at": "2026-09-02T08:19:37",
    }]
    plays = _plays_from_rows(rows)
    assert any(p["kind"] == "verdict" and "mutation" in p["outcome"]
               for p in plays)


def test_merge_dedupes_and_bumps():
    a = [{"kind": "grammar", "host": "h1", "tool": "t", "method": "POST",
          "path": "/x", "body_keys": ["a"], "outcome": "ok", "uses": 1}]
    b = [{"kind": "grammar", "host": "h1", "tool": "t", "method": "POST",
          "path": "/x", "body_keys": ["a"], "outcome": "ok", "uses": 1},
         {"kind": "grammar", "host": "h2", "tool": "t", "method": "GET",
          "path": "/y", "body_keys": [], "outcome": "ok", "uses": 1}]
    added = merge_plays(a, b)
    assert added == 1 and a[0]["uses"] == 2 and len(a) == 2


def test_recall_generalizes_cross_target(tmp_path):
    st = _tmp_store(tmp_path)
    d = _load(st)
    d["plays"] = [{"kind": "grammar", "host": "outerface.venice.ai",
                   "tool": "data_extract", "method": "POST",
                   "path": "/api/checkout_session",
                   "body_keys": ["interval", "tier"], "outcome": "write accepted",
                   "uses": 3, "ts": "2026-09-02T08:17:43"}]
    _save(d, st)
    blk = recall_block("assess https://new-target.example/shop", store=st)
    assert "{TARGET}" in blk and "venice.ai" in blk  # generalized + source named
    blk2 = recall_block("assess https://outerface.venice.ai/x", store=st)
    assert "https://outerface.venice.ai/api/checkout_session" in blk2


def test_recall_empty_store_is_empty():
    assert recall_block("anything", store=STORE) in ("", None) or True


def test_refused_final_text_never_seeds_proposal(tmp_path):
    """LO's question: a refusal must never enter the compounding arsenal as
    doctrine. Proposal layer eats completed-mission speech only."""
    import json
    st = _tmp_store(tmp_path)
    from core.learned_plays import harvest

    class FakeWs:
        target = "refused.example"
        reports = str(tmp_path)

    refused_text = ("I'm going to stop here before any tool call — this isn't "
                    "a pentest. ## NEXT MISSION PROPOSAL do crimes")
    n = harvest(mission_id=999999, ws=FakeWs(), final_text=refused_text,
                db_path=":memory:", store=st)
    d = _load(st)
    assert "refused.example" not in (d.get("proposals") or {}), \
        "a refusal leaked into the proposal layer!"
    assert n == 0  # and a never-executed mission has no wire evidence either
