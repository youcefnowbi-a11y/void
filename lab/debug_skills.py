import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools as reg
reg.discover()
from core.skills import list_skills, load_skill

REGISTRY = {t["name"]: t for t in reg.all_tools()}
param_names = {k for t in REGISTRY.values() for k in (t["params"].get("properties") or {})}
allowed = set(REGISTRY) | param_names

for s in list_skills():
    ghosts = {w for w in re.findall(r"\b[a-z][a-z0-9_]{3,28}\b", s["text"])
              if "_" in w and w not in allowed
              and not w.startswith(("url_", "api_", "auth_"))
              and w not in ("cve_id", "verify_url", "url_template", "url_template_cmd",
                            "success_pattern", "gadget_check", "mission_focus")}
    if ghosts:
        print(f"{s['id']}: {sorted(ghosts)}")
print("done")
