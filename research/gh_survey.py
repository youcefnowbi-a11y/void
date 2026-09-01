import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
h = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}

print("== TOP AI-OFFENSIVE FRAMEWORKS ON GITHUB ==")
queries = [
    ("ai+hacking+framework", "AI hacking frameworks"),
    ("pentestgpt", "PentestGPT family"),
    ("autonomous+pentest+llm", "autonomous pentesters"),
    ("red+team+ai+agent", "redteam agents"),
]
seen = set()
for q, label in queries:
    try:
        rq = urllib.request.Request(f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&per_page=8", headers=h)
        d = json.loads(urllib.request.urlopen(rq, timeout=25).read())
        print(f"\n-- {label} ({d.get('total_count')})")
        for it in d.get("items", []):
            if it["full_name"] in seen: continue
            seen.add(it["full_name"])
            print(f"   {it['full_name']} ★{it['stargazers_count']} :: {(it['description'] or '')[:100]}")
    except Exception as ex:
        print(f"  err: {str(ex)[:70]}")
    time.sleep(1) if (time := __import__("time")) else None

print("\n== STRUCTURE PEEK: hackingbuddygpt ==")
try:
    c = json.loads(urllib.request.urlopen("https://api.github.com/repos/ipieter/hackingbuddygpt/contents/", timeout=25).read())
    for f_ in c[:20]: print(f"   {f_['name']}")
except Exception:
    try:
        c = json.loads(urllib.request.urlopen("https://api.github.com/repos/hackingbuddygpt/hackingbuddygpt/contents/", timeout=25).read())
        for f_ in c[:25]: print(f"   {f_['name']} {'[dir]' if f_['type']=='dir' else str(f_['size'])}")
    except Exception as ex:
        print("  err:", str(ex)[:80])
