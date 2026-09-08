# -*- coding: utf-8 -*-
"""The jackpot check: what do the BOLA-leaked listing INSTRUCTIONS
actually contain? If sellers put the deliverable in there, mission D
already extracted the products without realizing it."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pull a few listings directly (the BOLA lane is anonymous-read)
import urllib.request, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for lid in (506, 509, 512, 520, 529):
    try:
        req = urllib.request.Request(
            f"https://duskyr.com/api/market/listings/{lid}",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
            instr = str(d.get("instructions", ""))[:400]
            print(f"--- listing {lid} | {str(d.get('title',''))[:50]}")
            print(f"    instructions: {instr!r}")
    except Exception as e:
        print(f"--- listing {lid}: FAIL {e}")
