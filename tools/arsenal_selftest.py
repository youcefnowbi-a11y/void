"""TOOL: arsenal_selftest — the agent's boot-time weapon check.

ROUND 0 protocol: before any mission action, the agent runs this once to load
a COMPLETE map of her arsenal (every tool, its parameters, its usage recipe)
and to LIVE-TEST every tool that can be safely tested locally (native cores,
workspace, reports, skills, public intel APIs). She never discovers her own
arsenal mid-mission again, and never burns rounds re-reading schemas.

Two modes:
  catalog    — instant. Full weapon map from the registry schemas. No execution.
  live_local — catalog + real execution of every locally-testable tool against
               auto-generated fixtures (tmp files, scratch workspace, public
               read-only intel APIs). Targets are NEVER touched.
"""
import json, os, time, tempfile, traceback
from tools import register, all_tools, discover

# tools that must NOT be executed in a selftest (stateful / destructive / need
# a confirmed live primitive) — they are catalog-verified only
_NO_LIVE = {
    "shell_exec", "shell_session", "upload_webshell", "c2_pulse",
    "h2_race_attack", "binary_fuzz_run",          # native strikes — needs live target
    "race_smash", "smuggle_probe", "ssti_detect_rce", "lfi_file_read",
    "sqli_union_dump", "sqli_blind_extract", "ssrf_probe", "proto_pollute",
    "redirect_cast", "idor_enum", "idor_b64_walk", "fuzz_attack_surface",
    "cmd_exec_probe", "nuclei_scan", "xxe_probe", "upload_webshell",
    "jwt_forge_replay", "auth_state_audit", "nday_exploit",
    "sqli_probe_param", "param_brute", "otp_brute", "auth_metadata_poison",
    "auth_signup_probe", "supabase_exfil", "supabase_full_assault",
    "realtime_tap", "replay_mutate", "spa_crawl", "deploy_watch",
    "dir_brute", "subdomain_enum", "wayback_urls", "js_mine_site",
    "js_mine_url", "deobfuscate_js", "vm_string_dump", "graphql_introspect",
}
# tools tested live against PUBLIC READ-ONLY intel APIs (no target contact)
_PUBLIC_SAFE = {"cisa_kev", "nvd_search", "ip_intel"}
# locally testable — fixtures generated on the fly
_LOCAL_TESTS = {
    "workspace_status": {},
    "skill_list": {},
    "report_write": {"title": "_selftest", "content": "arsenal selftest marker"},
    "file_grep": {},   # args synthesized at runtime (fixture file)
    "secret_scan": {}, # args synthesized at runtime (fixture file)
    "har_dissect": {}, # args synthesized at runtime (fixture HAR)
    "har_tokens": {},  # args synthesized at runtime (fixture HAR)
    "jwt_analyst": {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                             "eyJzdWIiOiJzZWxmdGVzdCIsImV4cCI6OTk5OTk5OTk5OX0."
                             "sig"},
    "crash_triage_rank": {},    # args synthesized at runtime (fixture crashes)
    "crash_triage_next": {},    # args synthesized at runtime (fixture crashes)
    "waf_detect": {"url": "https://example.com"},
    "web_fingerprint": {"url": "https://example.com"},
    "tg_probe": {"handles": ["durov"]},
}
_FAST_PUBLIC = {"cisa_kev": {"keyword": "edge"},
                "nvd_search": {"keyword": "nginx", "results": 3},
                "ip_intel": {"ip_or_host": "1.1.1.1"}}


def _schema_recipe(t):
    """Human-compact usage recipe from a tool's JSON schema."""
    p = t.get("params", {}) or {}
    props = p.get("properties", {}) or {}
    req = set(p.get("required", []) or [])
    parts = []
    for k, v in list(props.items())[:8]:
        typ = v.get("type", "any")
        mark = "*" if k in req else ""
        d = (v.get("description") or "").split(". ")[0][:80]
        parts.append(f"{k}{mark}({typ}): {d}")
    return parts


def _shape_of(out_str, limit=260):
    """Compact structural preview of a tool result — keys, types, sizes."""
    if not isinstance(out_str, str):
        out_str = str(out_str)
    try:
        d = json.loads(out_str)
    except Exception:
        return out_str[:limit]
    def shape(o, depth=0):
        if isinstance(o, dict):
            return {k: shape(v, depth + 1) for k, v in list(o.items())[:12]} \
                if depth < 2 else f"dict[{len(o)}]"
        if isinstance(o, list):
            return [shape(o[0], depth + 1), f"…{len(o)} items"] if o else []
        if isinstance(o, str):
            return f"str[{len(o)}]: {o[:60]}" if len(o) > 60 else o
        return o
    s = json.dumps(shape(d), ensure_ascii=False)
    return s[:limit] + ("…" if len(s) > limit else "")


@register(name="arsenal_selftest",
          desc="ROUND 0 BOOT PROTOCOL — run ONCE at mission start. Loads the "
               "complete weapon map: every tool, every parameter, every usage "
               "recipe, plus live local tests of everything testable without a "
               "target. mode='catalog' is instant; mode='live_local' also "
               "executes safe local fixtures (~30-90s). Know your arsenal "
               "BEFORE the first strike.",
          params={"type": "object", "properties": {
              "mode": {"type": "string",
                       "description": "'catalog' (instant map, default) or "
                                      "'live_local' (catalog + local live tests)"}},
              "required": []})
