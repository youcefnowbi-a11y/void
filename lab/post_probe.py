"""POST-path probe: proves the frontend's exact route works end-to-end.
POST /tool {tool: web_fingerprint, args: {url: lab range}} — harmless, fast.
"""
import json, urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/tool",
    data=json.dumps({"tool": "web_fingerprint", "args": {"url": "http://127.0.0.1:8765"}}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode())
        print("POST /tool ->", r.status)
        print("réponse:", json.dumps(body, ensure_ascii=False)[:300])
except Exception as ex:
    print("POST /tool ÉCHEC:", ex)
