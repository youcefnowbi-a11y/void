"""VOIDFORGE :: WALL BREAKER — the intel reflex.

When the mission brain hits a wall (WAF, auth wall, blind filtering, unknown
stack), this engine goes OUT: web + exploit-db + NVD + CISA KEV, hunting for
known CVEs, exploits and bypass techniques for the exact tech or something
close. It returns COMPRESSED intel with source URLs — ammunition, not a
lecture — and stores it in reports/breaker_cache.json so the next mission
against the same wall starts informed.

The tool call is one decision: wall identified -> seek outside knowledge ->
return with ordnance. Exactly how a real operator works.
"""
import json
import os
import re
import time
from urllib.parse import quote_plus

from tools import register
from tools._exploit_lib import paced_send

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "reports", "breaker_cache.json")
_RAW = "https://raw.githubusercontent.com/gonzalezreal/exploit-db-search/main/exploits_files.json"


def _cache_load():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _cache_store(key, entry):
    data = _cache_load()
    data[key] = {**entry, "ts": round(time.time(), 3)}
    # R3-6: éviction TTL 30j + cap 100 clés AVANT écriture — le cache ne
    # grossit plus à l'infini, et tmp+os.replace = pas de fichier à moitié écrit
    now = time.time()
    data = {k: v for k, v in data.items() if now - (v.get("ts") or 0) < 30 * 86400}
    if len(data) > 100:
        keep = sorted(data.items(), key=lambda kv: kv[1].get("ts") or 0, reverse=True)[:100]
        data = dict(keep)
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CACHE_PATH)
    except Exception:
        pass


def _dedupe(items, kfield="url"):
    out, seen = [], set()
    for it in items:
        k = it.get(kfield) or it.get("title")
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _web_leg(query, max_results=6):
    """Web search leg via the registered web_search tool (DDG)."""
    import tools as _t
    try:
        raw = _t.execute("web_search", {"query": query, "max_results": max_results})
        data = json.loads(raw)
        return [{"title": r.get("title", ""), "url": r.get("url", ""),
                 "snip": (r.get("snippet") or "")[:180]}
                for r in data.get("results", [])]
    except Exception as ex:
        # R3-7: une jambe qui throw doit se voir, pas ressembler a "rien trouvé"
        return [{"title": f"[leg-failed] web_search: {type(ex).__name__}", "url": ""}]


def _read_leg(url, max_chars=3000):
    """Fetch a promising page and keep the CVE/exploit-shaped lines."""
    import tools as _t
    try:
        raw = _t.execute("web_read", {"url": url, "max_chars": max_chars})
        data = json.loads(raw)
        txt = data.get("content") or ""
        keep = []
        for line in txt.splitlines():
            if re.search(r"(?i)(cve-\d{4}-\d{4,}|exploit|payload|bypass|poc|version\b)",
                         line) and len(line.strip()) > 15:
                keep.append(line.strip()[:200])
            if len(keep) >= 8:
                break
        return keep
    except Exception as ex:
        # R3-7: même honnêteté que _web_leg sur la jambe lecture
        return [{"title": f"[leg-failed] web_read: {type(ex).__name__}", "url": ""}]


def _edbid_leg(tech):
    """Exploit-DB index leg: filter the big index for the tech, newest first."""
    try:
        st, body, _ = paced_send(_RAW, timeout=30)
        if st != 200:
            return []
        idx = json.loads(body)
        rx = re.compile(re.escape(tech), re.I)
        hits = []
        for e in idx if isinstance(idx, list) else []:
            desc = str(e.get("description") or e.get("d") or "")
            if rx.search(desc):
                hits.append({
                    "title": f"[EDB-{e.get('id', '?')}] {desc[:120]}",
                    "url": f"https://www.exploit-db.com/exploits/{e.get('id')}",
                    "snip": f"{e.get('date', '')} {e.get('type', '')} {e.get('platform', '')}".strip(),
                    "year": str(e.get("date", ""))[:4],
                })
        hits.sort(key=lambda x: x.get("year", "0"), reverse=True)
        return hits[:8]
    except Exception as ex:
        # R3-7: jambe EDB visible en échec, pas muette
        return [{"title": f"[leg-failed] edb_index: {type(ex).__name__}", "url": ""}]


def _nvd_leg(tech):
    """NVD leg via the registered nvd_search tool."""
    import tools as _t
    try:
        raw = _t.execute("nvd_search", {"keyword": tech})
        data = json.loads(raw) if isinstance(raw, str) else raw
        out = []
        items = data.get("vulns") or data.get("results") or []
        for v in items[:8]:
            out.append({"title": f"[NVD] {v.get('id', '?')} — {(v.get('summary') or v.get('description') or '')[:110]}",
                        "url": v.get("url") or f"https://nvd.nist.gov/vuln/detail/{v.get('id', '')}",
                        "snip": f"cvss={v.get('cvss', '?')} {v.get('published', '')}".strip()})
        return out
    except Exception as ex:
        # R3-7: jambe NVD visible en échec, pas muette
        return [{"title": f"[leg-failed] nvd: {type(ex).__name__}", "url": ""}]


