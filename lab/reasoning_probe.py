"""REASONING PROBE — does the provider return reasoning_content on tool calls?
READ-ONLY: one raw chat.completions call with one tool schema; prints message keys.
"""
import sys, os, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml as _yaml

VOIDFORGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(VOIDFORGE_ROOT, "config", "provider.yaml"), encoding="utf-8") as f:
    cfg = _yaml.safe_load(f)
p = cfg["provider"]

body = {
    "model": p["model"], "temperature": 0.2,
    "messages": [{"role": "user", "content": "Scan example.com quickly. Use a tool."}],
    "tools": [{"type": "function", "function": {"name": "web_fingerprint", "description": "fingerprint a url",
               "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}],
}
req = urllib.request.Request(p["base_url"].rstrip("/") + "/chat/completions", method="POST")
req.add_header("Authorization", f"Bearer {p['api_key']}")
req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, data=json.dumps(body).encode(), timeout=90) as r:
        resp = json.loads(r.read().decode())
    msg = (resp.get("choices") or [{}])[0].get("message") or {}
    print("message keys:", sorted(msg.keys()))
    print("content:", (msg.get("content") or "")[:120])
    print("reasoning_content present:", "reasoning_content" in msg and bool(msg.get("reasoning_content")))
    print("reasoning sample:", (msg.get("reasoning_content") or "")[:200])
    print("tool_calls:", [(t["function"]["name"]) for t in msg.get("tool_calls") or []])
except Exception as ex:
    print("PROBE FAILED:", type(ex).__name__, str(ex)[:200])
