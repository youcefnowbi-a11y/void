# -*- coding: utf-8 -*-
"""Extract the api() definition from the now-reachable gap — the auth oracle."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.data_exfil import data_extract

r = json.loads(data_extract("https://duskyr.com/a316f209d2/",
                            truncate_at=3000, tail_bytes=150000, offset_bytes=60000))
w = r.get("window", "")

# every 'api(' occurrence with context — find the DEFINITION (class method)
import re
print("=== api( occurrences ===")
for m in re.finditer(r".{160}api\s*\(", w):
    seg = m.group(0).replace("\n", " ")
    print(seg[-320:])
    print("---")

# also the class constructor + fetch/xhr usage
print("=== fetch/headers grammar ===")
for pat in (r".{100}headers\s*[:=].{120}", r".{80}[Bb]earer.{100}"):
    for m in list(re.finditer(pat, w))[:4]:
        print(m.group(0).replace("\n", " ")[:260])
        print("---")
