"""Proof-section probe: what the final report will now carry."""
import sys, os, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mission_workspace import Workspace

ws = Workspace("probe-target")
# simulated campaign artifacts
ws.save_extraction("data_extract", json.dumps({
    "rows": [{"email": "admin@madleets.me", "plan": "vip"}, {"email": "user2@x.io", "plan": "pro"}],
    "count": 2, "source": "/api/v1/users"}))
ws.save_extraction("subdomain_enum", json.dumps(["api.madleets.me", "vpn.madleets.me", "dev.madleets.me"]))
ws.save_finding("jwt_forge_replay", json.dumps({
    "tool": "jwt_forge_replay", "exploitable": True,
    "summary": "alg:none accepté — /orders répond 200 avec rôle admin"}))
ws.log_run("jwt_forge_replay", {"replay_url": "u"}, '{"exploitable": true}', 2.1, "ok", 3)
ws.log_run("data_extract", {"url": "u"}, '{"rows": 2}', 0.4, "ok", 4)

print(ws.proof_section())
print("\n" + "=" * 60)
print("TAILLE:", len(ws.proof_section()), "chars — tient dans le contexte outil (6000)")
shutil.rmtree(ws.dir, ignore_errors=True)
