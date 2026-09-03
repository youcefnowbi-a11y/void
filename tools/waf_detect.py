"""TOOL: waf_detect - Web Application Firewall (WAF) detection and fingerprinting."""
import json, urllib.request, urllib.error, urllib.parse, re
from tools import register

WAF_SIGNATURES = {
    "Cloudflare": {
        "headers": ["cf-ray", "cf-cache-status"],
        "server": ["cloudflare"],
        "cookies": ["__cfduid", "cf_clearance"],
        "body": ["cloudflare", "ray id:", "attention required! | cloudflare"]
    },
    "AWS WAF": {
        "headers": ["x-amzn-requestid", "x-amz-cf-id", "x-amzn-waf-action"],
        "server": ["awselb", "amazon"],
        "cookies": ["aws-waf-token"],
        "body": ["awswaf", "amazon cloudfront"]
    },
    "Akamai": {
        "headers": ["x-akamai-transformed", "akamai-origin-hop", "x-akamai-session-id"],
        "server": ["akamaighost", "akamai"],
        "cookies": ["ak_bmsc", "bm_sv"],
        "body": ["akamai", "reference #"]
    },
    "Sucuri": {
        "headers": ["x-sucuri-id", "x-sucuri-cache"],
        "server": ["sucuri"],
        "cookies": ["sucuri_cloudproxy"],
        "body": ["sucuri website firewall", "cloudproxy"]
    },
    "Imperva/Incapsula": {
        "headers": ["x-iinfo", "x-cdn"],
        "server": ["incapsula"],
        "cookies": ["incap_ses", "visid_incap"],
        "body": ["incapsula incident", "imperva", "_incapsula_resource"]
    },
    "ModSecurity": {
        "headers": [],
        "server": ["mod_security", "modsecurity", "owasp_modsecurity"],
        "cookies": [],
        "body": ["mod_security", "modsecurity", "not acceptable on this server"]
    },
    "Fastly": {
        "headers": ["x-served-by", "fastly-debug-digest"],
        "server": ["fastly"],
        "cookies": [],
        "body": ["fastly"]
    }
}

SECURITY_HEADERS = [
    "Strict-Transport-Security",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Content-Security-Policy",
    "X-XSS-Protection"
]

def _fetch(url, timeout=12):
    rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            raw_cookies = resp.headers.get("Set-Cookie", "")
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, headers, raw_cookies, body
    except urllib.error.HTTPError as ex:
        headers = {k.lower(): v for k, v in ex.headers.items()}
        raw_cookies = ex.headers.get("Set-Cookie", "")
        err_body = ex.read().decode("utf-8", errors="replace")
        return ex.code, headers, raw_cookies, err_body
    except Exception as ex:
        return -1, {}, "", f"{type(ex).__name__}: {str(ex)[:100]}"

@register(
    name="waf_detect",
    desc="Detect Web Application Firewall (WAF) signatures, inspect security headers, and test probe blocking behavior.",
    params={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL to inspect (e.g. https://example.com)"}
        },
        "required": ["url"]
    }
)
def waf_detect(url):
    target_url = url.strip()
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    # Phase 1: Baseline Request & Header Analysis
    status, headers, cookies, body = _fetch(target_url)
    if status == -1:
        return json.dumps({
            "url": target_url,
            "error": "Failed to connect to target",
            "detail": body
        })

    detected_waf = "none"
    confidence = "none"
    matched_sigs = []
    waf_scores = {}

    server_val = headers.get("server", "").lower()
    x_cdn_val = headers.get("x-cdn", "").lower()
    cookies_lower = cookies.lower()
    body_lower = body.lower()

    for waf_name, sigs in WAF_SIGNATURES.items():
        score = 0
        matches = []

        # Check headers
        for h in sigs["headers"]:
            if h in headers:
                if h == "x-cdn" and "incapsula" not in x_cdn_val:
                    continue
                score += 3
                matches.append(f"header:{h}")

        # Check server header
        for s in sigs["server"]:
            if s in server_val:
                score += 3
                matches.append(f"server:{server_val}")

        # Check cookies
        for c in sigs["cookies"]:
            if c in cookies_lower:
                score += 3
                matches.append(f"cookie:{c}")

        # Check fastly special headers
        if waf_name == "Fastly":
            if "fastly" in headers.get("x-cache", "").lower() or "fastly" in headers.get("x-timer", "").lower():
                score += 2
                matches.append("header:x-cache/x-timer(fastly)")

        # Check body indicators if initial response is 403 or blocked
        if status in [403, 406, 501, 503]:
            for b in sigs["body"]:
                if b in body_lower:
                    score += 2
                    matches.append(f"body_keyword:{b}")

        if score > 0:
            waf_scores[waf_name] = {"score": score, "matches": matches}

    # Phase 2: Probe with suspicious payload
    sep = "&" if "?" in target_url else "?"
    # V13 (audit 3.4): raw <> in the URI — either an invalid request or
    # non-representative server behavior. The WAF probe must be a legal
    # request carrying an obviously-malicious encoded payload.
    _probe = urllib.parse.quote("<script>alert(1)</script>", safe="")
    probe_url = f"{target_url}{sep}test={_probe}"
    probe_status, probe_headers, probe_cookies, probe_body = _fetch(probe_url)

    block_behavior = {
        "probed_url": probe_url,
        "probe_status": probe_status,
        "blocked": False,
        "reason": "Normal response (probe not blocked)"
    }

    if probe_status in [403, 406, 418, 429, 501, 999] or (status == 200 and probe_status in [403, 406]):
        block_behavior["blocked"] = True
        block_behavior["reason"] = f"HTTP {probe_status} block on script payload"

        # Check probe body for WAF signatures if not already detected
        probe_body_lower = probe_body.lower()
        for waf_name, sigs in WAF_SIGNATURES.items():
            for b in sigs["body"]:
                if b in probe_body_lower:
                    waf_scores.setdefault(waf_name, {"score": 0, "matches": []})
                    waf_scores[waf_name]["score"] += 2
                    waf_scores[waf_name]["matches"].append(f"block_page_keyword:{b}")

    # Determine leading WAF
    if waf_scores:
        best_waf = max(waf_scores.items(), key=lambda x: x[1]["score"])
        detected_waf = best_waf[0]
        matched_sigs = best_waf[1]["matches"]
        best_score = best_waf[1]["score"]
        if best_score >= 5:
            confidence = "high"
        elif best_score >= 3:
            confidence = "medium"
        else:
            confidence = "low"

    # Phase 3: Security Headers Inspection
    sec_present = {}
    sec_missing = []

    for sh in SECURITY_HEADERS:
        sh_low = sh.lower()
        if sh_low in headers:
            sec_present[sh] = headers[sh_low]
        else:
            sec_missing.append(sh)

    return json.dumps({
        "url": target_url,
        "detected_waf": detected_waf,
        "waf_confidence": confidence,
        "matched_signatures": matched_sigs,
        "block_behavior": block_behavior,
        "security_headers": {
            "present": sec_present,
            "missing": sec_missing,
            "score": f"{len(sec_present)}/{len(SECURITY_HEADERS)} headers implemented"
        },
        "response_status": status,
        "server_header": headers.get("server", "not-disclosed")
    }, ensure_ascii=False, indent=1)
