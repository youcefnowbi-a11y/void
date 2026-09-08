# -*- coding: utf-8 -*-
"""Playformto recon 5: full grammar + example link data pull."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools._transport import fetch

def post(url, body):
    h = {"Content-Type": "application/json"}
    r = fetch(url, method="POST", body=json.dumps(body), headers=h, timeout=30)
    print(f"-> {url.split('/')[-1]} [{r['status']}] {r['size']}b")
    body_txt = r["body"][:1200]
    print("   ", body_txt)
    print()
    return r

# 1. the example link — full page grammar
post("https://api.qckenacio.to/v1/h5/share/link/files/page",
     {"linkId": "2022655389354573826", "size": 20, "page": 1})

# 2. most viewed — fileType grammar (video? image? all?)
for ft in (1, "video", "all"):
    post("https://api.qckenacio.to/v1/h5/random_operation_account/most_viewed",
         {"fileType": ft, "size": 10})
