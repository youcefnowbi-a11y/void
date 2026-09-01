"""VOIDFORGE :: workspace structural test.
Run: python lab/test_workspace.py
"""
import sys, os, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mission_workspace import Workspace, extract_target

# target extraction
assert extract_target("attack http://forge.local:8765 now") == "forge.local"
assert extract_target("pentest madleets.me please") == "madleets.me"
assert extract_target("scan the thing") is None
print("✓ target extraction")

ws = Workspace("forge.local")
print("✓ folder:", os.path.relpath(ws.dir))

# simulated runs
ws.log_run("web_fingerprint", {"url": "http://forge.local"}, '{"root_status":200}', 1.2, "ok", 1)
ws.save_extraction("web_fingerprint", '{"root_status":200,"server":"uvicorn"}')
ws.log_run("jwt_forge_replay", {"token": "x", "replay_url": "u"},
           json.dumps({"tool": "jwt_forge_replay", "exploitable": True,
                       "summary": "alg:none accepted — admin role"}), 3.1, "ok", 2)
ws.save_finding("jwt_forge_replay", json.dumps(
    {"tool": "jwt_forge_replay", "exploitable": True, "summary": "alg:none accepted"}))
ws.log_run("sqli_union_dump", {"url_template": "u{INJ}"},
           json.dumps({"tool": "sqli_union_dump", "exploitable": "partial",
                       "summary": "width found, rows partial"}), 8.0, "ok", 3)
ws.save_finding("sqli_union_dump", json.dumps(
    {"tool": "sqli_union_dump", "exploitable": "partial", "summary": "partial dump"}))
ws.log_run("race_smash", {"url": "u"}, "TOOL ERROR [UNKNOWN_TOOL]: nope", 0.1, "error", 4)

p = ws.write_power_report([("tool", "x"), ("agent", "r")])
assert p and os.path.exists(p), "power report missing"
print("✓ power report:", os.path.relpath(p))

# structure
sub = {d: len(os.listdir(os.path.join(ws.dir, d))) for d in
       ("extractions", "findings", "reports")}
print("✓ structure:", sub)
print("✓ ledger lines:", sum(1 for _ in open(ws.ledger_path, encoding="utf-8")))

pr = open(p, encoding="utf-8").read()
assert "jwt_forge_replay" in pr and "FORTE" in pr and "FAIBLE" in pr
print("✓ power report names strengths AND weaknesses")
shutil.rmtree(ws.dir, ignore_errors=True)  # clean test artifact
print("\nWORKSPACE TEST: all green")
