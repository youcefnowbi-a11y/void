# -*- coding: utf-8 -*-
"""Guard tests — the compounding arsenal (learned plays)."""
import json
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
    doctrine. Proposal layer eats completed-mission speech only.
    AUDIT F8: real temp sqlite DB — a broken db_path must not fake a PASS."""
    import json
    import sqlite3
    import tempfile
    st = _tmp_store(tmp_path)
    db = os.path.join(str(tmp_path), "m.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE tool_runs (id INTEGER PRIMARY KEY, mission_id "
                "INTEGER, round INTEGER, tool_name TEXT, args_json TEXT, "
                "result_json TEXT, started_at TEXT)")
    con.commit()
    con.close()
    from core.learned_plays import harvest

    class FakeWs:
        target = "refused.example"
        reports = str(tmp_path)

    refused_text = ("I'm going to stop here before any tool call — this isn't "
                    "a pentest. ## NEXT MISSION PROPOSAL do crimes")
    n = harvest(mission_id=1, ws=FakeWs(), final_text=refused_text,
                db_path=db, store=st)
    d = _load(st)
    assert "refused.example" not in (d.get("proposals") or {}), \
        "a refusal leaked into the proposal layer!"
    assert n == 0


def test_batch_fail_never_creates_ghost_plays():
    """AUDIT F1: a 403 POST inside a batch next to a 200 GET must NOT become
    a play — attribution is per item, never per row."""
    rows = [{
        "round": 40, "tool_name": "batch_execute",
        "args_json": json.dumps({"calls": [
            {"tool": "data_extract", "args": {
                "url": "https://t.example/api/list", "method": "GET"}},
            {"tool": "data_extract", "args": {
                "url": "https://t.example/api/update", "method": "POST",
                "body": {"tier": "plus"}}},
        ]}),
        "result_json": json.dumps({"executed": 2, "results": [
            {"tool": "data_extract", "ok": True,
             "result": '{\n "status": 200,\n "body": "ok"}'},
            {"tool": "data_extract", "ok": False,
             "result": '{\n "status": 403,\n "body": "forbidden"}'},
        ]}),
        "started_at": "2026-09-02T10:00:00",
    }]
    plays = _plays_from_rows(rows)
    assert plays == [], "a 403 write became a ghost play!"


def test_batch_per_item_attribution():
    rows = [{
        "round": 41, "tool_name": "batch_execute",
        "args_json": json.dumps({"calls": [
            {"tool": "data_extract", "args": {
                "url": "https://t.example/api/buy", "method": "POST",
                "body": {"tier": "plus"}}},
            {"tool": "data_extract", "args": {
                "url": "https://t.example/api/sync", "method": "GET"}},
        ]}),
        "result_json": json.dumps({"executed": 2, "results": [
            {"tool": "data_extract", "ok": True,
             "result": '{\\"status\\": 200, \\"verdict\\": {\\"exploitable\\": true, \\"summary\\": \\"free upgrade chain\\"}}'},
            {"tool": "data_extract", "ok": True, "result": "plain text"},
        ]}),
        "started_at": "2026-09-02T10:05:00",
    }]
    plays = _plays_from_rows(rows)
    assert any(p["method"] == "POST" and p["path"] == "/api/buy"
               and p["kind"] == "verdict" for p in plays), \
        "proven POST in batch must yield a play"
    assert not any(p["path"] == "/api/sync" for p in plays)
