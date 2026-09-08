import sys, json
sys.path.insert(0, ".")
from tools import execute, discover
discover()
r = execute("arsenal_selftest", {"mode": "catalog"})
d = json.loads(r)
print("catalog:", d["tools_total"], "tools ·", d["duration_s"], "s")
print("exemple recette binary_fuzz_run:", json.dumps(d["arsenal_map"]["binary_fuzz_run"], ensure_ascii=False)[:400])
