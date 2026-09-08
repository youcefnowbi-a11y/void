# -*- coding: utf-8 -*-
"""Playformto recon: inline scripts + bundle path mining."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools._transport import fetch

r = fetch("https://www.playformto.com", timeout=25)
b = r["body"]
inline = re.findall(r"<script>(.*?)</script>", b, re.S)
for i, s in enumerate(inline):
    print(f"--- inline script {i} ({len(s)} chars):")
    print(s[:900])

r2 = fetch("https://www.playformto.com/assets/index-9cbbf8c4.js", timeout=40)
print()
print("bundle:", r2["status"], r2["size"], "bytes")
apis = sorted(set(re.findall(r"['\"`]((?:https?://|/)[a-z0-9./_\-]{4,60})['\"`]", r2["body"])))
print("path/url refs:", len(apis))
for a in apis[:50]:
    print(" -", a)

# linkId refs — how the app consumes them
for m in re.finditer(r".{60}linkId.{120}", r2["body"]):
    print("LINKCTX:", m.group(0)[:200])
