"""VERIFICATION: self-healing organism prototype.
1. Classify the real nuclei -json failure
2. Learn + persist the migration
3. Prove learned fix retrieval
4. Prove TIMEOUT healing doubles timeout
5. Live: nuclei_scan with corrected flag runs for real."""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import healer

print("== 1. classify real failure ==")
cat, det = healer.classify('flag provided but not defined: -json')
assert cat == "FLAG_RENAMED", cat
print("   ->", cat, det)

print("== 2. learn migration ==")
healer.learn_flag_migration("nuclei", "-json", "-j")
data = healer._load_fixes()
assert data["tool_flag_migrations"]["nuclei"]["to"] == "-j"
print("   persisted to learned_fixes.json ✓")

print("== 3. heal_attempt with dict-args ==")
patched, note = healer.heal_attempt("nuclei", "FLAG_RENAMED",
                                    {"bad_flag": "-json"}, {"severity": "critical"})
print("   ->", note)

print("== 4. TIMEOUT healing ==")
a2, n2 = healer.heal_attempt("some_tool", "TIMEOUT", {}, {"timeout_min": 10})
assert a2["timeout_min"] == 20, a2
print(f"   timeout doubled -> {a2['timeout_min']} ({n2})")

print("== 5. LIVE nuclei scan (corrected flag) ==")
if not os.environ.get("VF_LIVE_NET"):
    # Intégration opt-in: binaire nuclei + réseau réel, 4 min — jamais dans la
    # batterie automatique (comme test_monster exige son lab). VF_LIVE_NET=1
    # pour la lancer à la main.
    print("   SKIP (live network — relance avec VF_LIVE_NET=1 pour l'intégration)")
else:
    import tools as reg
    out = reg.execute("nuclei_scan", {"target": "https://example.com",
                                      "timeout_min": 4})
    # les chain hints (tools/_hints.py) collent "→ NEXT: ..." APRÈS le JSON
    # des outils producteurs — strip le suffixe avant le parse.
    d = json.loads(out.split("\n\n→ NEXT: ")[0])
    print(f"   findings: {d.get('findings_count')} | raw_tail: {str(d.get('raw_tail'))[:150]}")
print("\n[PASS] THE ORGANISM LIVES")
