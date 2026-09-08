import sys, json, traceback
sys.path.insert(0, '.')
from tools import discover, all_tools, execute
discover()
by = {t["name"]: t["run"] for t in all_tools()}
BASE = "http://127.0.0.1:8765"

# 1. sqli_tamper_chain traceback réel
try:
    out = by["sqli_tamper_chain"](url=f"{BASE}/product?id=1", param="id", max_requests=6)
    print("tamper OK:", str(out)[:150])
except Exception:
    tb = traceback.format_exc().strip().splitlines()
    print("=== sqli_tamper_chain ===")
    print("\n".join(tb[-3:]))

# 2. data_extract /jwt — pourquoi pas de token?
out = execute("data_extract", {"url": f"{BASE}/jwt"})
print("\n=== data_extract /jwt ===")
print(str(out)[:300])
