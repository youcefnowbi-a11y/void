# -*- coding: utf-8 -*-
"""Provider sanity: full chat round-trip before mission relaunch."""
import requests, yaml

cfg = yaml.safe_load(open("config/provider.yaml", encoding="utf-8"))
p = cfg["provider"]
url = p.get("base_url", "").rstrip("/")
key = p.get("api_key", p.get("key", ""))
h = {"Authorization": "Bearer " + str(key)}
r = requests.post(url + "/chat/completions", headers=h, timeout=90,
                  json={"model": "glm-5.3-flash",
                        "messages": [{"role": "user", "content": "Reply with exactly: FORGE-OK"}],
                        "max_tokens": 800})
print("status:", r.status_code)
try:
    j = r.json()
    msg = j["choices"][0]["message"]
    print("content:", repr(msg.get("content", ""))[:200])
    print("reasoning:", repr(msg.get("reasoning_content", ""))[:100])
    print("finish:", j["choices"][0].get("finish_reason"))
except Exception as e:
    print("parse ERR:", e, r.text[:200])
