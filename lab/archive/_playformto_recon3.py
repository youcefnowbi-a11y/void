# -*- coding: utf-8 -*-
"""Playformto recon 3: auth grammar + linkId flow + live probe of share endpoint."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools._transport import fetch

r2 = fetch("https://www.playformto.com/assets/index-9cbbf8c4.js", timeout=60)
b = r2["body"]

# Token context — how the client gets/stores it
for m in list(re.finditer(r".{100}Token[:=].{140}", b))[:10]:
    t = m.group(0)
    if "Authorization" in t or "token" in t.lower():
        print("TOKENCTX:", t[:240].replace("\n", " "))
        print()

# linkId in API calls — what params ride the share page call
for m in list(re.finditer(r".{80}share/link/files.{200}", b)):
    print("SHARECTX:", m.group(0)[:280].replace("\n", " "))
    print()

# LIVE PROBE: the example link, anon
def probe(url, body=None):
    try:
        if body:
            r = fetch(url, method="POST", body=json.dumps(body),
                      headers={"Content-Type": "application/json"}, timeout=30)
        else:
            r = fetch(url, timeout=30)
        print(f"-> {url} [{r['status']}] {r['size']}b")
        if r["body"][:1] in ("{", "["):
            print("   ", r["body"][:700])
        else:
            print("   ", r["body"][:200].replace("\n", " "))
    except Exception as e:
        print(f"-> {url} ERR {type(e).__name__}: {str(e)[:150]}")
    print()

probe("https://api.qckenacio.to/v1/h5/share/link/files/page",
      {"linkId": "2022655389354573826", "page": 1, "pageSize": 20})
