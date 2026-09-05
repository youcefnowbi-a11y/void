"""Phase 3 (Ω3) guards — the dream: provenance, replay lane, fixpoint,
dream→doctrine feed.

Laws under test:
- 3.1 provenance: facts carry mission/target/step; archived stamps are
  NEVER overwritten (re-stamping would lie about birth)
- 3.2 replay lane: untaken branches = archived assets no consumer tool
  ever saw; simulation is honest (no archived evidence → no play);
  would-have-worked branches mint plays
- 3.3 fixpoint: bounded passes, saturation breaks, compounding plays
  (simulated secret_scan implies data_extract)
- 3.4 doctrine feed: plays mint predicate × context × where entries
- determinism: no live traffic anywhere; garbage never raises
"""
import json
import os
import time

import core.dream as dr


def _stamp(bb_fact):
    return dr.stamp_fact(bb_fact)


# ── 3.1 provenance ───────────────────────────────────────────────────

def test_d01_bind_and_stamp():
    dr.reset()
    dr.bind_mission("m-42", "target.example")
    dr.step_bump()
    dr.step_bump()
    f = {"seq": 1, "op": "asset", "kind": "endpoint"}
    _stamp(f)
    assert f["prov"]["mission_id"] == "m-42"
    assert f["prov"]["target"] == "target.example"
    assert f["prov"]["step"] == 2
    # archived stamp wins — NEVER overwritten
    f2 = {"seq": 2, "prov": {"mission_id": "m-OLD", "step": 99}}
    _stamp(f2)
    assert f2["prov"]["mission_id"] == "m-OLD" and f2["prov"]["step"] == 99


def test_d02_provenance_garbage():
    dr.reset()
    assert dr.stamp_fact(None) is None
    assert dr.stamp_fact("string") == "string"
    # stamp_fact({}) ADDS a prov key — a fact dict with no origin gets
    # stamped with the live context; assert the stamped shape:
    f = dr.stamp_fact({})
    assert f == {"prov": dr.provenance()}
    dr.bind_mission(None, None)
    p = dr.provenance()
    assert p["mission_id"] is None


# ── 3.2 replay lane (against a real archived blackboard file) ────────

def _write_bb(tmp_path, assets):
    d = tmp_path / "intel"
    d.mkdir(exist_ok=True)
    bb = {"target": "dream.example", "assets": assets}
    (d / "dream.example.json").write_text(json.dumps(bb), encoding="utf-8")
    return d


def test_d03_untaken_branches(monkeypatch, tmp_path):
    dr.reset()
    _d = _write_bb(tmp_path, {
        "key:sk_live_abc": {"kind": "key", "value": "sk_live_abc",
                            "confidence": 0.85, "props": {"kind_of_key": "api_key"}},
        "endpoint:https://dream.example/api": {"kind": "endpoint",
                                               "value": "https://dream.example/api",
                                               "confidence": 0.8, "props": {}},
    })
    # point the dream's intel dir at the tmp
    monkeypatch.setattr(dr, "_INTEL", str(_d))
    # no trajectory → no tool ever ran → all branches untaken
    monkeypatch.setattr(dr, "_TRAJ", str(tmp_path / "nope"))
    brs = dr.untaken_branches("dream.example",
                              {"secret_scan", "jwt_analyst", "data_extract",
                               "endpoint_oracle", "api_sweep"})
    kinds = {b["asset_key"] for b in brs}
    assert "key:sk_live_abc" in kinds          # never consumed
    assert "endpoint:https://dream.example/api" in kinds
    # sorted by confidence desc
    assert brs[0]["confidence"] >= brs[-1]["confidence"]


