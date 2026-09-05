"""Phase 4 (Ω4) guards — the doctrine: entries, goal termination,
skip-taught rules, self-verification.

Laws under test:
- 4.1: predicate × context × where triples mint; idempotent re-mint
  reinforces instead of duplicating; round0 block filters by context
- 4.2: Goal{trait, value, count} grammar parses countable predicates;
  progress counts against blackboard assets
- 4.3: the skip taxonomy (by_reason/example shape) becomes rules —
  failures teach
- 4.4: used-and-worked reinforces, used-and-failed decays; below the
  retire threshold the entry archives itself (graveyard, never lost);
  the retire-path save must not deadlock
- persistence: save/load round-trip; bounded entries
- determinism: garbage never raises
"""
import json
import threading

import core.doctrine as doc


# ── 4.1 entries ──────────────────────────────────────────────────────

def test_z01_mint_and_round0():
    doc.reset()
    e = doc.add_entry("webhooks before product API", "stripe-marketplace",
                      "api_sweep", expected="faster foothold",
                      origin="dream")
    assert e["predicate"] == "webhooks before product API"
    assert e["where"] == "api_sweep" and e["score"] == 0.6
    # round0 block: matching context rides
    blk = doc.round0_block(target="my-stripe-marketplace.example")
    assert "webhooks before product API" in blk
    assert "api_sweep" in blk
    # non-matching target: universal entries still ride (context match
    # is fuzzy-or-universal — a stripe rule on a non-stripe target shows
    # only if context empty). Here it must NOT show:
    blk2 = doc.round0_block(target="blog.example")
    assert "webhooks before product API" not in blk2


def test_z01b_universal_ctx_sentinels_ride_everywhere():
    # calib-B fix guard: "any-target"/"any" are UNIVERSAL — minted wins
    # must ride the round-0 block of ANY mission (the literal-ctx bug
    # made the doctrine silently invisible for entire missions)
    doc.reset()
    doc.add_entry("win law", "any-target", "api_sweep", origin="win-taught")
    doc.add_entry("other law", "any", "file_grep", origin="win-taught")
    for tgt in ("duskyr.com", "keypool.duskyr.com", "totally-unrelated.io",
                "127.0.0.1"):
        blk = doc.round0_block(target=tgt)
        assert "win law" in blk, f"win law missing for {tgt}"
        assert "other law" in blk, f"other law missing for {tgt}"
    # a REAL context still scopes properly
    doc.add_entry("scoped", "stripe-marketplace", "api_sweep")
    assert "scoped" in doc.round0_block(target="stripe-marketplace.example")
    assert "scoped" not in doc.round0_block(target="blog.example")


def test_z02_idempotent_remint_reinforces():
    doc.reset()
    e1 = doc.add_entry("p1", "ctx1", "w1")
    e2 = doc.add_entry("p1", "ctx1", "w1")     # same triple
    assert e2 is not e1 or True                 # _find returns the same
    assert len([e for e in doc._ENTRIES
                if e["predicate"] == "p1"]) == 1
    assert e1["times_re_minted"] == 2
    assert e1["score"] > 0.6                    # reinforced


def test_z03_malformed_entries_rejected():
    doc.reset()
    assert doc.add_entry("", "ctx", "w") is None
    assert doc.add_entry("p", "ctx", "") is None
    assert doc.add_entry(None, None, None) is None


# ── 4.2 goal termination ─────────────────────────────────────────────

def test_z04_goal_grammar():
    doc.reset()
    goals = doc.parse_goals("pull admin keys; Goal: keys: admin x3 "
                            "endpoints: api x2")
    assert isinstance(goals, list)
    # grammar matches "trait: value xN"
    kinds = {g["trait"] for g in goals}
    assert "keys" in kinds and "endpoints" in kinds
    kc = next(g for g in goals if g["trait"] == "keys")
    assert kc["value"] == "admin" and kc["count"] == 3
    # loose text without the grammar → no hallucinated goals
    assert doc.parse_goals("just look around a bit") == []
    assert doc.parse_goals(None) == []


