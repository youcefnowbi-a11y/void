"""TOOL: js_mine v2 - mine JS bundles for endpoints, secrets, routes, tables.

v2 additions:
  - source maps: fetches <bundle>.map and mines sourcesContent (original code!)
  - chunk graph: auto-enqueues same-origin chunk URLs discovered in bundles
  - hardened transport everywhere (DoH fallback, cache, backoff)
"""
import os, re, json
from tools import register
from tools._transport import fetch

PAT = {
    "table_calls": re.compile(r'\.from\(\s*["\']([A-Za-z0-9_]+)["\']'),
    "rpc_calls": re.compile(r'\.rpc\(\s*["\']([A-Za-z0-9_]+)["\']'),
    "routes": re.compile(r'path:\s*["\'](/[a-zA-Z0-9_\-/:.]*)["\']'),
    "api_urls": re.compile(r'https?://[a-zA-Z0-9\.\-]+\.[a-z]{2,10}[a-zA-Z0-9/\-_.]*'),
    "secrets": re.compile(r'["\']((?:sb_|sk_|pk_|whsec_|AIza|xoxb-|ghp_|eyJhbGci)[A-Za-z0-9_\-.]{12,})["\']'),
    "env_assign": re.compile(r'([A-Z][A-Z0-9_]{5,30})\s*[:=]\s*["\']([^"\']{8,100})["\']'),
    "supabase_refs": re.compile(r'https://([a-z0-9]{20})\.supabase\.co'),
    # Full JWT (header.payload.signature) — no quote requirement: catches tokens
    # built via concatenation or sitting bare in minified code.
    "jwt_tokens": re.compile(r'eyJhbGci[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*'),
}

# V9: chunk hashes — webpack (name-8h.js) AND Vite (name.b7a3ef12.js, dot
# separator, 8 hex) AND 16-char hashes (long-hash webpack builds).
_CHUNK_RE = re.compile(r'["\'](?:\./)?((?:[\w\-]+/)*[\w\-]+[.\-][A-Za-z0-9_\-]{8,16}\.js)["\']')

# JWTs/anon keys run 200-400 chars — a flat 120-char cap amputated them mid-claim.
_CAP = {"secrets": 600, "jwt_tokens": 600, "api_urls": 200}


def _mine_text(src):
    out = {}
    for name, pat in PAT.items():
        vals = set()
        for m in pat.finditer(src):
            v = (m.group(1) if m.lastindex else m.group(0))[:_CAP.get(name, 120)]
            vals.add(v)
        out[name] = sorted(vals)[:40]
    return out


def _chunk_urls(src, base):
    from urllib.parse import urljoin
    urls = set()
    for m in _CHUNK_RE.finditer(src):
        u = urljoin(base if base.endswith("/") else base.rsplit("/", 1)[0] + "/", m.group(1))
        urls.add(u)
    return sorted(urls)


def _mine_url(url, depth=0, _seen=None):
    """Mine one bundle + its source map; return (mined_dict, chunk_urls)."""
    _seen = _seen if _seen is not None else set()
    r = fetch(url, timeout=40)
    if r["status"] != 200:
        return {"err": f"HTTP {r['status']}"}, []
    src = r["body"]
    m = _mine_text(src)

    # source map: original pre-minification code often holds cleaner secrets
    sm = fetch(url + ".map", timeout=30)
    if sm["status"] == 200:
        try:
            mp = json.loads(sm["body"])
            contents = mp.get("sourcesContent") or []
            joined = "\n".join(c for c in contents if c)[:300000]
            if joined:
                m["source_map"] = {"file": mp.get("file"), "sources": mp.get("sources", [])[:20],
                                   **{k: v for k, v in _mine_text(joined).items() if v}}
        except Exception:
            pass

    chunks = _chunk_urls(src, url) if depth == 0 else []
    return {"size": len(src), **m}, chunks


