# -*- coding: utf-8 -*-
"""Direct slice around the api() position + hunt auth grammar anywhere."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.data_exfil import data_extract

r = json.loads(data_extract("https://duskyr.com/a316f209d2/",
                            truncate_at=3000, tail_bytes=150000, offset_bytes=60000))
w = r.get("window", "")
print("window len:", len(w))

i = w.find("api(")
print("api( at:", i)
if i >= 0:
    print(w[max(0, i-400):i+600])

for kw in ("Authorization", "Bearer", "initData", "X-Auth", "token"):
    j = w.find(kw)
    if j >= 0:
        print(f"\n=== {kw} at {j} ===")
        print(w[max(0, j-200):j+400])