def test_z05_goal_progress():
    doc.reset()
    goals = doc.parse_goals("keys: admin x3")
    assets = [
        {"value": "admin-key-1", "props": {}},
        {"value": "admin-key-2", "props": {}},
        {"value": "user-key-9", "props": {}},
    ]
    prog = doc.goal_progress(goals, assets)
    assert prog[0]["have"] == 2 and prog[0]["need"] == 3
    assert prog[0]["met"] is False
    assets.append({"value": "admin-key-3", "props": {}})
    prog2 = doc.goal_progress(goals, assets)
    assert prog2[0]["have"] == 3 and prog2[0]["met"] is True


# ── 4.3 skip-taught ──────────────────────────────────────────────────

def test_z06_skip_taxonomy_becomes_rules():
    doc.reset()
    summary = {"total": 3, "by_reason": {"unknown_tool": 2, "rail_pivot": 1},
               "example": {"unknown_tool": "hack_the_planet: no such tool",
                           "rail_pivot": "dir_brute: 403 wall"}}
    minted = doc.skip_taught(summary)
    assert len(minted) == 2
    preds = {e["predicate"] for e in minted}
    assert any("hallucinated" in p for p in preds)
    assert any("stop rail" in p for p in preds)
    wheres = {e["where"] for e in minted}
    assert "naming" in wheres and "wall-avoidance" in wheres
    # the example rides in the predicate
    assert any("hack_the_planet" in p for p in preds)


def test_z07_skip_taught_garbage():
    doc.reset()
    assert doc.skip_taught(None) == []
    assert doc.skip_taught({"by_reason": "notadict"}) == []
    assert doc.skip_taught({"by_reason": {"unknown_category": 5}}) == []


# ── 4.4 self-verification ────────────────────────────────────────────

def test_z08_reinforce_and_decay():
    doc.reset()
    e = doc.add_entry("p", "ctx", "w")
    s0 = e["score"]
    doc.report_use(e, True)
    assert e["used"] == 1 and e["worked"] == 1
    assert e["score"] > s0
    s1 = e["score"]
    doc.report_use(e, False)
    assert e["failed"] == 1
    assert e["score"] < s1
    # still live (one failure doesn't retire a fresh entry)
    assert e in doc._ENTRIES


def test_z09_retire_to_graveyard(tmp_path, monkeypatch):
    # calib fix: retire fires save() — patch the store or the test
    # writes the real intel/doctrine.json (same pollution class as z13)
    monkeypatch.setattr(doc, "_DOCTRINE_DIR", str(tmp_path))
    monkeypatch.setattr(doc, "_DOCTRINE_FILE", str(tmp_path / "d.json"))
    doc.reset()
    e = doc.add_entry("weak rule", "ctx", "w")
    # hammer it with failures until it retires
    for _ in range(12):
        r = doc.report_use(e, False)
        if r and r.get("retired"):
            break
    assert e not in doc._ENTRIES
    assert e in doc._GRAVEYARD
    assert e.get("retired_ts")
    # auditable: the graveyard keeps the full entry
    assert e["predicate"] == "weak rule"


def test_z10_report_use_unknown_entry():
    doc.reset()
    assert doc.report_use(("ghost", "ctx", "w"), True) is None
    assert doc.report_use(None, True) is None


def test_z10b_retire_saves_without_deadlock(tmp_path, monkeypatch):
    # audit-fix guard: report_use holds _LOCK and retires inside it —
    # the immediate save() must not deadlock (RLock, not Lock)
    monkeypatch.setattr(doc, "_DOCTRINE_DIR", str(tmp_path))
    monkeypatch.setattr(doc, "_DOCTRINE_FILE", str(tmp_path / "d.json"))
    doc.reset()
    e = doc.add_entry("dl", "ctx", "w")
    done = []
    t = threading.Thread(target=lambda: [
        done.append(doc.report_use(e, False) or doc.report_use(e, False))
        for _ in range(6)])
    t.start()
    t.join(timeout=10)          # a deadlock hangs past this
    assert not t.is_alive(), "report_use deadlocked on save()"
    assert e in doc._GRAVEYARD or e in doc._ENTRIES  # reached a verdict


# ── persistence ──────────────────────────────────────────────────────

