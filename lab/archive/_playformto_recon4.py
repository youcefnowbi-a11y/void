# -*- coding: utf-8 -*-
"""Playformto recon 4: correct grammar probe + auth flow hunt."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools._transport import fetch

def post(url, body, extra_headers=None):
    h = {"Content-Type": "application/json"}
    if extra_headers:
        h.update(extra_headers)
    r = fetch(url, method="POST", body=json.dumps(body), headers=h, timeout=30)
    print(f"-> {url} [{r['status']}] {r['size']}b")
    print("   ", r["body"][:800])
    print()
    return r

# 1. share link files with the revealed grammar
post("https://api.qckenacio.to/v1/h5/share/link/files/page",
     {"linkId": "2022655389354573826", "size": 20})

# 2. most viewed accounts (random_operation_account)
post("https://api.qckenacio.to/v1/h5/random_operation_account/most_viewed",
     {"size": 10})

# 3. open data
post("https://api.qckenacio.to/v1/h5_open_data", {})

# 4. push operation pools
post("https://api.qckenacio.to/v1/h5_app_push_operation_pools", {"size": 10})
