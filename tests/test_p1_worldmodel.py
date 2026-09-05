"""Phase 1 (Ω1) guards — the world model: prediction contract, calibrated
comparator, cascade floors, fail-closed slots, TTL discipline.

Laws under test:
- law #1: surprise is the signal — respected = 0, violated = 1, partial
  proportional; unmeasurable axes never fake a verdict
- law #1.4 (caldera): predict with unresolved {slots} DEFERS, never fires
- sqlmap fidelity: markings learned from two clean fetches are REMOVED
  before comparison; the ratio band (0.02/0.98/Δ0.05) and learned
  false-signature decide
- ffuf fidelity: only scalars IDENTICAL across ≥3 semantically-loaded
  probes form the floor; a floor-matching response is noise
- amass fidelity: entries expire on TTL; expired reads return None
  (re-verify) — the graph is the cache
- determinism: no LLM anywhere; garbage never raises
"""
import time

import core.world_model as wm


# ── 1.1 prediction contract ──────────────────────────────────────────

def test_w01_parse_and_extraction():
    wm.reset()
    args = {"url": "http://t.example/", "predict": {
        "expected_status": 200, "expect_contains": "login"}}
    pred, clean = wm.parse_prediction(args)
    assert pred == {"expected_status": 200, "expect_contains": "login"}
    assert "predict" not in clean and clean["url"] == "http://t.example/"
    # absent predict → (None, args unchanged)
    pred, clean = wm.parse_prediction({"url": "x"})
    assert pred is None and clean == {"url": "x"}
    # invalid shapes dropped, call still fires unmeasured
    pred, clean = wm.parse_prediction({"predict": "garbage"})
    assert pred is None
    pred, clean = wm.parse_prediction({"predict": {"expected_status": 42}})
    assert pred is None     # 42 not a valid status
    pred, clean = wm.parse_prediction({"predict": {"expected_status": [200, 204]}})
    assert pred == {"expected_status": [200, 204]}


def test_w02_slot_defer_fail_closed():
    wm.reset()
    pred, clean = wm.parse_prediction({"predict": {
        "expected_status": 200, "expect_contains": "{session_token}"}})
    assert pred == {"deferred": "unresolved-slot"}
    assert "predict" not in clean      # still extracted from tool args


def test_w03_measure_respected():
    wm.reset()
    out = '{"status": 200, "body": "welcome to login page"}'
    v = wm.measure("t", {"url": "http://e.example/"}, {
        "expected_status": 200, "expect_contains": "login"}, out)
    assert v["verdict"] == "respected" and v["surprise"] == 0.0


def test_w04_measure_violated_all_axes():
    wm.reset()
    out = '{"status": 403, "body": "blocked by cloudflare"}'
    v = wm.measure("t", {"url": "http://e.example/"}, {
        "expected_status": 200, "expect_contains": "login",
        "sentinel": "uid="}, out)
    assert v["verdict"] == "violated" and v["surprise"] == 1.0
    assert len(v["notes"]) == 3


def test_w05_measure_partial_and_unmeasured():
    wm.reset()
    # status OK but sentinel absent → partial
    v = wm.measure("t", {"url": "http://e.example/"}, {
        "expected_status": 200, "sentinel": "uid="},
        '{"status": 200, "body": "no markers here"}')
    assert v["verdict"] == "partial" and 0 < v["surprise"] <= 1.0
    # no status axis observable → unmeasured
    v = wm.measure("t", {"url": "http://e.example/"}, {
        "expected_status": 200}, '{"tool": "x", "summary": "no status"}')
    assert v["verdict"] == "unmeasured"


def test_w05b_deep_status_not_faked():
    # audit fix: a 30-status output (dir_brute shape) whose MATCH sits at
    # index 12 must NOT fake a violation — the check scans every status;
    # only the note is display-bounded.
    wm.reset()
    junk = ", ".join(f'"status": 404' for _ in range(12))
    out = "{" + junk + ', "status": 200}'
    v = wm.measure("t", {"url": "http://deep.example/"}, {
        "expected_status": 200}, out)
    assert v["verdict"] == "respected" and v["surprise"] == 0.0


def test_w06_surprise_ring_and_digest():
    wm.reset()
    url = {"url": "http://ring.example/api"}
    for i in range(3):
        wm.measure("t", url, {"expected_status": 200},
                   '{"status": 403, "body": "waf"}')
    d = wm.surprise_digest()
    assert d and d[0]["violations"] >= 1
    assert any("403" in (n or "") or "expected" in (n or "")
               for n in (d[0]["last"] or []))
    assert "ring.example" in d[0]["endpoint"]


def test_w07_prediction_note_deterministic():
    wm.reset()
    n = wm.prediction_note({"verdict": "respected", "surprise": 0.0})
    assert "0 surprise" in n
    n = wm.prediction_note({"verdict": "violated", "surprise": 1.0,
                             "notes": ["expected status 200"]})
    assert "FAUX" in n or "viol" in n.lower()
    assert wm.prediction_note({"verdict": "unmeasured"}) == ""


