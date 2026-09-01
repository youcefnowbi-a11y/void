"""VOIDFORGE :: WEB SEARCH — the strategist's eyes on the open web.

The war room is a conversation, and conversations need facts. These tools
give any phase (chat counsel, plan recon, strike agent) general-purpose
web search + page reading — independent of the offensive recon battery.

Both tools are pure stdlib (urllib), no API keys, best-effort against
DuckDuckGo's HTML endpoints with a lite fallback.
"""
import html as _html
import json
import re
import time
import urllib.parse
import urllib.request

from tools import register

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9,fr;q=0.8"}

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _fetch(url, timeout=20):
    rq = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        return r.status, r.read().decode(errors="replace")


def _clean(text):
    return _WS.sub(" ", _TAG.sub("", text)).strip()


def _uddg_decode(href):
    """DDG wraps result URLs in a /l/?uddg=<encoded> redirect — unwrap."""
    if "uddg=" in href:
        try:
            q = urllib.parse.urlparse(href if href.startswith("http") else "https:" + href).query
            u = urllib.parse.parse_qs(q).get("uddg", [None])[0]
            if u:
                return urllib.parse.unquote(u)
        except Exception:
            pass
    return href


def _parse_ddg_html(body, max_results):
    """Parse the full HTML endpoint: result__a anchors + result__snippet blocks."""
    out = []
    # split into result blocks to keep title/snippet pairing honest
    blocks = re.split(r'class="result\b', body)[1:]
    for b in blocks[: max_results * 2]:
        m = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        url = _uddg_decode(_html.unescape(m.group(1)))
        title = _clean(m.group(2))
        if not title or not url.startswith("http"):
            continue
        snip = ""
        ms = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', b, re.S)
        if ms:
            snip = _clean(ms.group(1))[:280]
        out.append({"title": title[:160], "url": url, "snippet": snip})
        if len(out) >= max_results:
            break
    return out


def _parse_ddg_lite(body, max_results):
    """Fallback: the lite endpoint renders a flat table of result-link anchors."""
    out = []
    for m in re.finditer(r"<a[^>]+href=\"(http[^\"]+)\"[^>]*class='result-link'[^>]*>(.*?)</a>", body, re.S):
        title = _clean(m.group(2))
        url = _uddg_decode(_html.unescape(m.group(1)))
        if title and url.startswith("http"):
            out.append({"title": title[:160], "url": url, "snippet": ""})
        if len(out) >= max_results:
            break
    # lite snippets: td.result-snippet follows each link row
    if out:
        snips = [_clean(s)[:280] for s in re.findall(r"class='result-snippet'[^>]*>(.*?)</td>", body, re.S)]
        for i, s in enumerate(snips[: len(out)]):
            if s:
                out[i]["snippet"] = s
    return out


@register(name="web_search",
          desc="General web search via DuckDuckGo (no API key): returns title/url/snippet results for any query. For research during discussion and recon context.",
          params={"type": "object", "properties": {
              "query": {"type": "string", "description": "Search query"},
              "max_results": {"type": "integer", "description": "Max results (default 8, max 15)"},
              "region": {"type": "string", "description": "Region hint, e.g. fr-fr, en-us (default wt-wt)"},
          }, "required": ["query"]})
def web_search(query, max_results=8, region="wt-wt"):
    query = (query or "").strip()
    if not query:
        return json.dumps({"error": "query vide"})
    max_results = max(1, min(int(max_results or 8), 15))
    q = urllib.parse.quote(query)
    errors = []
    # attempt 1: full HTML endpoint (rich snippets)
    try:
        st, body = _fetch(f"https://html.duckduckgo.com/html/?q={q}&kl={region}")
        if st == 200:
            res = _parse_ddg_html(body, max_results)
            if res:
                return json.dumps({"query": query, "results": res, "source": "ddg-html",
                                   "count": len(res)}, ensure_ascii=False, indent=1)
            errors.append(f"html endpoint: 200 but 0 parsed (captcha probable, len={len(body)})")
        else:
            errors.append(f"html endpoint: HTTP {st}")
    except Exception as ex:
        errors.append(f"html endpoint: {type(ex).__name__}: {str(ex)[:120]}")
    time.sleep(1.2)
    # attempt 2: lite endpoint
    try:
        st, body = _fetch(f"https://lite.duckduckgo.com/lite/?q={q}&kl={region}")
        if st == 200:
            res = _parse_ddg_lite(body, max_results)
            if res:
                return json.dumps({"query": query, "results": res, "source": "ddg-lite",
                                   "count": len(res)}, ensure_ascii=False, indent=1)
            errors.append(f"lite endpoint: 200 but 0 parsed (len={len(body)})")
        else:
            errors.append(f"lite endpoint: HTTP {st}")
    except Exception as ex:
        errors.append(f"lite endpoint: {type(ex).__name__}: {str(ex)[:120]}")
    return json.dumps({"query": query, "results": [], "error": "recherche indisponible",
                       "attempts": errors}, ensure_ascii=False, indent=1)


@register(name="web_read",
          desc="Fetch a web page and return its readable text (scripts/styles stripped, HTML tags removed). For reading sources found via web_search during discussion.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "Page URL to read"},
              "max_chars": {"type": "integer", "description": "Max characters of extracted text (default 6000, max 20000)"},
          }, "required": ["url"]})
def web_read(url, max_chars=6000):
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return json.dumps({"error": "URL invalide (http/https requis)"})
    max_chars = max(500, min(int(max_chars or 6000), 20000))
    try:
        st, body = _fetch(url, timeout=25)
    except Exception as ex:
        return json.dumps({"url": url, "error": f"{type(ex).__name__}: {str(ex)[:160]}"})
    # strip non-content elements BEFORE tag removal
    body = re.sub(r"(?is)<(script|style|noscript|svg|iframe|form)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>", "\n", body)
    text = _html.unescape(_TAG.sub(" ", body))
    lines = [_WS.sub(" ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    title = ""
    mt = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I) or \
         re.search(r"og:title[\"']?\s*content=[\"']([^\"']+)", body, re.I)
    if mt:
        title = _clean(mt.group(1))[:160]
    return json.dumps({"url": url, "status": st, "title": title,
                       "text": text[:max_chars],
                       "truncated": len(text) > max_chars}, ensure_ascii=False, indent=1)