def breaker_cache(query=None):
    """Sub-tool: read cached intel for a wall signature."""
    data = _cache_load()
    if not query:
        if not data:
            return "CACHE VIDE — aucune intelligence de mur stockée."
        lines = [f"CACHE BREAKER — {len(data)} entrées:"]
        for k, v in list(data.items())[-15:]:
            n = len(v.get("findings", []))
            lines.append(f"- {k} ({time.strftime('%Y-%m-%d', time.localtime(v['ts']))}, {n} findings)")
        return "\n".join(lines)
    low = query.lower()
    hits = [(k, v) for k, v in data.items() if low in k.lower()]
    if not hits:
        return f"CACHE MISS pour '{query}' — lance wall_breaker sur la cible."
    lines = [f"CACHE BREAKER — '{query}':"]
    for k, v in hits[:5]:
        for fnd in v.get("findings", [])[:6]:
            lines.append(f"- {fnd.get('title', '')[:120]}")
            if fnd.get("snip"):
                lines.append(f"  {fnd['snip'][:160]}")
            if fnd.get("url"):
                lines.append(f"  {fnd['url']}")
    return "\n".join(lines)


@register(name="wall_breaker",
          desc="INTEL REFLEX: when blocked by a wall (WAF, auth, unknown stack, "
               "blind filtering) — search web + Exploit-DB + NVD/KEV for known "
               "CVEs, exploits and bypasses for that exact tech or close "
               "relatives, and return COMPRESSED ammunition with sources. "
               "op='break' hunts; op='cache' reads stored intel.",
          params={"type": "object", "properties": {
              "op": {"type": "string", "enum": ["break", "cache"], "default": "break"},
              "tech": {"type": "string", "description": "the tech/wall: 'cloudflare WAF', 'Apache 2.4.49', 'jwt none alg', 'api rate limit'"},
              "context": {"type": "string", "description": "one line of what you were trying when blocked"},
              "deep": {"type": "boolean", "description": "read top pages for CVE-shaped lines (slower, richer)"},
              "refresh": {"type": "boolean", "description": "re-hunt fresh intel: skip the 7-day cache read and OVERWRITE the cached entry with new findings (default false)"},
              "query": {"type": "string", "description": "cache lookup key (op=cache only)"}},
              "required": []},
          danger="safe")
def wall_breaker(op="break", tech=None, context=None, deep=False, query=None, refresh=False):
    if (op or "break") == "cache":
        return breaker_cache(query)

    if not tech:
        return "TOOL ERROR [NO_TECH]: décris le mur — 'cloudflare WAF', 'Apache 2.4.49', 'jwt none alg'..."
    tech = str(tech)[:80]

    # cache hit = instant ammunition from a previous mission
    # (C-WB1 : refresh=True saute la lecture — « relance op=break » était un
    # no-op puisque op=break EST le chemin caché ; le store final écrase.)
    key = tech.lower()
    cached = None if refresh else _cache_load().get(key)
    if cached and (time.time() - cached.get("ts", 0)) < 7 * 86400:
        fnd = cached.get("findings", [])
        lines = [f"BREAKER CACHE HIT — '{tech}' ({len(fnd)} findings, mission précédente):"]
        for f in fnd[:8]:
            lines.append(f"- {f.get('title', '')[:120]}")
            if f.get("url"):
                lines.append(f"  {f['url']}")
        lines.append("\n(Cache ≤7j — si la surface a changé, relance op=break avec refresh=true.)")
        return "\n".join(lines)

    ctx = f" — contexte: {context}" if context else ""
    findings = []
    # leg 1: web search, several angles
    for q in (f"{tech} bypass technique exploit",
              f"{tech} known vulnerabilities CVE exploit",
              f"{tech} pentest trick绕 bypass poc"):
        findings += _web_leg(q, 5)
    # leg 2: exploit-db index
    edb_tech = re.sub(r"(?i)\b(waf|wall|filter|bypass|technique|exploit)\b", "", tech).strip() or tech
    findings += _edbid_leg(edb_tech)
    # leg 3: NVD
    findings += _nvd_leg(edb_tech)
    # leg 4 (optional): read the top promising pages
    if deep:
        for r in _dedupe(findings)[:3]:
            for l in _read_leg(r["url"]):
                if isinstance(l, dict):
                    # finding [leg-failed] déjà structurée — pas de repr dict
                    findings.append(l)
                else:
                    findings += [{"title": f"[deep:{r['url'][:60]}] {l}",
                                  "url": r["url"], "snip": "page-extracted"}]

    findings = _dedupe(findings)
    if not findings:
        return (f"BREAKER — aucun known exploit trouvé pour '{tech}'. "
                "Le mur est probablement niche: documente la technique dans le rapport final "
                "(elle a de la valeur).")
    entry = {"findings": findings[:14]}
    _cache_store(key, entry)
    lines = [f"BREAKER — intel compressée pour '{tech}'{ctx} ({len(findings)} findings):", ""]
    for f in findings[:14]:
        lines.append(f"- {f.get('title', '')[:130]}")
        if f.get("snip"):
            lines.append(f"    {f['snip'][:160]}")
        if f.get("url"):
            lines.append(f"    {f['url']}")
    lines.append("\nUSE: pioche ces techniques/exploits dans les prochaines étapes — "
                 "chaque finding a sa source.")
    return "\n".join(lines)
