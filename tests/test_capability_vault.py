# -*- coding: utf-8 -*-
"""Guard tests — E2 unified capability vault."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
import core.capability_vault as V


def _tmp_meta():
    fd, p = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(p)
    return p


def setup_function(fn):
    fn._tmp = _tmp_meta()
    fn._old = V.META
    V.META = fn._tmp


def teardown_function(fn):
    V.META = fn._old
    if os.path.exists(fn._tmp):
        os.unlink(fn._tmp)


def test_touch_and_score_roundtrip():
    V.touch("skill", "web_access_master")
    V.touch("skill", "web_access_master")
    V.touch("forged", "forged_http_request")
    assert V._usage("skill", "web_access_master") == 2
    assert V._usage("forged", "forged_http_request") == 1
    assert V._usage("skill", "never_touched") == 0


def test_touch_ignores_garbage():
    V.touch("nope_kind", "x")
    V.touch("skill", "")
    V.touch(None, None)
    assert V._load_meta().get("usage", {}) == {} or all(
        k.startswith(("skill:", "forged:", "play:"))
        for k in V._load_meta().get("usage", {}))


def test_inventory_shape_and_forged_presence():
    inv = V.recall()
    assert inv, "inventory must never be empty on a healthy install"
    for r in inv:
        assert r["kind"] in V.KINDS
        assert isinstance(r["score"], int)
        assert "payload" in r
    # the live arsenal ships known forged tools — they must be visible
    ids = {r["id"] for r in inv if r["kind"] == "forged"}
    assert any(i.startswith("forged_") for i in ids)


def test_play_inventory_carries_native_uses():
    plays = [r for r in V.recall("play") if r["kind"] == "play"]
    for p in plays:
        assert p["score"] >= 1  # plays are born with uses=1


def test_top_sorts_by_score():
    plays = [r for r in V.recall("play")]
    inv = V.recall()
    ranked = V.top(len(inv))
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)


def test_deposit_versions_with_content_hash_and_provenance():
    p1 = {"id": "my_skill", "payload": "v1 text"}
    r1 = V.deposit("skill", p1, provenance="mission venice #71")
    assert r1["ok"] and r1["version_count"] == 1
    V.deposit("skill", {"id": "my_skill", "payload": "v2 text"},
              provenance="mission venice #72")
    vs = V.versions("skill", "my_skill")
    assert len(vs) == 2
    assert vs[0]["hash"] != vs[1]["hash"]
    assert "venice #71" in vs[0]["provenance"]


def test_deposit_same_content_never_duplicates():
    for _ in range(3):
        V.deposit("forged", {"id": "f_tool", "payload": "same"})
    assert len(V.versions("forged", "f_tool")) == 1


def test_deposit_unknown_kind_honest_error():
    assert "error" in V.deposit("ghost_kind", {"id": "x"})


def test_corrupt_meta_degrades_to_honest_empty():
    with open(V.META, "w", encoding="utf-8") as f:
        f.write("{ this is not json !!!")
    assert V._usage("skill", "x") == 0
    V.touch("skill", "x")  # self-heals on next write
    assert V._usage("skill", "x") == 1


def test_capability_block_ranks_and_mentions_kinds():
    # REAL forged tool name from the live registry — the E2 audit caught a
    # test forging a ghost identity ("forged_hot_tool") that touch() counted
    # while recall() rightly never listed it.
    from tools import _REGISTRY, _DISCOVERED
    if not _DISCOVERED:
        from tools import discover
        discover()
    real = next(n for n in _REGISTRY if n.startswith("forged_"))
    V.touch("forged", real)
    V.touch("forged", real)
    V.touch("forged", real)
    blk = V.capability_block()
    assert blk and "CAPABILITY VAULT" in blk
    assert f"[forged] {real}" in blk
    lines = [l for l in blk.splitlines() if l.startswith("- [")]
    assert lines[0].startswith(f"- [forged] {real}"), \
        f"top-reuse first, got: {lines[0]}"


def test_untried_kinds_still_visible():
    """AUDIT E2-V2: a forged tool never used must still be announced —
    untried is not nonexistent."""
    blk = V.capability_block()
    assert blk and "[forged]" in blk, \
        "fresh install: forged arsenal must be visible as available"


def test_capability_block_caps_length():
    blk = V.capability_block(cap=400)
    assert len(blk) <= 400
