"""TOOL: httpx_sweep - concurrent host liveness sweep (our httpx).

Given a list of hosts, probe scheme/port combinations concurrently under the
ROE governor and report what's alive: status, title, server header, redirects,
tech hints. The strategist uses it at round 0 to turn a target list into a
prioritized live-surface map.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from tools import register
from tools._exploit_lib import paced_send

DEFAULT_PORTS = [80, 443, 8080, 8443, 8000, 3000]

TECH_HINTS = [
    ("wordpress", r"wp-content|wp-json"),
    ("drupal", r"drupal|sites/default"),
    ("joomla", r"Joomla!|/media/jui/"),
    ("react", r"__NEXT_DATA__|react|/static/js/"),
    ("vue", r"vue\.js|data-v-app"),
    ("angular", r"ng-version|angular"),
    ("django", r"csrfmiddlewaretoken|__admin__/"),
    ("laravel", r"laravel_session|XSRF-TOKEN"),
    ("spring", r"JSESSIONID|Spring Framework"),
    ("express", r"X-Powered-By: Express|express"),
    ("nginx", r"<center>nginx</center>|nginx/"),
    ("cloudflare", r"cloudflare|cf-ray"),
    ("grafana", r"grafana"),
    ("kibana", r"kibana"),
    ("jenkins", r"Jenkins|X-Jenkins"),
    ("gitlab", r"gitlab"),
    ("phpmyadmin", r"phpMyAdmin"),
    ("swagger", r"swagger|openapi"),
]


def normalize_hosts(hosts):
    """Accept list, comma/newline string, or single host -> clean host list."""
    if isinstance(hosts, str):
        hosts = re.split(r"[,\s]+", hosts)
    out, seen = [], set()
    for h in hosts or []:
        h = str(h).strip().replace("http://", "").replace("https://", "").rstrip("/")
        h = h.split(":")[0] if ":" in h and not h.startswith("[") else h
        if h and h not in seen:
            seen.add(h)
            out.append(h)
    return out[:200]


def build_candidates(hosts, ports):
    urls = []
    for h in hosts:
        host = h.split(":")[0] if ":" in h and not h.startswith("[") else h
        for p in ports:
            if p == 443:
                urls.append(f"https://{host}/")
            elif p == 80:
                urls.append(f"http://{host}/")
            else:
                urls.append(f"http://{host}:{p}/")
    return urls


def _probe(url, timeout):
    st, body, dt = paced_send(url, timeout=timeout)
    if st < 0:
        return None
    m = re.search(r"<title[^>]*>([^<]{0,120})</title>", body or "", re.I)
    server = ""
    tech = []
    low = (body or "").lower()
    for name, rx in TECH_HINTS:
        if re.search(rx, low):
            tech.append(name)
    return {"url": url, "status": st, "title": (m.group(1).strip() if m else ""),
            "len": len(body or ""), "dt": round(dt, 2), "tech": tech[:6]}


@register(name="httpx_sweep",
          desc="HOST SWEEP: probe a list of hosts across scheme/port combos "
               "CONCURRENTLY (ROE-governed) — alive status, page title, tech "
               "hints (CMS/framework), response length. Round-0 recon: turn a "
               "target list into a prioritized live map.",
          params={"type": "object", "properties": {
              "hosts": {"type": "array", "description": "hosts: list or comma/newline string"},
              "ports": {"type": "array", "description": f"ports to try, default {DEFAULT_PORTS}"},
              "timeout": {"type": "integer", "default": 8},
              "workers": {"type": "integer", "default": 12}},
              "required": ["hosts"]},
          danger="active")
def httpx_sweep(hosts, ports=None, timeout=8, workers=12):
    host_list = normalize_hosts(hosts)
    if not host_list:
        return "TOOL ERROR [NO_HOSTS]: liste vide"
    port_list = [int(p) for p in (ports or DEFAULT_PORTS)][:12]
    cands = build_candidates(host_list, port_list)
    alive = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers or 12), 30))) as ex:
        futs = {ex.submit(_probe, u, int(timeout or 8)): u for u in cands}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                alive.append(r)
    alive.sort(key=lambda r: (r["url"]))
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "reports", "httpx_sweep.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(alive, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

    lines = [f"SWEEP — {len(cands)} sondes, {len(alive)} vivantes sur {len(host_list)} hôtes.", ""]
    for r in alive:
        tags = f" [{', '.join(r['tech'])}]" if r["tech"] else ""
        title = f" — {r['title']}" if r["title"] else ""
        lines.append(f"{r['status']} {r['url']}{title}{tags} ({r['len']}B, {r['dt']}s)")
    if not alive:
        lines.append("Aucune sonde vivante — hôtes down ou filtrés.")
    return "\n".join(lines)
