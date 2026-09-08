# -*- coding: utf-8 -*-
"""Playformto recon 2: full API grammar from the 500KB bundle."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools._transport import fetch

r2 = fetch("https://www.playformto.com/assets/index-9cbbf8c4.js", timeout=60)
b = r2["body"]
print("bundle:", r2["status"], r2["size"])

# every /v1/ endpoint with surrounding context
seen = set()
for m in re.finditer(r"/v1/h5[a-z0-9_/.]*", b):
    ep = m.group(0)
    if ep in seen:
        continue
    seen.add(ep)
    ctx = b[max(0, m.start() - 80):m.end() + 150].replace("\n", " ")
    print(f"\n=== {ep}")
    print("   ", ctx[:220])

# headers / auth grammar
for pat in (r"Authorization[^,;]{0,80}", r"[Tt]oken['\"]?\s*[:=][^,;}]{0,60}",
            r"headers\s*[:=]\s*\{[^}]{0,200}"):
    hits = list(re.finditer(pat, b))[:8]
    for h in hits:
        print("AUTHCTX:", h.group(0)[:150])
