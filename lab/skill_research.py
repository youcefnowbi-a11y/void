"""VOIDFORGE :: skill research — scan GitHub's offensive-knowledge corpora.
Real API queries against the canonical repositories the world's operators
learn from. Output: ranked dossier -> reports/skill_research.json
Run: python lab/skill_research.py
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools._exploit_lib import paced_send

QUERIES = [
    "payload all the things",
    "hacktricks",
    "GTFOBins",
    "LOLBAS windows",
    "atomic red team",
    "red team playbook",
    "penetration testing checklist methodology",
    "command and control framework red team",
    "privilege escalation enumeration linux windows",
    "active directory attack cheatsheet",
    "cloud security exploitation aws azure",
    "web security methodology OWASP WSTG",
]

def search(q, per=4):
    st, body, _ = paced_send(
        "https://api.github.com/search/repositories?q=" + q.replace(" ", "+")
        + "&sort=stars&order=desc&per_page=" + str(per),
        headers={"Accept": "application/vnd.github+json"}, timeout=25)
    if st != 200:
        return {"query": q, "error": f"HTTP {st}", "repos": []}
    try:
        items = json.loads(body).get("items", [])
        return {"query": q, "repos": [
            {"name": r["full_name"], "stars": r["stargazers_count"],
             "desc": (r.get("description") or "")[:180], "url": r["html_url"]}
            for r in items]}
    except Exception as ex:
        return {"query": q, "error": str(ex)[:120], "repos": []}

def main():
    out = []
    for i, q in enumerate(QUERIES, 1):
        r = search(q)
        out.append(r)
        print(f"[{i}/{len(QUERIES)}] {q}")
        for repo in r["repos"]:
            print(f"    {repo['stars']:>7}★  {repo['name']:<44} {repo['desc'][:70]}")
        if r.get("error"):
            print(f"    ! {r['error']}")
        time.sleep(7)  # unauthenticated search: 10 req/min — stay polite
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "reports", "skill_research.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n[saved] {path}")

if __name__ == "__main__":
    main()
