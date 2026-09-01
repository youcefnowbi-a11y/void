"""TOOL: wayback_miner - historical URL mining via Wayback CDX API."""
import json, urllib.request, urllib.parse, re
from tools import register

UA = {"User-Agent": "Mozilla/5.0"}

@register(name="wayback_urls",
          desc="Mine ALL historical URLs of a domain from Wayback Machine CDX. Endpoint discovery goldmine: old APIs, removed pages, forgotten params.",
          params={"type":"object","properties":{
              "domain":{"type":"string"},
              "filter_ext":{"type":"string","description":"e.g. php,js,json — filter to extension"},
              "collapse":{"type":"boolean"}},
              "required":["domain"]})
def wayback_urls(domain, filter_ext=None, collapse=True):
    domain = domain.lower().replace("https://", "").replace("http://", "").rstrip("/")
    url = (f"http://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=text"
           f"&fl=original,timestamp,statuscode&collapse=urlkey&limit=3000")
    raw = ""
    for attempt in range(3):
        try:
            rq = urllib.request.Request(url, headers=UA)
            raw = urllib.request.urlopen(rq, timeout=120).read().decode(errors="replace")
            break
        except Exception as ex:
            if attempt == 2:
                return json.dumps({"domain": domain, "error": f"CDX unreachable after 3 tries: {str(ex)[:80]}"})
    urls, with_status = [], []
    seen = set()
    for line in raw.strip().split("\n"):
        parts = line.split(" ")
        if len(parts) < 3: continue
        original, ts, code = parts[0], parts[1], parts[2]
        if filter_ext and not original.lower().endswith("." + filter_ext.lstrip(".")):
            continue
        if original not in seen:
            seen.add(original)
            urls.append(original)
            with_status.append({"url": original[:180], "archived": ts[:8], "status": code})
    # classify
    interesting = [u for u in urls if re.search(
        r"api|admin|config|backup|\.env|token|key|debug|test|old|beta|internal|rpc|auth", u, re.I)]
    return json.dumps({"domain": domain, "total_unique": len(urls),
                       "interesting": interesting[:50],
                       "sample_with_dates": with_status[:40]},
                      ensure_ascii=False, indent=1)
