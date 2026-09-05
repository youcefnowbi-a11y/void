"""Phase 0.3 guards — per-host circuit breaker (nuclei hosterrorscache).

Laws under test:
- 3 consecutive transport deaths (status -1) → quarantine WITH cause
- success = FULL removal (nuclei discipline), not a decrement
- quarantined host: fetch() refuses with synthetic -3, no wire volley
- stale quarantine (cooldown elapsed) reaps → probe re-arms
- -3 fast-skip must NOT re-mark the breaker (no auto-perpetuation)
- non-transport statuses (404/403/500) never quarantine
- bounded host table; garbage input never raises
"""
import time

import tools._transport as tr


def _dead(host, n=1, cause="URLError: timeout"):
    for _ in range(n):
        tr._tb_observe(host, {"status": -1, "body": cause})


def _alive(host):
    tr._tb_observe(host, {"status": 200, "body": ""})


def test_t01_three_deaths_quarantine_with_cause():
    tr._TRANSPORT_FAILS.clear()
    _dead("a.example.com", 1)
    assert tr.host_quarantined("a.example.com") is None  # not yet
    _dead("a.example.com", 1)
    assert tr.host_quarantined("a.example.com") is None  # not yet
    _dead("a.example.com", 1, cause="ConnectionResetError: reset by peer")
    q = tr.host_quarantined("a.example.com")
    assert q and "reset by peer" in q["cause"]
    assert q["remaining_s"] > 0 and q["until"] > time.time()


def test_t02_success_removes_fully():
    tr._TRANSPORT_FAILS.clear()
    _dead("b.example.com", 2)      # 2 deaths: armed but not quarantined
    _alive("b.example.com")         # one success clears ALL
    assert tr.host_quarantined("b.example.com") is None
    assert "b.example.com" not in tr._TRANSPORT_FAILS
    _dead("b.example.com", 2)       # fresh count: 2 deaths again — still no quarantine
    assert tr.host_quarantined("b.example.com") is None


def test_t03_quarantine_skip_returns_minus3():
    tr._TRANSPORT_FAILS.clear()
    _dead("c.example.com", 3)
    # the fetch fast-skip path: host quarantined → synthetic -3 out,
    # no wire volley, no ROE slot consumed
    q = tr.host_quarantined("c.example.com", refresh=True)
    assert q is not None
    # simulate the exact dict fetch() returns on the skip path
    out = {"status": -3, "body": f"host quarantined: {q['cause']}"}
    # and confirm the -3 does NOT re-mark (no auto-perpetuation)
    tr._tb_observe("c.example.com", out)
    assert tr._TRANSPORT_FAILS["c.example.com"]["count"] == 3  # unchanged


def test_t04_cooldown_expiry_reaps_and_rearms():
    tr._TRANSPORT_FAILS.clear()
    _dead("d.example.com", 3)
    assert tr.host_quarantined("d.example.com") is not None
    # force-expire: the entry's until goes to the past
    with tr._TB_LOCK:
        tr._TRANSPORT_FAILS["d.example.com"]["until"] = time.time() - 1
    # refresh=True reaps the stale entry → probe re-arms
    assert tr.host_quarantined("d.example.com", refresh=True) is None
    assert "d.example.com" not in tr._TRANSPORT_FAILS


def test_t05_non_transport_statuses_never_quarantine():
    tr._TRANSPORT_FAILS.clear()
    for st in (404, 403, 429, 500, 502, 301, 200):
        tr._tb_observe("e.example.com", {"status": st, "body": ""})
    assert tr.host_quarantined("e.example.com") is None
    # and a success among deaths keeps the streak honest:
    _dead("e.example.com", 2)
    _alive("e.example.com")     # streak reset
    _dead("e.example.com", 2)  # 2 more — still under threshold
    assert tr.host_quarantined("e.example.com") is None


def test_t06_fetch_skips_quarantined_helper():
    tr._TRANSPORT_FAILS.clear()
    assert tr.fetch_skips_quarantined("f.example.com") is False
    _dead("f.example.com", 3)
    assert tr.fetch_skips_quarantined("f.example.com") is True


def test_t07_bounded_and_garbage_safe():
    tr._TRANSPORT_FAILS.clear()
    # garbage never raises
    tr._tb_observe(None, None)
    tr._tb_observe("", {"status": -1})
    tr._tb_observe("g", "not a dict")
    tr.host_quarantined(None)
    tr.host_quarantined("")
    # bound: flood of hosts capped
    for i in range(tr._TB_MAX_HOSTS + 50):
        tr._tb_mark_locked(f"h{i}.example.com", "x")
    assert len(tr._TRANSPORT_FAILS) <= tr._TB_MAX_HOSTS
    tr._TRANSPORT_FAILS.clear()


def test_t08_interleaved_deaths_across_hosts_dont_bleed():
    tr._TRANSPORT_FAILS.clear()
    # alternating deaths on two hosts: each needs ITS OWN 3
    for _ in range(2):
        _dead("h1.example.com", 1)
        _dead("h2.example.com", 1)
    assert tr.host_quarantined("h1.example.com") is None
    assert tr.host_quarantined("h2.example.com") is None
    _dead("h1.example.com", 1)   # h1 reaches 3
    assert tr.host_quarantined("h1.example.com") is not None
    assert tr.host_quarantined("h2.example.com") is None  # h2 still at 2
    tr._TRANSPORT_FAILS.clear()