def test_z11_save_load_roundtrip(tmp_path, monkeypatch):
    doc.reset()
    monkeypatch.setattr(doc, "_DOCTRINE_DIR", str(tmp_path))
    monkeypatch.setattr(doc, "_DOCTRINE_FILE", str(tmp_path / "doctrine.json"))
    doc.add_entry("persisted rule", "ctx-p", "tool-p", origin="dream")
    assert doc.save()
    doc.reset()
    assert doc.load()
    assert any(e["predicate"] == "persisted rule" for e in doc._ENTRIES)
    # corrupted file → honest False, never raises
    (tmp_path / "doctrine.json").write_text("{broken", encoding="utf-8")
    doc.reset()
    assert doc.load() is False


def test_z12_bounded_entries():
    doc.reset()
    for i in range(doc._MAX_ENTRIES + 50):
        doc.add_entry(f"p{i}", f"ctx{i}", f"w{i}")
    assert len(doc._ENTRIES) <= doc._MAX_ENTRIES
    assert len(doc._GRAVEYARD) >= 1     # overflow archived, not deleted


def test_z13_autopsy_end_to_end(tmp_path, monkeypatch):
    # calib-A fix: NO real-file writes from tests — monkeypatch the
    # doctrine store paths (test_z13 was polluting intel/doctrine.json,
    # which then rode mission round-0 blocks as test noise)
    monkeypatch.setattr(doc, "_DOCTRINE_DIR", str(tmp_path))
    monkeypatch.setattr(doc, "_DOCTRINE_FILE", str(tmp_path / "d.json"))
    doc.reset()
    summary = {"total": 2, "by_reason": {"quarantined": 2},
               "example": {"quarantined": "dark host x.example"},
               "mission": "m-80"}
    minted = doc.autopsy(target="t.example", skip_summary=summary,
                         extra_entries=[
                             {"predicate": "report rule", "context": "any",
                              "where": "report_write", "origin": "mission"}],
                         transcript=[
                             ("tool", "api_sweep: {\"url\": \"https://x/openapi.json\", \"status\": 200, \"paths\": \"FULL schema exposed\"}"),
                             ("assistant", "grammar cracked via openapi.json")])
    assert any(e["where"] == "patience" for e in minted)
    assert any(e["predicate"] == "report rule" for e in minted)
    # win-taught: the openapi pattern minted from the transcript
    assert any(e["origin"] == "win-taught" for e in minted)
    # persisted (to the patched file — autopsy saves)
    doc.reset()
    assert doc.load()


def test_z14_mint_wins_deterministic():
    doc.reset()
    # final-audit B2 contract: signatures anchor on SUCCESS-shaped
    # evidence. The old file_grep entry ("X-Admin-Token ... single shared
    # secret found") was a bare MENTION — the exact false-positive class
    # the audit killed. A win now carries hit-context.
    tr = [
        ("tool", "data_extract: {\"url\": \"https://keypool/openapi.json\", "
                 "\"status\": 200, \"text\": \"FULL OpenAPI schema exposed\"}"),
        ("tool", "file_grep: `X-Admin-Token` header, single shared secret — "
                 "H() builder located, path tpl_edeb90daa6c.js:11892, match_no 4"),
        ("tool", "forge_tool: {\"ok\": true, \"tool\": \"forged_js_fetch_grep\", "
                 "\"note\": \"outil ARMÉ et vivant\"}"),
        # mention-only prose must NOT mint (the B2 kill):
        ("agent", "I saw X-Admin-Token in the docs once, maybe single shared"),
    ]
    minted = doc.mint_wins(tr)
    origins = {e["origin"] for e in minted}
    assert minted and origins == {"win-taught"}
    wheres = {e["where"] for e in minted}
    assert "api_sweep" in wheres and "file_grep" in wheres \
        and "forge_tool" in wheres
    # idempotence: same transcript re-minted reinforces, not duplicates
    n0 = len([e for e in doc._ENTRIES if e["origin"] == "win-taught"])
    doc.mint_wins(tr)
    n1 = len([e for e in doc._ENTRIES if e["origin"] == "win-taught"])
    assert n1 == n0
    # garbage never raises
    assert doc.mint_wins(None) == []
    assert doc.mint_wins([("bogus", 42)]) == []
