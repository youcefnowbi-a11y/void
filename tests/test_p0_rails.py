"""Phase 0.2 guards — mission stop rails (ffuf discipline).

Laws under test:
- deterministic arithmetic over a bounded window (law #3)
- noise-tool exemption (WB2 lesson: probe 40x are data, not walls)
- rails arm at ffuf thresholds (95% 403 / 20% 429 over 50+) and only
  deliver once per escalation; rearm on collapse or worsening
- observe() never raises on garbage input
"""
import core.stop_rails as sr


def _obs_status(code, tool="some_tool", n=1):
    return sr.observe(tool, '{"status": %d}' % code * 1) if n == 1 else None


def test_s01_window_and_wall_arming():
    sr.reset()
    # 49 walls: below min_n — no rail
    for _ in range(49):
        sr.observe("some_tool", '{"status": 403}')
    assert sr.pending() is None
    # 50th wall: wall rail arms at exactly 50 / 95%+
    sr.observe("some_tool", '{"status": 403}')
    r = sr.pending()
    assert r and r["rail"] == "wall_403" and r["n"] == 50
    assert r["share"] >= 0.95


def test_s02_delivery_once_then_rearm_on_worse():
    sr.reset()
    # 98% wall (59/60): rail arms, delivered at 0.983
    for _ in range(59):
        sr.observe("some_tool", '{"status": 403}')
    sr.observe("some_tool", '{"status": 200}')
    r = sr.pending()
    assert r and r["rail"] == "wall_403" and abs(r["share"] - 0.983) < 0.01
    sr.deliver(r["rail"], r["share"])
    # delivered at this share: not pending again (no nagging)
    assert sr.pending() is None
    # WORSE wall (pure-403 flood pushes share to 100%): re-arms
    for _ in range(200):
        sr.observe("some_tool", '{"status": 403}')
    r2 = sr.pending()
    assert r2 and r2["rail"] == "wall_403" and r2["share"] > r["share"]
    sr.deliver(r2["rail"], r2["share"])


def test_s03_rate_rail_and_collapse_rearm():
    sr.reset()
    # 12/57 = 21% 429 over 57 = rate rail
    for _ in range(45):
        sr.observe("some_tool", '{"status": 200}')
    for _ in range(12):
        sr.observe("some_tool", '{"status": 429}')
    r = sr.pending()
    assert r and r["rail"] == "rate_429" and r["share"] >= 0.20
    sr.deliver(r["rail"], r["share"])
    assert sr.pending() is None
    # healthy traffic floods the window: share collapses below 10%
    # (< half threshold) → rail forgotten, can re-arm fresh later
    for _ in range(300):
        sr.observe("some_tool", '{"status": 200}')
    assert sr.pending() is None
    for _ in range(100):
        sr.observe("some_tool", '{"status": 429}')
    r2 = sr.pending()
    assert r2 and r2["rail"] == "rate_429"


def test_s04_noise_tool_exempt():
    sr.reset()
    # idor/auth/oracle tools EXPECT 40x — never rail
    for _ in range(60):
        sr.observe("idor_enum", '{"status": 403}')
    assert sr.pending() is None
    for _ in range(60):
        sr.observe("auth_state_audit", '{"status_code": 401}')
    assert sr.pending() is None


def test_s05_transport_dead_not_rail():
    sr.reset()
    # transport-dead statuses (-1/0) are the circuit breaker's domain
    for _ in range(60):
        sr.observe("some_tool", '{"status": -1}')
    assert sr.pending() is None
    assert sr.stats()["n"] == 0


def test_s06_mixed_statuses_honest_shares():
    sr.reset()
    # 90% 403 over 60: below 95% → no wall rail (honesty about noise)
    for _ in range(54):
        sr.observe("some_tool", '{"status": 403}')
    for _ in range(6):
        sr.observe("some_tool", '{"status": 200}')
    assert sr.pending() is None


def test_s07_garbage_never_raises():
    sr.reset()
    sr.observe("t", None)
    sr.observe("", '{"status":')
    sr.observe("t", 12345)          # non-str out
    sr.observe("t", '{"status": "abc"}')
    sr.observe("t", '{"status": 999}')    # out of range
    sr.observe("t", '{"status": 403}', )
    assert sr.stats()["n"] == 1


def test_s08_window_bounded():
    sr.reset()
    for i in range(1000):
        sr.observe("t", '{"status": %d}' % (200 if i % 2 else 404))
    assert sr.stats()["n"] <= 400


def test_s09_reset_clears_everything():
    sr.reset()
    for _ in range(60):
        sr.observe("some_tool", '{"status": 403}')
    sr.deliver("wall_403", 1.0)
    sr.reset()
    assert sr.stats()["n"] == 0
    assert sr.stats()["delivered"] == {}


def test_s10_per_payload_statuses_count():
    sr.reset()
    # one output carrying many payload statuses = many observations
    # (ffuf semantics — per-response accounting)
    body = ",".join('"status": %d' % c for c in [403] * 55)
    sr.observe("some_tool", "{" + body + "}")
    r = sr.pending()
    assert r and r["rail"] == "wall_403" and r["n"] == 55
