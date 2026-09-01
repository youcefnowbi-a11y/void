"""VOIDFORGE :: Monster build test battery — blackboard, transport, protocols,
replay, jwt_analyst, batch, dir_brute, js_mine v2, playbooks.
Requires ForgeRange running on 127.0.0.1:8765 (lab/forge_range.py).
Run: python tests/test_monster.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

B = "http://127.0.0.1:8765"
PASS = 0


def ok(name, cond, detail=""):
    global PASS
    assert cond, f"FAIL {name} {detail}"
    PASS += 1
    print(f"  OK {name} {detail}")


def main():
    from core.protocols import seroval_encode, seroval_decode, tanstack_fn_call
    from tools._transport import fetch
    from core.blackboard import Blackboard, set_active
    from core import playbooks

    # ── Blackboard ────────────────────────────────────────────
    INTEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "intel")
    for suffix in (".json", ".events.jsonl"):
        try:
            os.remove(os.path.join(INTEL, f"forge-range.test{suffix}"))
        except OSError:
            pass
    bb = Blackboard("forge-range.test")
    set_active(bb)
    bb.add_asset("endpoint", B + "/api/orders", source_tool="test")
    bb.add_asset("key", "eyJhbGciOiJIUzI1NiJ9.x.y", props={"kind_of_key": "anon_key"}, source_tool="test")
    ok("blackboard assets", len(bb.assets) == 2, str(bb.stats()))
    ok("blackboard connections", len(bb.unmade_connections(3)) >= 1)
    bb.mark_tested("endpoint:" + B + "/api/orders", "data_extract", "403")
    cov = bb.coverage()
    ok("blackboard coverage", cov["endpoint"]["tested"] == 1)

    # ── Transport ─────────────────────────────────────────────
    r1 = fetch(B + "/products")
    r2 = fetch(B + "/products")
    ok("transport cache", r2.get("cache_hit") is True and r1["status"] == 200)
    rr = fetch(B + "/start")
    ok("transport 307 chain", rr["status"] == 200 and rr.get("redirect_chain") is not None)

    # ── Protocols ─────────────────────────────────────────────
    v = {"cat": "all", "nums": [1, 2.5, None, True], "n": {"a": "x"}}
    ok("seroval round-trip", seroval_decode(seroval_encode(v)) == v)
    r = tanstack_fn_call(B, "20b34aaaa7e9a6d097543e", {"cat": "all"})
    ok("serverFn products decoded", r["status"] == 200 and len((r["parsed"] or {}).get("items", [])) == 5)
    r = tanstack_fn_call(B, "9a85874eff31c2bd0045a1", {"slug": "forge-admin"})
    ok("serverFn admin_gate via wire", (r["parsed"] or {}).get("ok") is True)

    # ── Tools (spa_crawl v2, replay, jwt, batch, dir_brute, js_mine v2) ──
    import tools
    out = tools.execute("spa_crawl", {"url": B, "wait_s": 2})
    d = json.loads(out)
    ok("spa_crawl v2 captures app requests", len(d["captured_requests"]) >= 2,
       f'{len(d["captured_requests"])}')
    ok("spa_crawl v2 storage", any("forge_token" in (v.get("local") or "") for v in d["storage"].values()))
    cap = d["capture_file"]

    rm = json.loads(tools.execute("replay_mutate", {
        "capture_file": cap, "url_filter": "_serverFn",
        "body_patch": {"data.slug": "forge-admin"}}))
    hit = [x for x in rm["results"] if "9a85874e" in x["original"]["url"]]
    ok("replay unlocks admin via app-oracle", bool(hit) and hit[0]["replayed"]["status"] == 200)

    hm = fetch(B + "/assets/chunk-Tracker-EF56GH78.js")
    tok = [w for w in hm["body"].split('"') if w.startswith("eyJ")][0]
    ja = json.loads(tools.execute("jwt_analyst", {"token": tok}))
    ok("jwt_analyst decodes + flags", ja["tokens"] == 1 and
       any("role" in f for f in ja["analysis"][0]["flags"]))

    bt = json.loads(tools.execute("batch_execute", {"calls": [
        {"tool": "web_fingerprint", "args": {"url": B}},
        {"tool": "waf_detect", "args": {"url": B}}]}))
    ok("batch concurrent", bt["executed"] == 2 and all(x["ok"] for x in bt["results"]))

    db = json.loads(tools.execute("dir_brute", {"base": B}))
    paths = [h["path"] for h in db["hits"]]
    ok("dir_brute python prober", "orders" in paths and ".well-known/security.txt" in paths, str(paths))

    jm = json.loads(tools.execute("js_mine_url", {"url": B + "/assets/index-ForgeLab.js"}))
    ok("js_mine v2 source map", "source_map" in jm and "ADMIN_SLUG" in str(jm.get("source_map")))
    ok("js_mine v2 chunk graph", any("chunk-Admin" in c for c in jm.get("chunks_discovered", [])))

    # ── Passive intel through transport ───────────────────────
    ok("blackboard grew passively", len(bb.assets) > 2, f'{len(bb.assets)} assets total')

    # ── Playbooks ─────────────────────────────────────────────
    pb = playbooks.learn("test mission on forge range shop",
                         {"recon": [("tool", "spa_crawl: ok"), ("tool", "js_mine_url: ok"),
                                    ("tool", "data_extract: ok")]}, bb)
    ok("playbook learned", pb is not None and len(pb["sequence"]) == 3)
    block = playbooks.prompt_block("attack the forge range spa with supabase backend")
    ok("playbook injected", "PLAYBOOKS" in block and "spa_crawl" in block)

    # ── Report v2 with board ──────────────────────────────────
    from core.report import write_report
    rp = write_report("monster test mission",
                      [("tool", "spa_crawl: ok"), ("agent", "done")],
                      os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports"),
                      board=bb)
    content = open(rp, encoding="utf-8").read()
    ok("report v2 living-graph section", "LIVING GRAPH" in content and "Unmade connections" in content)

    print(f"\n★ {PASS}/19 monster build checks green")


if __name__ == "__main__":
    main()
