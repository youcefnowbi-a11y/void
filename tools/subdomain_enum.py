"""TOOL: subdomain_enum - certificate transparency (crt.sh) + hackertarget host search."""
import json, urllib.request, urllib.parse, re, time
from tools import register

UA = {"User-Agent": "Mozilla/5.0"}

def _get(url, timeout=30):
    rq = urllib.request.Request(url, headers=UA)
    try:
        return urllib.request.urlopen(rq, timeout=timeout).read().decode(errors="replace")
    except Exception as ex:
        return f"__ERR__ {type(ex).__name__}: {str(ex)[:70]}"

@register(name="subdomain_enum",
          desc="Enumerate subdomains of a domain via certificate transparency logs (crt.sh) and hackertarget host search. No keys needed.",
          params={"type":"object","properties":{
              "domain":{"type":"string"},"identity_only":{"type":"boolean"}},
              "required":["domain"]})
def subdomain_enum(domain, identity_only=True):
    domain = domain.lower().strip()
    subs = set()
    # crt.sh
    q = f"%.{domain}" if identity_only else domain
    raw = _get(f"https://crt.sh/?q={urllib.parse.quote(q)}&output=json", timeout=45)
    if not raw.startswith("__ERR__"):
        try:
            entries = json.loads(raw)
            for e in entries:
                for n in str(e.get("name_value", "")).split("\n"):
                    n = n.strip().lstrip("*.").lower()
                    if n.endswith(domain):
                        subs.add(n)
        except Exception:
            pass
    time.sleep(1)
    # hackertarget
    raw2 = _get(f"https://api.hackertarget.com/hostsearch/?q={domain}")
    if not raw2.startswith("__ERR__") and "," in raw2:
        for line in raw2.strip().split("\n"):
            host = line.split(",")[0].strip().lower()
            if host.endswith(domain):
                subs.add(host)
    return json.dumps({"domain": domain, "subdomains_found": len(subs),
                       "subdomains": sorted(subs)[:150]}, ensure_ascii=False, indent=1)

@register(name="ip_intel",
          desc="IP intelligence: geo/ASN (ip-api) + reverse IP pointer (hackertarget).",
          params={"type":"object","properties":{"ip_or_host":{"type":"string"}},
                  "required":["ip_or_host"]})
def ip_intel(ip_or_host):
    out = {}
    geo = _get(f"http://ip-api.com/json/{ip_or_host}")
    if not geo.startswith("__ERR__"):
        try: out["geo"] = json.loads(geo)
        except Exception: out["geo_raw"] = geo[:200]
    rev = _get(f"https://api.hackertarget.com/reverseiplookup/?q={ip_or_host}")
    if not rev.startswith("__ERR__"):
        hosts = [h for h in rev.strip().split("\n") if h and "error" not in h.lower()][:50]
        out["reverse_hosts"] = hosts
    return json.dumps(out, ensure_ascii=False, indent=1)
