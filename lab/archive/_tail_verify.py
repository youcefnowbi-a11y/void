# -*- coding: utf-8 -*-
"""Locate the crypto section across bundle slices."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
from tools.data_exfil import data_extract

r = json.loads(data_extract("https://www.playformto.com/assets/index-9cbbf8c4.js",
                            truncate_at=3000, tail_bytes=200000))
t = r.get("tail", "")
print("tail len:", len(t))
for kw in ("AES", "encrypt", "secretKey", "handlePlayVideo", "ECB"):
    idx = t.find(kw)
    state = "FOUND" if idx >= 0 else "not in last 200KB"
    print(f"  {kw}: pos {idx} ({state})")

r2 = json.loads(data_extract("https://www.playformto.com/assets/index-9cbbf8c4.js",
                             truncate_at=200000, tail_bytes=0))
b = r2.get("text", "")
print("head-200K len:", len(b))
for kw in ("AES", "secretKey", "ECB", "handlePlayVideo", "qckenacio"):
    print(f"  head-200K {kw}: pos", b.find(kw))
