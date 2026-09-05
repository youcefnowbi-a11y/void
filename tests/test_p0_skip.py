"""Phase 0.5 guards — the skip ledger (caldera skip-reason taxonomy).

Laws under test:
- machine-readable categories; unknown reasons map to 'other' with raw
  detail (closed taxonomy, lossless memory)
- per-mission isolation (start_mission clears; entries carry mission id)
- bounded memory (512; oldest falls off under flood)
- summary() answers "what never fired and why" with counts + examples
- skip() never raises (ledger must not kill the tool path it records)
"""
import core.skip_ledger as sl


def test_k01_categories_and_query():
    sl.reset()
    sl.start_mission("m-test-1")
    sl.skip("unknown_tool", tool="sqlmmap", detail="closest: sqlmap")
    sl.skip("scope_tool", tool="upload_webshell", detail="role=recon")
    sl.skip("roe_blocked", tool="cmd_exec_probe", detail="danger=loud")
    sl.skip("quarantined", tool="transport", detail="host dead.example.com")
    assert len(sl.entries()) == 4
    assert sl.entries(reason="roe_blocked")[0]["tool"] == "cmd_exec_probe"
    assert sl.entries(tool="transport")[0]["reason"] == "quarantined"
    s = sl.summary()
    assert s["total"] == 4 and s["by_reason"]["unknown_tool"] == 1
    assert "sqlmmap" in s["example"]["unknown_tool"]


def test_k02_unknown_reason_maps_other_with_raw():
    sl.reset()
    sl.start_mission("m-test-2")
    sl.skip("weird_future_reason", tool="x", detail="the raw why")
    e = sl.entries(reason="other")
    assert len(e) == 1 and "raw why" in e[0]["detail"]
    assert e[0]["reason"] == "other"


def test_k03_mission_isolation():
    sl.reset()
    sl.start_mission("m-A")
    sl.skip("budget", tool="t1", detail="rounds exhausted")
    sl.start_mission("m-B")
    assert sl.entries() == []          # fresh ledger
    sl.skip("budget", tool="t2", detail="wall")
    assert all(e["mission"] == "m-B" for e in sl.entries())
    assert len(sl.entries()) == 1


def test_k04_bounded_memory():
    sl.reset()
    sl.start_mission("m-flood")
    for i in range(sl._MAX + 100):
        sl.skip("budget", tool=f"t{i}", detail="d")
    assert len(sl.entries()) <= sl._MAX
    # oldest fell off: t0..t99 gone, t100 present
    tools = {e["tool"] for e in sl.entries()}
    assert "t0" not in tools and f"t{sl._MAX + 99}" in tools


def test_k05_never_raises():
    sl.reset()
    sl.skip(None, tool=None, detail=None)
    sl.skip(123, tool=456, detail=[1, 2])       # garbage types
    sl.skip("budget")                            # missing optionals
    assert len(sl.entries()) >= 1


def test_k06_registry_refusals_categorized():
    # the four registry refusal paths record the right category
    sl.reset()
    sl.start_mission("m-reg")
    import tools as T
    # scope_tool: restrict arsenal, call outside it
    _prev = T.current_allowed()
    try:
        T.allowed.names = {"web_fingerprint"}   # tiny arsenal
        T.execute("upload_webshell", {})         # outside → refused
    finally:
        T.allowed.names = _prev
    e = sl.entries(reason="scope_tool")
    assert any(e2["tool"] == "upload_webshell" for e2 in e)
    # unknown_tool: hallucinated name
    T.execute("totally_fake_tool_xyz", {})
    assert any(e2["reason"] == "unknown_tool" for e2 in sl.entries())
    sl.reset()


def test_k07_breaker_skip_categorized():
    # transport breaker refusal records 'quarantined'
    sl.reset()
    sl.start_mission("m-tb")
    import tools._transport as tr
    tr._TRANSPORT_FAILS.clear()
    for _ in range(3):
        tr._tb_observe("dark.example.com", {"status": -1, "body": "URLError"})
    tr._resp_cache_clear = getattr(tr, "_resp_cache_clear", None)
    # fetch the dark host (use_cache=False → no cache; method POST → no
    # coalescer path → straight to breaker fast-skip)
    out = tr.fetch("http://dark.example.com/x", method="POST", use_cache=False)
    assert out["status"] == -3
    e = sl.entries(reason="quarantined")
    assert len(e) == 1 and "dark.example.com" in e[0]["detail"]
    tr._TRANSPORT_FAILS.clear()


def test_k08_summary_shape_for_autopsy():
    sl.reset()
    sl.start_mission("m-sum")
    for _ in range(5):
        sl.skip("rail_pivot", tool="dir_brute", detail="wall_403 at 97%")
    sl.skip("prereq_missing", tool="sqli_union_dump",
            detail="column count unknown")
    s = sl.summary()
    assert s["by_reason"]["rail_pivot"] == 5
    assert "wall_403" in s["example"]["rail_pivot"]
    assert s["total"] == 6
    assert s["mission"] == "m-sum"
    sl.reset()