@register(name="js_mine_url",
          desc="Mine a JS bundle: endpoints, secrets, routes, tables, full JWTs, source-map original code, discovered chunks.",
          params={"type": "object", "properties": {"url": {"type": "string"}},
                  "required": ["url"]})
def js_mine_url(url):
    from core.blackboard import observe
    mined, chunks = _mine_url(url)
    out = {"url": url, **mined, "chunks_discovered": chunks[:12]}
    observe("js_mine_url", json.dumps(out)[:40000])
    return _safe_json(out)


def _safe_json(obj, cap=20000):
    """V3 (audit 1.3): slicing a serialized JSON string mid-key produces
    INVALID JSON the model can't parse. Elide whole list ENTRIES instead:
    keep the head of every list, drop the middle, mark the truncation."""
    import json as _j
    def _elide(o):
        if isinstance(o, dict):
            return {k: _elide(v) for k, v in o.items()}
        if isinstance(o, list):
            if len(o) > 12:
                return _elide(o[:10]) + [f"…+{len(o) - 10} more elided"]
            return [_elide(v) for v in o]
        if isinstance(o, str) and len(o) > 600:
            return o[:600] + "…"
        return o
    s = _j.dumps(_elide(obj), ensure_ascii=False, indent=1)
    while len(s) > cap:                       # last resort: entry-level shrink
        s = _j.dumps(_elide(obj, ), ensure_ascii=False, indent=1)[:cap]
        s = s[:s.rfind("\n")] if "\n" in s else s[:cap]
        s += f"\n…[elided at {len(s)}c — full data in extractions]"
        break
    return s


@register(name="js_mine_site",
          desc="Fetch site HTML, extract all local .js bundle URLs, mine every one (with source maps), auto-follow chunk graph. Full frontend recon.",
          params={"type": "object", "properties": {"site": {"type": "string"},
                  "keyword_filter": {"type": "array", "items": {"type": "string"}}},
                  "required": ["site"]})
def js_mine_site(site, keyword_filter=None):
    from core.blackboard import observe
    site = site.rstrip("/")
    r = fetch(site, timeout=30)
    if r["status"] != 200:
        return json.dumps({"err": f"HTTP {r['status']} on {site}"})
    html = r["body"]
    # V9 (audit 2.5): double-quotes + root-anchored only — single quotes,
    # relative (assets/app.js) and CDN-absolute srcs were all invisible.
    scripts = sorted(set(
        re.findall(r"""(?:src|href)=["']([^"']+\.js[^"']*)["']""", html)
        + re.findall(r"""(?:src|href)=["']([^"']+\.mjs[^"']*)["']""", html)))
    kw = [k.lower() for k in (keyword_filter or ["admin", "vip", "pro", "premium", "secret", "pay", "auth", "api"])]
    mined, queue, seen = {}, list(scripts)[:10], set()
    depth_rounds = 0
    while queue and depth_rounds < 3:
        nxt = []
        for s in queue:
            if s in seen:
                continue
            seen.add(s)
            u = s if s.startswith("http") else site + s
            try:
                m, chunks = _mine_url(u, depth=depth_rounds, _seen=seen)
            except Exception as ex:
                mined[u] = {"err": str(ex)[:60]}
                continue
            if "err" in m:
                mined[u] = m
                continue
            interesting = any(any(k in str(v).lower() for k in kw) for v in m.values())
            mined[u] = {"size": m["size"], "interesting": interesting,
                        "tables": m["table_calls"], "rpcs": m["rpc_calls"],
                        "routes": m["routes"][:25], "secrets": m["secrets"][:8],
                        "jwts": m["jwt_tokens"][:8], "urls": m["api_urls"][:15],
                        "source_map": m.get("source_map"),
                        "chunks": len(chunks)}
            for c in chunks:
                if c not in seen and len(nxt) + len(queue) < 14:
                    nxt.append(c)
        queue = nxt
        depth_rounds += 1
    out = {"site": site, "bundles_mined": len(mined), "mined": mined}
    observe("js_mine_site", json.dumps(out)[:60000])
    return _safe_json(out, cap=22000)
