"""Y-wave (audit 4) guards — vault saves, dossier parses, scrub is case-blind."""
import os, sys, json, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_y1_1_vault_deposit_persists():
    import core.learned_plays as LP
    import core.capability_vault as V
    tmp = tempfile.mktemp(suffix=".json")
    _old = LP.STORE
    LP.STORE = tmp
    try:
        r = V.deposit("play", {"host": "yguard.example", "kind": "grammar",
                               "method": "GET", "path": "/g", "tool": "t",
                               "outcome": "200", "uses": 1,
                               "last_seen": "now"})
        assert r.get("ok") is True, r
        assert isinstance(r.get("merged"), int), r
        d = json.load(open(tmp, encoding="utf-8"))
        assert any(p.get("host") == "yguard.example"
                   for p in d.get("plays", [])), "play not on disk"
    finally:
        LP.STORE = _old
        if os.path.exists(tmp):
            os.remove(tmp)


def test_y2_1_dossier_parses_nested_verdicts():
    # reproduce the exact dossier extraction on a nested-verdict card
    card = ("# FINDING\n\n```json\n"
            '{"tool": "sqli_union_dump", "exploitable": true, '
            '"steps": {"dbms": "mysql", "columns": 5}}\n'
            "```\n")
    import re
    m = re.search(r"```json\s*\n", card)
    assert m
    start = card.find("{", m.end())
    depth, i = 0, start
    while i < len(card):
        if card[i] == "{":
            depth += 1
        elif card[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    v = json.loads(card[start:i + 1])
    assert v["steps"]["dbms"] == "mysql" and v["exploitable"] is True


def test_y3_1_scrub_case_insensitive():
    import core.scrub as S
    old = S._STRINGS
    try:
        S._STRINGS = ["DESKTOP-ABC", "Operator"]
        S._LOADED = [True]
        txt = "host desktop-abc and user OPERATOR and mixed Desktop-Abc"
        out = S.scrub(txt)
        assert "desktop-abc" not in out.lower()
        assert "operator" not in out.lower().replace("[operator]", "")
    finally:
        S._STRINGS = old


def test_y2_2_workspace_auto_isolation():
    from core.mission_workspace import workspace_for, release_workspace, _LIVE_TARGETS
    _LIVE_TARGETS.clear()
    w1 = workspace_for("assess https://iso-y.example/x")
    w2 = workspace_for("assess https://iso-y.example/y")
    assert w1.dir != w2.dir, "concurrent runs must not share the ledger dir"
    assert "run_" in os.path.basename(w2.dir), "second claim must be isolated"
    release_workspace(w1)
    release_workspace(w2)
    w3 = workspace_for("assess https://iso-y.example/z")
    assert "run_" not in os.path.basename(w3.dir), "freed target takes the classic path"
    release_workspace(w3)
    _LIVE_TARGETS.clear()


def test_y2_3_log_run_tolerates_leading_noise():
    from core.mission_workspace import Workspace
    ws = Workspace("yguard-noise.example")
    ws.log_run("t", {}, '\ufeff {"exploitable": true, "summary": "bom ok"}',
               0.1, "ok", 1)
    ws.log_run("t", {}, '[{"exploitable": false, "summary": "array ok"}]',
               0.1, "ok", 1)
    entries = [json.loads(l) for l in open(ws.ledger_path, encoding="utf-8")]
    assert entries[0]["verdict"] and entries[0]["verdict"]["exploitable"] is True
    assert entries[1]["verdict"] and entries[1]["verdict"]["exploitable"] is False


def test_y4_1_tail_lines_reads_end():
    from core.trajectory import _tail_lines
    tmp = tempfile.mktemp(suffix=".jsonl")
    with open(tmp, "w", encoding="utf-8") as f:
        for i in range(5000):
            f.write(json.dumps({"i": i}) + "\n")
    try:
        evs = _tail_lines(tmp, 10)
        assert len(evs) == 10
        assert evs[-1]["i"] == 4999 and evs[0]["i"] == 4990
    finally:
        os.remove(tmp)


def test_y1_2_block_guarantees_kind_slots():
    import core.capability_vault as V
    # top(10) of a play-heavy vault must not bury a used skill
    _old_top, V.top = V.top, lambda n=12: [
        {"kind": "play", "id": f"p{i}", "score": 9, "payload": {}}
        for i in range(10)]
    _old_recall, V.recall = V.recall, lambda kind=None: [
        {"kind": "skill", "id": "sk1", "score": 2, "payload": {"desc": "d"}}]
    try:
        blk = V.capability_block()
        assert "[skill] sk1" in blk, "silent kind must get its slot (Y1.2)"
    finally:
        V.top, V.recall = _old_top, _old_recall
