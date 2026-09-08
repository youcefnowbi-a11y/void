# -*- coding: utf-8 -*-
"""Probe provider model availability during the b.ai routing-DB outage."""
import requests, yaml

cfg = yaml.safe_load(open("config/provider.yaml", encoding="utf-8"))
p = cfg["provider"]
url = p.get("base_url", "").rstrip("/")
key = p.get("api_key", p.get("key", ""))
h = {"Authorization": "Bearer " + str(key)}
models = ["glm-5.3-flash", "glm-4.7-flash", "glm-4-flash",
          "glm-4.6", "glm-4.5-flash", "glm-5.3", "glm-5.2-flash"]
for m in models:
    try:
        r = requests.post(url + "/chat/completions", headers=h, timeout=45,
                          json={"model": m,
                                "messages": [{"role": "user", "content": "say OK"}],
                                "max_tokens": 5})
        if r.status_code == 200 and "content" in r.text:
            print(f"{m}: 200 OK ->", r.json()["choices"][0]["message"]["content"][:40])
            break
        print(f"{m}: {r.status_code}", r.text[:110])
    except Exception as e:
        print(f"{m}: ERR {type(e).__name__} {str(e)[:80]}")
