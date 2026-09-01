"""Smoke test du generateur de rapport professionnel."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.report import write_report

t = [
    ("agent", "Plan: recon target, then probe auth. EXECUTIVE SUMMARY pending."),
    ("tool",  'data_extract: fetched bundle, found api_key = "AIzaSyD-9tJq8xTest_abc123def456" in config'),
    ("tool",  "data_extract: JWT captured eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"),
    ("tool",  "data_exfil: storage/v1/bucket -> 200 OK, bucket listing exposed"),
    ("tool",  "waf_detect: cloudflare detected, moderate intensity"),
    ("tool",  "data_extract: fetched bundle, found api_key = \"AIzaSyD-9tJq8xTest_abc123def456\" in config"),  # doublon
]
p = write_report("test mission synthetic", t, "reports")
print("RAPPORT:", p)
print("---")
content = open(p, encoding="utf-8").read()
print(content[:1600])
print("...")
assert "ENGAGEMENT & RULES OF ENGAGEMENT" in content
assert "[HIGH]" in content
assert "ARSENAL LEDGER" in content
# dedup : exactement UN bullet finding contient AIzaSyD (evidence+context = 1 entrée)
findings_section = content.split("## FINDINGS")[1].split("## ARSENAL")[0]
bullets = [l for l in findings_section.splitlines() if l.startswith("- **[") and "AIzaSyD" in l]
assert len(bullets) == 1, f"doublon non deduplique dans findings: {len(bullets)} bullets"
assert "data_extract` ×3" in content, "ledger non aggrege"
print("[PASS] rapport pro genere, severites triees, doublons dedupliques, ledger aggrege")