def test_d04_taken_branches_excluded(monkeypatch, tmp_path):
    dr.reset()
    _d = _write_bb(tmp_path, {
        "key:sk_live_abc": {"kind": "key", "value": "sk_live_abc",
                            "confidence": 0.85, "props": {"kind_of_key": "api_key"}},
    })
    monkeypatch.setattr(dr, "_INTEL", str(_d))
    # trajectory shows secret_scan DID see this key
    td = tmp_path / "missions" / "_trajectories"
    td.mkdir(parents=True)
    (td / "trajectories.jsonl").write_text(
        json.dumps({"tool": "secret_scan", "ok": True,
                    "args": "path=sk_live_abc"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(dr, "_TRAJ", str(td))
    brs = dr.untaken_branches("dream.example", {"secret_scan"})
    assert not any(b["asset_key"] == "key:sk_live_abc" and b["tool"] == "secret_scan"
                   for b in brs)
    # other consumers remain untaken
    brs2 = dr.untaken_branches("dream.example", {"secret_scan", "jwt_analyst"})
    assert any(b["tool"] == "jwt_analyst" for b in brs2)


def test_d05_simulate_branch_honesty(monkeypatch, tmp_path):
    dr.reset()
    _d = _write_bb(tmp_path, {
        # corroborated key — the branch would-have-worked
        "key:sk_live_abc": {"kind": "key", "value": "sk_live_abc",
                            "confidence": 0.85,
                            "props": {"kind_of_key": "api_key"}},
        # weak key — no archived evidence: NO play (honesty)
        "key:sk_weak": {"kind": "key", "value": "sk_weak",
                        "confidence": 0.5, "props": {"kind_of_key": "api_key"}},
    })
    monkeypatch.setattr(dr, "_INTEL", str(_d))
    monkeypatch.setattr(dr, "_TRAJ", str(tmp_path / "nope"))
    # fetch full branch WITH props: simulate_branch reads props from the
    # branch — untaken_branches strips them; emulate the real branch shape
    brs = dr.untaken_branches("dream.example", {"secret_scan"})
    for b in brs:
        b["props"] = {"kind_of_key": "api_key"}
    plays = [p for p in (dr.simulate_branch(b) for b in brs) if p]
    strong = [p for p in plays
              if "sk_live_abc" in p["action"]["on"]]
    weak = [p for p in plays if "sk_weak" in p["action"]["on"]]
    assert strong, "corroborated asset must mint a play"
    assert not weak, "weak asset must NOT mint (no archived evidence)"


def test_d06_dream_run_end_to_end(monkeypatch, tmp_path):
    dr.reset()
    _d = _write_bb(tmp_path, {
        "key:sk_live_abc": {"kind": "key", "value": "sk_live_abc",
                            "confidence": 0.85,
                            "props": {"kind_of_key": "api_key"}},
        "endpoint:https://dream.example/api": {"kind": "endpoint",
                                               "value": "https://dream.example/api",
                                               "confidence": 0.8, "props": {}},
    })
    monkeypatch.setattr(dr, "_INTEL", str(_d))
    monkeypatch.setattr(dr, "_TRAJ", str(tmp_path / "nope"))
    # plays file lives in the tmp intel dir
    report = dr.dream("dream.example")
    assert report["target"] == "dream.example"
    assert report["plays"], "archived corroborated assets must yield plays"
    # persisted
    saved = dr.load_plays(limit=64)
    assert saved and any("sk_live_abc" in str(p.get("action", {}).get("on", ""))
                         for p in saved)
    # compounding: simulated secret_scan implies a data_extract play
    tools_in_plays = {p.get("action", {}).get("tool") for p in saved}
    assert "data_extract" in tools_in_plays


def test_d07_dream_missing_archive_safe(monkeypatch, tmp_path):
    dr.reset()
    monkeypatch.setattr(dr, "_INTEL", str(tmp_path / "empty"))
    report = dr.dream("ghost.example")
    assert report["plays"] == []


# ── 3.4 doctrine feed ────────────────────────────────────────────────

def test_d08_mint_doctrine_entry():
    e = dr.mint_doctrine_entry({
        "status": "play",
        "precondition": "asset key with confidence ≥ 0.8",
        "action": {"tool": "secret_scan", "on": "sk_live_abc"},
        "expected": "escalate",
        "evidence": {"confidence": 0.85}})
    assert e["origin"] == "dream" and e["where"] == "secret_scan"
    assert "predicate" in e and "context" in e
    # malformed plays → None
    assert dr.mint_doctrine_entry(None) is None
    assert dr.mint_doctrine_entry({"status": "wip"}) is None


def test_d08b_play_target_filtering(monkeypatch, tmp_path):
    # audit fix guard: plays minted for target A must NOT feed target B's
    # round-0 brief — cross-target plays poison the mission
    dr.reset()
    # a blackboard for target A (the dream reads A's archive)
    d2 = tmp_path / "bb_a"
    d2.mkdir()
    (d2 / "a.example.json").write_text(json.dumps({
        "target": "a.example",
        "assets": {"key:sk_live_abc": {
            "kind": "key", "value": "sk_live_abc", "confidence": 0.85,
            "props": {"kind_of_key": "api_key"}}}}), encoding="utf-8")
    # plays.json lives in a separate dir (save_plays writes to _INTEL)
    pd = tmp_path / "playsdir"
    pd.mkdir()
    (pd / "plays.json").write_text("[]", encoding="utf-8")
    # point blackboard reads at bb_a, play persistence at playsdir —
    # monkeypatch the play-file resolver, not just _INTEL
    monkeypatch.setattr(dr, "_INTEL", str(pd))
    monkeypatch.setattr(dr, "_play_file", lambda: str(pd / "plays.json"))
    orig_load = dr._load_blackboard
    monkeypatch.setattr(dr, "_load_blackboard",
                        lambda t: json.load(open(d2 / "a.example.json", encoding="utf-8"))
                        if (t or "").strip().lower() == "a.example" else None)
    monkeypatch.setattr(dr, "_TRAJ", str(tmp_path / "nope"))
    dr.dream("a.example")          # mints plays stamped target=a.example
    # target A sees its plays
    pa = dr.load_plays(limit=8, target="a.example")
    assert pa and all(p.get("target") == "a.example" for p in pa)
    # target B sees NOTHING (no cross-target poisoning)
    pb = dr.load_plays(limit=8, target="b.example")
    assert pb == []


# ── tool surface ────────────────────────────────────────────────────

def test_d09_tool_registered_and_safe():
    import tools
    t = [x for x in tools.all_tools() if x["name"] == "dream_rehearsal"]
    assert t and t[0]["danger"] == "safe"


def test_d10_blackboard_stamped(monkeypatch, tmp_path):
    # a fresh blackboard asset carries the dream provenance stamp
    dr.reset()
    dr.bind_mission("m-99", "prov.example")
    dr.step_bump()      # one tool ran BEFORE the fact minted (real order)
    from core.blackboard import Blackboard
    bb = Blackboard("prov.example", fresh=True)
    bb.path = str(tmp_path / "bb.json")
    bb.events_path = str(tmp_path / "bb.events.jsonl")
    bb.add_asset("endpoint", "https://prov.example/x")
    fact = bb.facts[-1]
    assert fact.get("prov", {}).get("mission_id") == "m-99"
    assert fact["prov"]["step"] >= 1
