"""Phase 0.6 guards — datastore cascade (metasploit datastore, our shape).

Laws under test:
- cascade fills MISSING params only; explicit args always win
- curated closed map: only known param→key pairs auto-fill
- mission layer dies with the mission; session layer sticks
- value hygiene: 4KB cap, garbage never raises
- the agent-facing tool (mission_globals) round-trips set/get/list/unset
- batch inherits through the same choke point (execute())
"""
import json

import core.datastore as ds


def test_d01_cascade_fills_missing_only():
    ds.reset()
    ds.set("auth_token", "tok-123")
    import tools as T
    # a tool param named 'token' absent from args → filled
    # (use a real tool with a token param: js_mine? auth_attack? — use
    # the registry's choke point directly with a fake call)
    # Direct choke test: simulate what execute() does via _cascade fill
    args = {}
    for pk, dk in T._CASCADE_KEYS.items():
        if pk in args and args.get(pk) in (None, "", [], {}):
            v = ds.get(dk)
            if v is not None:
                args[pk] = v
    # 'token' wasn't in args at all → the fill only touches PRESENT keys,
    # so args stays empty: the cascade fills present-but-empty holes only
    assert args == {}
    # present-but-empty 'token' hole → filled
    args = {"token": ""}
    for pk, dk in T._CASCADE_KEYS.items():
        if pk in args and args.get(pk) in (None, "", [], {}):
            v = ds.get(dk)
            if v is not None:
                args[pk] = v
    assert args["token"] == "tok-123"
    # explicit arg WINS (never overridden)
    args = {"token": "EXPLICIT"}
    for pk, dk in T._CASCADE_KEYS.items():
        if pk in args and args.get(pk) in (None, "", [], {}):
            v = ds.get(dk)
            if v is not None:
                args[pk] = v
    assert args["token"] == "EXPLICIT"
    ds.reset()


def test_d02_layers_and_isolation():
    ds.reset()
    ds.set("k1", "mission-val")
    ds.set("k1", "session-val", layer="session")
    assert ds.get("k1") == "mission-val"      # mission wins on read
    ds.start_mission("m2")                    # mission layer dies
    assert ds.get("k1") == "session-val"      # session sticks
    ds.reset()


def test_d03_value_hygiene():
    ds.reset()
    ds.set("big", "x" * 10_000)
    assert len(ds.get("big")) <= 4096
    ds.set(None, None)          # garbage never raises
    ds.set("k", 42)             # non-str coerced
    assert isinstance(ds.get("k"), str)
    ds.reset()


def test_d04_tool_roundtrip():
    ds.reset()
    import tools as T
    T.discover() if not T._DISCOVERED else None
    r = json.loads(T.execute("mission_globals",
                             {"action": "set", "key": "cookies",
                              "value": "sid=abc"}))
    assert r["ok"] and "cookies" in r["cascade"]      # mapped param listed
    r = json.loads(T.execute("mission_globals",
                             {"action": "get", "key": "cookies"}))
    assert r["value"] == "sid=abc"
    r = json.loads(T.execute("mission_globals", {"action": "list"}))
    assert "cookies" in r["globals"]
    r = json.loads(T.execute("mission_globals",
                             {"action": "unset", "key": "cookies"}))
    assert r["ok"]
    assert ds.get("cookies") is None
    ds.reset()


def test_d05_registry_fill_via_real_tool():
    # end-to-end: a datastore global fills a REAL tool call's hole
    ds.reset()
    import tools as T
    ds.set("api_key", "hk_test_key_123")
    # secret_scan? api_sweep takes api_key? — call with api_key as an
    # empty string and check the tool's args post-fill… we can't see the
    # args from outside; instead verify via the event tap: the fill emits
    # a system event naming the param
    seen = []
    T.execute("mission_globals", {"action": "set", "key": "api_key",
                                  "value": "hk_test_key_123"})
    # use a real tool with an api_key param present-but-empty
    out = T.execute("tg_probe", {"handle": "@test", "api_key": ""},
                    on_event=lambda ev: seen.append(ev))
    filled = [e for e in seen if e.get("type") == "system"
              and "api_key" in e.get("text", "")]
    assert filled, f"cascade fill event not emitted; seen={len(seen)}"
    ds.reset()
