"""TOOL: ssrf_test - SSRF detection tool."""
import json, urllib.request, urllib.error, urllib.parse, time
from tools import register

PAYLOADS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://[::1]",
    "http://169.254.169.254/latest/meta-data/",
    "http://0.0.0.0",
    "http://2130706433",
]

AWS_METADATA_KEYWORDS = [
    "ami-id",
    "instance-id",
    "local-ipv4",
    "public-ipv4",
    "security-groups",
    "instance-type",
    "iam/security-credentials",
    "ami-manifest-path",
    "reservation-id"
]

BASELINE_URL = "http://example.com"

def _send_req(url, timeout=10):
    rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            dt = time.time() - t0
            return resp.status, body, round(dt, 3)
    except urllib.error.HTTPError as ex:
        dt = time.time() - t0
        err_body = ex.read().decode("utf-8", errors="replace")
        return ex.code, err_body, round(dt, 3)
    except Exception as ex:
        dt = time.time() - t0
        return -1, f"{type(ex).__name__}: {str(ex)[:100]}", round(dt, 3)

@register(
    name="ssrf_probe",
    desc="Probe URL parameters for Server-Side Request Forgery (SSRF) against loopback, cloud metadata, and alternate IP representations.",
    params={
        "type": "object",
        "properties": {
            "url_template": {
                "type": "string",
                "description": "Target URL with {PAYLOAD} placeholder (e.g. https://target.com/proxy?url={PAYLOAD})"
            },
            "timeout": {
                "type": "integer",
                "default": 10,
                "description": "Request timeout in seconds (default: 10)"
            }
        },
        "required": ["url_template"]
    }
)
def ssrf_probe(url_template, timeout=10):
    if "{PAYLOAD}" not in url_template:
        return json.dumps({
            "error": "url_template must contain the {PAYLOAD} placeholder",
            "url_template": url_template
        })

    # Baseline request with neutral external URL
    base_url = url_template.replace("{PAYLOAD}", urllib.parse.quote(BASELINE_URL, safe=""))
    base_status, base_body, base_time = _send_req(base_url, timeout=timeout)
    base_len = len(base_body)

    tested_results = []
    suspected_vectors = []

    for payload in PAYLOADS:
        target_url = url_template.replace("{PAYLOAD}", urllib.parse.quote(payload, safe=""))
        status, body, dt = _send_req(target_url, timeout=timeout)
        body_len = len(body)
        signals = []

        # Check status code diff
        if status != -1 and status != base_status:
            signals.append(f"status_diff({status} vs baseline {base_status})")

        # Check response time anomaly (internal target responds significantly faster or slower)
        if base_time > 0:
            if dt < (base_time * 0.4) and (base_time - dt) > 0.5:
                signals.append(f"fast_response_anomaly({dt}s vs baseline {base_time}s)")
            elif dt > (base_time * 2.5) and dt > 3.0:
                signals.append(f"slow_response_anomaly({dt}s vs baseline {base_time}s)")

        # Check body length diff
        if abs(body_len - base_len) > 50 and status != -1:
            signals.append(f"body_length_diff({body_len} vs baseline {base_len})")

        # Check AWS metadata leaks
        body_lower = body.lower()
        matched_meta = [kw for kw in AWS_METADATA_KEYWORDS if kw in body_lower]
        if matched_meta:
            signals.append(f"cloud_metadata_match({','.join(matched_meta)})")

        res = {
            "payload": payload,
            "status": status,
            "response_time_s": dt,
            "body_length": body_len,
            "signals": signals,
            "body_sample": body[:200] if signals else ""
        }
        tested_results.append(res)

        if signals:
            suspected_vectors.append({
                "payload": payload,
                "signals": signals
            })

    return json.dumps({
        "url_template": url_template,
        "baseline": {
            "payload": BASELINE_URL,
            "status": base_status,
            "response_time_s": base_time,
            "body_length": base_len
        },
        "tested_payloads": tested_results,
        "signals_found": len(suspected_vectors),
        "suspected_ssrf_vectors": suspected_vectors,
        "verdict": "potential SSRF signals detected" if suspected_vectors else "no obvious SSRF indicators"
    }, ensure_ascii=False, indent=1)
