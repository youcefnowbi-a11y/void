# -*- coding: utf-8 -*-
"""Grimoire integration test: tool registration + all 6 modes live."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.grimoire_query import grimoire_query

print("== 1. registration ==")
from tools import discover, _REGISTRY
discover()
assert "grimoire_query" in _REGISTRY, "grimoire_query not in the fleet registry!"
entry = _REGISTRY["grimoire_query"]
print("   registered in fleet:", entry["name"], "| danger:", entry["danger"])
assert entry["danger"] == "safe"

print("== 2. stats mode ==")
r = json.loads(grimoire_query(mode="stats"))
assert r["library"]["techniques"] == 53, r
assert r["library"]["kev_entries"] == 1695
print("   53 techniques / 1695 KEV /", r["library"]["spine_records"], "spine OK")

print("== 3. kev mode (nginx) ==")
r = json.loads(grimoire_query(mode="kev", keyword="nginx"))
print(f"   nginx KEV hits: {r['hits']}")
for e in r["entries"][:3]:
    print("   -", e[:110])

print("== 4. kev mode ransomware-only wordpress ==")
r = json.loads(grimoire_query(mode="kev", keyword="wordpress", ransomware_only=True))
print(f"   wordpress ransomware-flagged: {r['hits']}")

print("== 5. technique mode (identity domain) ==")
r = json.loads(grimoire_query(mode="technique", domain="identity"))
print(f"   identity techniques: {r['matches']}")
assert r["matches"] > 0
first = r["techniques"][0]
assert "requires_confirmation" in first
print("   sample:", first.split("\n")[0])

print("== 6. technique verbose with detection pair ==")
r = json.loads(grimoire_query(mode="technique", keyword="Kerberoast", verbose=True))
assert r["matches"] >= 1, "kerberoasting not found"
assert "detection:" in r["techniques"][0]
print("   kerberoasting found, detection pair rides")

print("== 7. spine lookup T1558.003 ==")
r = json.loads(grimoire_query(mode="spine", keyword="T1558.003"))
assert r["matches"] >= 1
assert "execution-ineligible" in r["note"]
print("   spine record:", r["records"][0].split("\n")[0])

print("== 8. atomic for T1003.006 ==")
r = json.loads(grimoire_query(mode="atomic", keyword="T1003.006"))
assert r["matches"] >= 1
assert "command:" in r["tests"][0]
print("   atomic test:", r["tests"][0].split("\n")[0])

print("== 9. catalog wordlists ==")
r = json.loads(grimoire_query(mode="catalog", keyword="wordlist"))
assert r["matches"] >= 1
print("   catalog:", r["entries"][0].split("\n")[0])

print("\n[PASS] GRIMOIRE INTEGRATION — 9/9")