# ── 1.2 calibrated comparator ─────────────────────────────────────────

def test_w08_markings_removed_before_compare():
    wm.reset()
    a = ("<html><body>Token: ABC123 csrf-token-here XXY END Rest of page"
         " which is quite long and stable across fetches yes stable"
         " content here more stable text</body></html>")
    b = a.replace("ABC123 csrf-token-here XXY", "ZZZ999 csrf-token-here WWW")
    marks = wm.learn_markings("ep1", a, b)
    assert marks, "dynamic span should be marked"
    # a later page with the SAME dynamic zone spliced out → comparison
    # sees only stable content
    c = "<html><body>Token: QQQ777 csrf-token-here QQ2 END Rest of page which is quite long and stable across fetches yes stable content here more stable text</body></html>"
    assert wm.calibrated_verdict("ep1", c, a) == "same"


def test_w09_ratio_band_verdicts():
    wm.reset()
    # identical → same
    assert wm.calibrated_verdict("ep2", "page", "page") == "same"
    # totally different → differs
    assert wm.calibrated_verdict("ep2", "page", "completely other text") == "differs"


def test_w10_learned_false_signature():
    wm.reset()
    # first mid-band ratio LEARNS the signature (sqlmap kb.matchRatio)
    v1 = wm.calibrated_verdict("ep3", "aaaa bbbb cccc", "aaaa bbbb dddd")
    assert v1 in ("same", "differs")     # learns, no crash
    # same-shape junk later (same ratio) → SAME (matches signature)
    v2 = wm.calibrated_verdict("ep3", "aaaa bbbb cccc", "aaaa bbbb eeee")
    assert v2 == v1


# ── 1.3 cascade floors ───────────────────────────────────────────────

def test_w11_noise_floor_from_identical_scalars():
    wm.reset()
    samples = [{"size": 512, "words": 20, "lines": 3, "status": 200},
               {"size": 512, "words": 20, "lines": 3, "status": 200},
               {"size": 512, "words": 20, "lines": 3, "status": 200}]
    floor = wm.noise_floor("h.example", samples)
    assert floor and floor["size"] == 512 and floor["words"] == 20
    # a floor-matching response is noise
    assert wm.is_noise("h.example", size=512, words=20, lines=3, status=200)
    # any scalar off the floor → NOT noise (a real find)
    assert not wm.is_noise("h.example", size=2048, words=20, lines=3, status=200)


def test_w12_no_floor_without_consensus():
    wm.reset()
    samples = [{"size": 512}, {"size": 512}, {"size": 900}]
    assert wm.noise_floor("h2.example", samples) is None
    assert wm.noise_floor("h3.example", [{"size": 1}]) is None  # < min


def test_w13_string_samples_derive_scalars():
    wm.reset()
    body = "same wildcard response body here"
    floor = wm.noise_floor("h4.example", [body, body, body])
    assert floor and floor["size"] == len(body)
    assert floor["words"] == len(body.split())


# ── 1.5 TTL ──────────────────────────────────────────────────────────

def test_w14_ttl_expiry_reaps():
    wm.reset()
    wm.noise_floor("ttl.example",
                   [{"size": 9, "words": 9, "lines": 9}] * 3)
    assert wm.is_noise("ttl.example", size=9, words=9, lines=9)
    # force-expire the entry
    with wm._LOCK:
        wm._STORE["floor"]["ttl.example"]["ts"] = time.time() - 7200
    # expired → returns None → not noise anymore (re-verify first)
    assert not wm.is_noise("ttl.example", size=9, words=9, lines=9)
    # store bounded
    for i in range(wm._MAX_PER_KIND + 100):
        wm._put("floor", f"h{i}", {"size": i})
    assert len(wm._STORE["floor"]) <= wm._MAX_PER_KIND
    wm.reset()


def test_w15_garbage_never_raises():
    wm.reset()
    wm.parse_prediction(None)
    wm.parse_prediction({"predict": None})
    wm.measure("t", None, None, None)
    wm.measure("t", {}, {"expected_status": 200}, None)
    wm.learn_markings("", "", "")
    wm.noise_floor("x", None)
    wm.noise_floor("x", [1, 2, 3])
    wm.is_noise("", size=None)
    wm.prediction_note(None)
    wm.surprise_digest()
    wm.calibrated_verdict("", None, None)


# ── end-to-end through the registry choke point ───────────────────────

def test_w16_registry_prediction_flow():
    wm.reset()
    import tools as T
    # predict rides the call, is extracted before the tool sees it, and
    # the note lands in the output — verified via a real safe tool.
    out = T.execute("crypto_hash", {"op": "md5", "data": "abc",
                                    "predict": {"expect_contains": "900150"}},
                    on_event=None)
    assert "TOOL ERROR" not in out
    assert "md5" in out.lower()
    # the prediction was satisfied → the note rode the output
    assert "0 surprise" in out or "PREDICT" in out
    wm.reset()
