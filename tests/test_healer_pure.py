"""VERIFICATION healer PUR - aucune execution reelle d'outil externe."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import healer

print("== 1. classify real failure ==")
cat, det = healer.classify('flag provided but not defined: -json')
assert cat == "FLAG_RENAMED", cat
print("   ->", cat, det)

print("== 2. learn + persist migration ==")
healer.learn_flag_migration("nuclei", "-json", "-j")
data = healer._load_fixes()
assert data["tool_flag_migrations"]["nuclei"]["to"] == "-j"
print("   persisted OK")

print("== 3. TIMEOUT healing: tool AVEC timeout_min ==")
a2, n2 = healer.heal_attempt("t1", "TIMEOUT", {}, {"timeout_min": 10})
assert a2["timeout_min"] == 20 and "doubled" in n2
print(f"   doubled -> {a2['timeout_min']} ({n2})")

print("== 4. TIMEOUT healing: tool SANS timeout_min (fix audit) ==")
a3, n3 = healer.heal_attempt("t2", "TIMEOUT", {}, {"url": "https://x.com"})
assert a3 == {"url": "https://x.com"}, f"kwargs injectes a tort: {a3}"
assert "plain retry" in n3
print(f"   args intacts ({n3})  <- regression #1 CORRIGEE")

print("== 5. AUTH_REQUIRED detection (fix audit) ==")
cat5, _ = healer.classify('HTTPError: 401 Unauthorized for url ...')
assert cat5 == "AUTH_REQUIRED", cat5
print(f"   -> {cat5}  <- regression #4 CORRIGEE")

print("== 6. UNKNOWN par defaut ==")
cat6, _ = healer.classify('something weird happened')
assert cat6 == "UNKNOWN"
print("   -> UNKNOWN")

print("\n[PASS] HEALER SAIN - 6/6")
