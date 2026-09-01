"""deploy_watch.py — détecte les changements de déploiement sur un site."""
import json, hashlib, re, time
import urllib.request
from tools import register

@register(
    name="deploy_watch",
    desc="Capture un snapshot d'un site (bundles JS, routes, titres, robots). Compare avec les snapshots précédents pour détecter déploiements, nouvelles routes, endpoints cachés.",
    params={
        "type": "object",
        "properties": {
            "target": {"type": "string"},
            "action": {"type": "string", "enum": ["snapshot", "diff"]},
            "snapshot_file": {"type": "string"}
        },
        "required": ["target"]
    }
)
def deploy_watch(target, action="snapshot", snapshot_file=None):
    target = target.rstrip("/")
    snap = {}

    # 1. Récupérer le HTML
    try:
        req = urllib.request.Request(target, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode(errors="replace")
    except Exception as ex:
        return json.dumps({"error": f"fetch failed: {type(ex).__name__}: {str(ex)[:150]}",
                           "target": target}, indent=2)
    snap["title"] = re.search(r"<title>(.*?)</title>", html, re.I).group(1).strip() if re.search(r"<title>(.*?)</title>", html, re.I) else ""
    snap["robots"] = "robots" in html

    # 2. Extraire tous les JS du HTML (inclut les module scripts et les import maps)
    # On cherche aussi les "type=importmap" pour repérer les modules préchargés
    import_map = re.search(r'<script[^>]*type="importmap"[^>]*>(.*?)</script>', html, re.S)
    if import_map:
        snap["import_map"] = import_map.group(1).strip()[:500]
    js_urls = []
    # scripts avec src
    js_urls += re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html)
    # scripts type module (souvent sans extension .js mais on les garde)
    js_urls += re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
    # lien preload des modules
    js_urls += re.findall(r'<link[^>]*href=["\']([^"\']+\.js[^"\']*)["\']', html)
    js_hashes = {}
    for js in set(js_urls):
        if js.startswith("//"): js = "https:" + js
        elif js.startswith("/"): js = target + js
        elif not js.startswith("http") and not js.startswith("data:"):
            js = target + "/" + js
        if js.startswith("data:") or js.startswith("blob:"):
            continue
        try:
            r = urllib.request.urlopen(js, timeout=20)
            h = hashlib.md5(r.read()).hexdigest()
            js_hashes[js] = h
        except Exception:
            pass
    snap["bundles"] = js_hashes
    snap["bundles_count"] = len(js_hashes)

    # 3. Lire quelques endpoints connus
    endpoints = ["/robots.txt", "/sitemap.xml", "/.env", "/admin", "/api/health"]
    ep_status = {}
    for ep in endpoints:
        try:
            r = urllib.request.urlopen(target + ep, timeout=10)
            ep_status[ep] = r.status
        except Exception:
            ep_status[ep] = None
    snap["endpoints"] = ep_status

    # 4. Sauvegarder ou comparer
    import os
    # confinement: snapshots sous reports/snapshots/, basename slugifié (R5-4)
    snap_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "reports", "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    fname = os.path.join(snap_dir, os.path.basename(
        snapshot_file or f"snapshot_{int(time.time())}.json"))
    real, reald = os.path.realpath(fname), os.path.realpath(snap_dir)
    if not real.startswith(reald + os.sep):
        return "TOOL ERROR [ARGS]: snapshot path refuse"

    if action == "snapshot":
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(snap, f, indent=2, ensure_ascii=False)
        return json.dumps({"snapshot_saved": fname, "bundles_count": len(js_hashes)}, indent=2)

    if not snapshot_file:
        return "missing snapshot_file"
    with open(fname, "r", encoding="utf-8") as f:
        prev = json.load(f)
    changes = {"new_bundles": [], "removed_bundles": [], "changed_bundles": []}
    for url, h in js_hashes.items():
        if url not in prev.get("bundles", {}):
            changes["new_bundles"].append(url)
        elif prev["bundles"][url] != h:
            changes["changed_bundles"].append(url)
    for url in prev.get("bundles", {}):
        if url not in js_hashes:
            changes["removed_bundles"].append(url)
    changes["title_changed"] = prev.get("title") != snap["title"]
    return json.dumps(changes, indent=2)