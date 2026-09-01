import json, sys, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
h = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}

def gh(url):
    rq = urllib.request.Request(url, headers=h)
    try:
        return json.loads(urllib.request.urlopen(rq, timeout=30).read())
    except Exception as ex:
        return {"__err__": str(ex)[:80]}

print("== SELF-HEALING / SELF-EVOLVING AGENT RESEARCH ==")
for q, label in [
    ("self-healing+agent+tool+errors", "self-healing tool agents"),
    ("agent+learns+from+failed+commands", "learning from failures"),
    ("llm+agent+auto+fix+code", "LLM auto-fix"),
    ("autonomous+agent+memory+persistence", "persistent memory agents"),
]:
    d = gh(f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&per_page=6")
    print(f"\n-- {label} ({d.get('total_count', '?')})")
    for it in d.get("items", [])[:6]:
        print(f"   {it['full_name']} ★{it['stargazers_count']} :: {(it['description'] or '')[:95]}")

print("\n== HEXSTRIKE self-healing mentions in README ==")
r = gh("https://api.github.com/repos/0x4m4/hexstrike-ai/readme")
if "__err__" not in r:
    import base64
    txt = base64.b64decode(r.get("content", "")).decode(errors="replace")
    import re
    for kw in ["self-heal", "healing", "auto-recover", "intelligent", "fallback", "retry"]:
        hits = [m.start() for m in re.finditer(kw, txt, re.I)]
        if hits:
            i = hits[0]
            print(f"  [{kw}] ...{txt[max(0,i-100):i+200]}...".replace(chr(10), " ")[:280])