def arsenal_selftest(mode="catalog"):
    # R3-9: un mode inconnu ne doit pas dégrader silencieusement au catalogue
    if mode not in ("catalog", "live_local"):
        return "TOOL ERROR [ARGS]: mode must be 'catalog' or 'live_local'"
    discover()
    tools = all_tools()
    by_name = {t["name"]: t for t in tools}
    t0 = time.time()
    tested, passed, failed = [], [], []

    # ── fixture workspace ────────────────────────────────────────────
    fx_dir = os.path.join("missions", "_arsenal_selftest")
    os.makedirs(fx_dir, exist_ok=True)
    fx_crash = os.path.join(fx_dir, "crash_asan.txt")
    with open(fx_crash, "w", encoding="utf-8") as f:
        f.write("==ERROR: AddressSanitizer: SEGV on unknown address 0x41414141\n"
                "WRITE of size 4\n"
                "    #0 0x40a1f2 in parse_header parser.c:88\n"
                "    #1 0x40b3aa in handle_req server.c:201\n")
    fx_har = os.path.join(fx_dir, "fixture.har")
    with open(fx_har, "w", encoding="utf-8") as f:
        f.write(json.dumps({"log": {"entries": [{"request": {
            "url": "https://selftest.local/api", "method": "GET",
            "headers": [{"name": "Authorization",
                         "value": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhIjoxfQ.s"}]},
            "response": {"status": 200, "content": {"size": 2, "text": "{}"}}}]}}))
    fx_py = os.path.join(fx_dir, "fixture_code.py")
    with open(fx_py, "w", encoding="utf-8") as f:
        f.write("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\napi_secret = 'deadbeef'*4\n")
    fx_txt = os.path.join(fx_dir, "fixture.txt")
    with open(fx_txt, "w", encoding="utf-8") as f:
        f.write("hello selftest needle_in_haystack_7f3a\n")
    fx_find = os.path.join(fx_dir, "fuzz_findings.json")
    with open(fx_find, "w", encoding="utf-8") as f:
        json.dump([
            {"url_path": "/api/selftest", "param": "q", "payload": "' OR 1=1--",
             "severity": 0.9, "signals": ["sqli", "sql_error"]},
            {"url_path": "/api/selftest", "param": "q", "payload": "' OR '1'='1",
             "severity": 0.85, "signals": ["sqli"]},
        ], f)

    _LOCAL_TESTS["file_grep"] = {"path": fx_txt, "pattern": "needle_\\w+_\\w+"}
    _LOCAL_TESTS["secret_scan"] = {"path": fx_dir}
    _LOCAL_TESTS["har_dissect"] = {"har_path": fx_har}
    _LOCAL_TESTS["har_tokens"] = {"har_path": fx_har}
    _LOCAL_TESTS["crash_triage_rank"] = {"crash_dir": fx_dir}
    _LOCAL_TESTS["crash_triage_next"] = {"path": fx_find}

    # ── live local / public tests ────────────────────────────────────
    live_enabled = (mode == "live_local")
    live_results = {}
    if live_enabled:
        from tools import execute as reg_execute
        plan = {}
        for name in by_name:
            if name == "arsenal_selftest":
                continue
            if name in _LOCAL_TESTS:
                plan[name] = _LOCAL_TESTS[name]
            elif name in _PUBLIC_SAFE:
                plan[name] = _FAST_PUBLIC[name]
        for name, args in plan.items():
            tstart = time.time()
            try:
                out = reg_execute(name, args)
                err = isinstance(out, str) and out.startswith("TOOL ERROR")
                entry = {"ok": not err, "dur_s": round(time.time() - tstart, 2),
                         "args": args, "shape": _shape_of(out)}
                live_results[name] = entry
                (passed if not err else failed).append(name)
            except Exception as e:
                live_results[name] = {"ok": False, "dur_s": round(time.time() - tstart, 2),
                                      "args": args, "error": f"{type(e).__name__}: {e}"[:200]}
                failed.append(name)
            tested.append(name)

    # ── the weapon map ───────────────────────────────────────────────
    catalog = {}
    for t in sorted(tools, key=lambda x: x["name"]):
        n = t["name"]
        entry = {"danger": t.get("danger", "safe"),
                 "desc": (t.get("desc", "") or "").split(". ")[0][:130],
                 "params": _schema_recipe(t)}
        if n in _NO_LIVE:
            entry["note"] = "targeted tool — needs live recon data first"
        elif n in _LOCAL_TESTS or n in _PUBLIC_SAFE:
            entry["note"] = "self-tested locally" if live_enabled else \
                            "testable via arsenal_selftest(mode='live_local')"
        catalog[n] = entry

    out = {
        "mode": mode,
        "tools_total": len(tools),
        "live_tested": len(tested) if live_enabled else 0,
        "live_passed": len(passed),
        "live_failed": failed,
        "duration_s": round(time.time() - t0, 2),
        "live_results": live_results,
        "arsenal_map": catalog,
        "next": "Tu vois maintenant chaque arme, ses paramètres et sa recette. "
                "Les notes 'targeted tool' demandent du recon VIVANT d'abord. "
                "Retrouve cette carte à tout moment via ce même tool.",
    }
    # archive the map so file_grep / report flow can cite it
    try:
        with open(os.path.join(fx_dir, "arsenal_map.json"), "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return json.dumps(out, ensure_ascii=False, indent=1)
