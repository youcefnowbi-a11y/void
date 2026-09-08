# -*- coding: utf-8 -*-
"""Playformto recon 6: bundle tells how requests are wrapped (encrypt? sign?)."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools._transport import fetch

b = fetch("https://www.playformto.com/assets/index-9cbbf8c4.js", timeout=60)["body"]

# axios instance creation + interceptors (the wrapper lives there)
for m in list(re.finditer(r"interceptors\.request[^;]{0,400}", b))[:6]:
    print("REQ-INTERCEPTOR:", m.group(0)[:400])
    print()

for m in list(re.finditer(r"baseURL[^,;]{0,100}", b))[:8]:
    print("BASEURL:", m.group(0)[:120])

# sign/encrypt/params wrap
for pat in (r"encrypt[A-Za-z]{0,20}\(", r"AES[^({]{0,60}", r"sign\s*[:=][^,;}]{0,60}",
            r"timestamp[^,;}]{0,50}", r"nonce[^,;}]{0,40}"):
    hits = list(re.finditer(pat, b))[:5]
    for h in hits:
        print(f"{pat[:14]}:", h.group(0)[:110])
