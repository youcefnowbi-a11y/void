# -*- coding: utf-8 -*-
"""Verify K2 fleet fixes live: offset window + header capture."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.data_exfil import data_extract
from tools.spa_crawl import spa_crawl

# Fix 1: sliding window into the verifier HTML middle (the 60-208KB gap K2 died on)
r = json.loads(data_extract("https://duskyr.com/a316f209d2/",
                            truncate_at=3000, tail_bytes=150000, offset_bytes=60000))
w = r.get("window", "")
print("FIX1 offset window: len", len(w), "offset", r.get("window_offset"))
assert len(w) > 140000, "window too small"
assert "api(" in w or "initData" in w or "Authorization" in w, "gap content not reached"
print("FIX1 OK — the never-reachable middle now lands in one call:")
for kw in ("api(", "initData", "Authorization", "class "):
    print(f"  '{kw}' at window pos", w.find(kw))

# Fix 2: header capture via the fetch hook
try:
    c = json.loads(spa_crawl("https://duskyr.com/", wait_s=20))
    reqs = c.get("captured_requests", [])
    print("FIX2 captured requests:", len(reqs))
    with_hdr = [q for q in reqs if q.get("req_headers")]
    print("FIX2 requests WITH headers:", len(with_hdr))
    for q in with_hdr[:3]:
        print("  ", q.get("method"), q.get("url", "")[:60], "→", json.dumps(q.get("req_headers"))[:120])
except Exception as e:
    print("FIX2 spa_crawl error:", type(e).__name__, str(e)[:200])
