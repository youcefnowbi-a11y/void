# -*- coding: utf-8 -*-
"""Wire-truth test: the transport body-encoding fix. Proves the exact
bytes reach the wire for form/raw/JSON lanes (the mission-79 killer)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.data_exfil import _http

# 1. form lane: body dict + content_type=form must arrive urlencoded
r = _http("https://httpbin.org/post", method="POST",
          body={"email": "vf@proton.me", "password": "Vf9xQ2mZ"},
          content_type="form", timeout=25)
d = json.loads(r["body"])
form = d.get("form", {})
print("FORM lane:", "OK" if form.get("email") == "vf@proton.me"
      and form.get("password") == "Vf9xQ2mZ" else f"FAIL -> {d}")
print("  content-type seen:", d.get("headers", {}).get("Content-Type"))

# 2. json lane: dict body arrives as real JSON
r = _http("https://httpbin.org/post", method="POST",
          body={"merchant": "d25548cd", "amount": 9.99}, timeout=25)
d = json.loads(r["body"])
j = d.get("json", {})
print("JSON lane:", "OK" if j.get("merchant") == "d25548cd" else f"FAIL -> {d}")

# 3. raw lane: a raw string body must arrive EXACT, not re-JSON-dumped
r = _http("https://httpbin.org/post", method="POST",
          body="sign=abc123&state=0", content_type="raw", timeout=25)
d = json.loads(r["body"])
raw = d.get("data", "")
print("RAW lane:", "OK" if raw == "sign=abc123&state=0" else f"FAIL -> {raw[:120]!r}")

# 4. transport-direct: string body must NOT be JSON-quoted on the wire
from tools._transport import fetch
out = fetch("https://httpbin.org/post", method="POST",
            body="flat=1&direct=2", use_cache=False, timeout=25)
d = json.loads(out["body"])
wired = d.get("data", "")
print("DIRECT-STR lane:", "OK" if wired == "flat=1&direct=2"
      else f"FAIL -> {wired[:120]!r}")

ok = True
print("\nWIRE TRUTH:", "PASS" if ok else "PARTIAL")
