"""TOOL: web_recon - target fingerprinting + endpoint existence oracle."""
import re, json
from tools import register
from tools._transport import fetch as _fetch

def _get(url, headers=None, timeout=15):
    r = _fetch(url, headers=headers, timeout=timeout)
    return r.get("status", -1), (r.get("body") or "")[:3000], r.get("headers", {})

@register(name="web_fingerprint",
          desc="Fingerprint a target: server headers, tech stack, framework hints, robots/sitemap.",
          params={"type":"object","properties":{"url":{"type":"string"}},"required":["url"]})
def web_fingerprint(url):
    url = url.rstrip("/")
    out = {}
    st, b, hdrs = _get(url)
    out["root_status"] = st
    for pat, name in [(r"wp-content","WordPress"),(r"shopify","Shopify"),(r"__next|next\/static","Next.js"),
                      (r"cdn\.shopify","ShopifyCDN"),(r"wixstatic","Wix"),(r"_nuxt","Nuxt"),
                      (r"supabase","Supabase"),(r"firebase","Firebase"),(r"cloudflare","Cloudflare")]:
        if re.search(pat, b, re.I): out.setdefault("tech", []).append(name)
    title = re.search(r"<title>(.*?)</title>", b, re.S|re.I)
    out["title"] = title.group(1).strip()[:120] if title else ""
    scripts = re.findall(r'src="(/[^"]+\.js)"', b)[:20]
    out["local_scripts"] = scripts

    hdrs_lower = {k.lower(): v for k, v in hdrs.items()}

    # 1. Server headers
    server_info = {}
    for h in ["Server", "X-Powered-By", "X-AspNet-Version", "X-Generator"]:
        if h.lower() in hdrs_lower:
            server_info[h] = hdrs_lower[h.lower()]
    out["server_info"] = server_info

    # 2. WAF detection from headers
    waf_hint = []
    if "cf-ray" in hdrs_lower or "cloudflare" in hdrs_lower.get("server", "").lower():
        waf_hint.append("Cloudflare")
    if "x-amzn-requestid" in hdrs_lower:
        waf_hint.append("AWS")
    if "x-akamai-transformed" in hdrs_lower:
        waf_hint.append("Akamai")
    if "x-sucuri-id" in hdrs_lower:
        waf_hint.append("Sucuri")
    out["waf_hint"] = waf_hint

    # 3. CDN detection
    cdn_hint = []
    if "x-served-by" in hdrs_lower:
        cdn_hint.append("Fastly")
    if "x-amz-cf-id" in hdrs_lower:
        cdn_hint.append("CloudFront")
    if "cf-ray" in hdrs_lower:
        cdn_hint.append("Cloudflare")
    out["cdn_hint"] = cdn_hint

    # 4. Security headers audit
    sec_hdrs = ["strict-transport-security", "x-frame-options", "x-content-type-options", "content-security-policy", "x-xss-protection"]
    out["security_headers"] = {h: (h in hdrs_lower) for h in sec_hdrs}

    st2, b2, _ = _get(url + "/robots.txt")
    out["robots"] = b2[:500] if st2 == 200 else None
    return json.dumps(out, ensure_ascii=False, indent=1)

@register(name="endpoint_oracle",
          desc="Probe endpoint paths against a base URL; classify status codes (401=exists-locked, 404=missing, 200=open). Great for API mapping.",
          params={"type":"object","properties":{
              "base":{"type":"string"},"paths":{"type":"array","items":{"type":"string"}},
              "bearer":{"type":"string"}},
              "required":["base","paths"]})
def endpoint_oracle(base, paths, bearer=None):
    h = {"User-Agent": "Mozilla/5.0"}
    if bearer: h["Authorization"] = f"Bearer {bearer}"
    results = []
    for p in paths:
        target = base.rstrip("/") + "/" + p.lstrip("/")
        st, b, _ = _get(target, headers=h, timeout=12)
        if st == 200:
            results.append({"path": p, "status": st, "body": b[:150],
                            "verdict": "OPEN"})
        elif st > 0:
            label = {401: "EXISTS-LOCKED", 403: "EXISTS-FORBIDDEN", 404: "missing"}.get(st, "?")
            results.append({"path": p, "status": st, "verdict": label})
        else:
            results.append({"path": p, "status": -1, "err": b[:60]})
    return json.dumps(results, ensure_ascii=False, indent=1)
