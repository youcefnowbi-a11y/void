"""TOOL: cve_intel - NVD recent CVEs + CISA KEV exploited-in-wild."""
import json, urllib.request, time
from tools import register

UAH = {"User-Agent": "Mozilla/5.0"}

def _get(url, timeout=40):
    rq = urllib.request.Request(url, headers=UAH)
    try:
        return urllib.request.urlopen(rq, timeout=timeout).read()
    except Exception as ex:
        return b""

@register(name="nvd_search",
          desc="Search NVD for CVEs by keyword, newest first, with severity and references.",
          params={"type":"object","properties":{
              "keyword":{"type":"string"},"results":{"type":"integer"},
              "pub_start":{"type":"string","description":"YYYY-MM-DD"}},
              "required":["keyword"]})
def nvd_search(keyword, results=25, pub_start=None):
    u = (f"https://services.nvd.nist.gov/rest/json/cves/2.0/"
         f"?keywordSearch={urllib.parse.quote(keyword)}&resultsPerPage={int(results)}")
    if pub_start:
        u += f"&pubStartDate={pub_start}T00:00:00.000"
    raw = _get(u)
    if not raw: return "NVD unreachable"
    try:
        data = json.loads(raw)
        rows = []
        for v in data.get("vulnerabilities", []):
            c = v["cve"]
            desc = next((d["value"] for d in c["descriptions"] if d["lang"]=="en"), "")[:180]
            sev = ""
            for k in ("cvssMetricV31","cvssMetricV30","cvssMetricV2"):
                if k in c.get("metrics", {}):
                    sev = str(c["metrics"][k][0]["cvssData"].get("baseScore",""))
                    break
            refs = [r_.get("url") for r_ in c.get("references", [])][:3]
            rows.append({"id": c["id"], "published": c["published"][:10], "sev": sev, "desc": desc, "refs": refs})
        rows.sort(key=lambda x: x["published"], reverse=True)
        return json.dumps({"total": data.get("totalResults"), "cves": rows}, ensure_ascii=False, indent=1)
    except Exception as ex:
        return f"parse err: {ex}"

import urllib.parse

@register(name="cisa_kev",
          desc="CISA Known Exploited Vulnerabilities - filter by keyword. These are confirmed exploited-in-the-wild.",
          params={"type":"object","properties":{"keyword":{"type":"string"}},"required":["keyword"]})
def cisa_kev(keyword):
    raw = _get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    if not raw: return "KEV unreachable"
    kev = json.loads(raw).get("vulnerabilities", [])
    kwl = keyword.lower()
    hits = [v for v in kev if kwl in (v.get("vendorProject","")+v.get("product","")+v.get("shortDesc","")).lower()]
    hits.sort(key=lambda v: v.get("dateAdded",""), reverse=True)
    return json.dumps({"total_kev": len(kev), "matches": len(hits),
                       "list": [{"cve": v.get("cveID"), "added": v.get("dateAdded"),
                                 "vendor": v.get("vendorProject"), "product": v.get("product"),
                                 "desc": v.get("shortDesc","")[:150]} for v in hits[:25]]},
                        ensure_ascii=False, indent=1)
