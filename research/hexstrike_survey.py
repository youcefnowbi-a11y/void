import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
h = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}

def gh(url):
    rq = urllib.request.Request(url, headers=h)
    try:
        return json.loads(urllib.request.urlopen(rq, timeout=30).read())
    except Exception as ex:
        return {"__err__": str(ex)[:80]}

print("== HEXSTRIKE-AI: root structure ==")
c = gh("https://api.github.com/repos/0x4m4/hexstrike-ai/contents/")
if "__err__" in c:
    print(c["__err__"])
else:
    for f_ in c[:25]:
        print(f"   {f_['name']:32s} {'[dir]' if f_['type']=='dir' else str(f_['size'])}")

print("\n== HEXSTRIKE README head (integration philosophy) ==")
r = gh("https://api.github.com/repos/0x4m4/hexstrike-ai/readme")
if "__err__" not in r:
    import base64
    txt = base64.b64decode(r.get("content","")).decode(errors="replace")
    print(txt[:1500])
else:
    print(r["__err__"])

print("\n== TELEGRAM HARVESTERS SURVEY ==")
for q, label in [("telegram+scraper+members", "member scrapers"),
                 ("telethon+userbot+framework", "userbot frameworks")]:
    d = gh(f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&per_page=6")
    print(f"\n-- {label}")
    for it in d.get("items", [])[:6]:
        print(f"   {it['full_name']} ★{it['stargazers_count']} :: {(it['description'] or '')[:80]}")

import urllib.parse
