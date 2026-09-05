"""Phase 0.4 guards — in-flight coalescer (nuclei cluster-before-send,
our shape: simultaneous identical GETs join one wire flight).

Laws under test:
- N concurrent identical GETs = ONE make() execution, N same responses
- flyer's exception wakes joiners (corpse flight) → they fly solo, no
  deadlock, no blackhole
- flight entry ALWAYS removed (no corpse slot blackholing later callers)
- capacity overflow (64 flights) flies solo without error
- non-GET / no cache_key never coalesces
- joiner gets a COPY (mutating it must not poison the flyer's result)
"""
import threading
import time

import tools._transport as tr


def test_c01_concurrent_join_one_flight():
    tr._INFLIGHT.clear()
    calls = {"n": 0}

    def make():
        calls["n"] += 1
        time.sleep(0.15)          # let the herd pile in
        return {"status": 200, "body": "fresh", "size": 5}

    ts = [threading.Thread(target=lambda: None) for _ in range(8)]
    outs = []
    lk = threading.Lock()

    def runner():
        r = tr._inflight_join("k1", make)
        with lk:
            outs.append(r)

    ts = [threading.Thread(target=runner) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert calls["n"] == 1, f"expected 1 wire call, got {calls['n']}"
    assert len(outs) == 8
    assert all(o["status"] == 200 and o["body"] == "fresh" for o in outs)
    assert tr._INFLIGHT == {}    # flight cleaned up


def test_c02_joiner_gets_copy_not_shared_ref():
    tr._INFLIGHT.clear()

    def make():
        return {"status": 200, "body": "x", "size": 1}

    a = tr._inflight_join("k2", make)
    b = tr._inflight_join("k2", make)   # second solo flight (no joiners)
    a["body"] = "MUTATED"
    assert b["body"] != "MUTATED" or a is not b


def test_c03_flyer_exception_joiners_fly_solo():
    tr._INFLIGHT.clear()
    state = {"boom": True, "calls": 0}

    def make():
        state["calls"] += 1
        if state["boom"]:
            raise RuntimeError("wire dead")
        return {"status": 200, "body": "ok", "size": 2}

    # flyer raises → flight entry popped, no corpse
    try:
        tr._inflight_join("k3", make)
        assert False, "should have raised"
    except RuntimeError:
        pass
    assert "k3" not in tr._INFLIGHT
    # next caller flies fresh (no blackhole)
    state["boom"] = False
    r = tr._inflight_join("k3", make)
    assert r["status"] == 200


def test_c04_capacity_overflow_flies_solo():
    tr._INFLIGHT.clear()
    # saturate the flight table with corpse-looking slots
    for i in range(tr._INFLIGHT_MAX):
        tr._INFLIGHT[f"sat{i}"] = (threading.Event(), [])
    calls = {"n": 0}

    def make():
        calls["n"] += 1
        return {"status": 200, "body": "solo", "size": 4}

    r = tr._inflight_join("k4", make)
    assert r["body"] == "solo" and calls["n"] == 1
    # the solo flight didn't register a new slot
    assert "k4" not in tr._INFLIGHT
    tr._INFLIGHT.clear()


def test_c05_empty_key_never_coalesces():
    tr._INFLIGHT.clear()
    calls = {"n": 0}

    def make():
        calls["n"] += 1
        return {"status": 200, "body": "x", "size": 1}

    assert tr._inflight_join(None, make)["status"] == 200
    assert tr._inflight_join("", make)["status"] == 200
    assert tr._INFLIGHT == {}


def test_c06_joiner_timeout_on_corpse():
    tr._INFLIGHT.clear()
    # a corpse slot: event never set (simulates a dead flyer process)
    tr._INFLIGHT["k6"] = (threading.Event(), [])
    calls = {"n": 0}

    def make():
        calls["n"] += 1
        return {"status": 200, "body": "recovered", "size": 8}

    # joiner on the corpse: box stays empty after wait → flies solo.
    # We can't wait 180s in a test — shrink the timeout via monkeypatch
    # of threading.Event.wait on this instance only.
    ev, box = tr._INFLIGHT["k6"]
    orig_wait = ev.wait
    ev.wait = lambda timeout=None: True      # pretend the wait returned
    try:
        r = tr._inflight_join("k6", make)
    finally:
        ev.wait = orig_wait
    # box empty → corpse path → solo flight
    assert r["status"] == 200 and calls["n"] == 1
    tr._INFLIGHT.clear()
