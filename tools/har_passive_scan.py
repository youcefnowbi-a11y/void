"""TOOL: har_passive_scan - passive vulnerability lens on HAR captures.

ZERO REQUESTS. Reads a browser HAR export and finds what the app leaks about
its own weaknesses: IDOR-shaped params (vary the id), JWT weaknesses (alg
none/HS256, stale exp, role claims), cookies without Secure/HttpOnly/SameSite,
missing security headers, secrets sitting in responses, and price/credit/
amount fields (server-trust candidates: race & mutation strikes). This is
where the money bugs start — no attack packets, pure reading.
"""
import base64
import json
import os
import re

from tools import register

_IDOR_RX = re.compile(
    r"(?i)(?:^|[/&?])(?:user|account|customer|order|invoice|payment|card|doc|file|"
    r"message|ticket|profile)s?_?(?:id)?[=/](\d{1,10}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)
_MONEY_RX = re.compile(r"(?i)(price|amount|credit|balance|total|discount|cost|"
                       r"subtotal|currency|wallet)")
_SECRET_RX = re.compile(
    r"(?i)(sk_live_[0-9a-z]{10,}|AKIA[0-9A-Z]{16}|(?<!-)Bearer\s+[A-Za-z0-9\-_.]{20,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key[\"':= ]+[A-Za-z0-9\-_]{16,}|"
    r"secret[\"':= ]+[A-Za-z0-9\-_]{16,}|password[\"':= ]+[^\s\"']{6,})")
_JWT_RX = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_.\-+/=]*")
_SEC_HEADERS = ("content-security-policy", "strict-transport-security",
                "x-frame-options", "x-content-type-options")


def _b64d(seg):
    try:
        pad = seg + "=" * (-len(seg) % 4)
        return json.loads(base64.urlsafe_b64decode(pad))
    except Exception:
        return {}


def _analyze_entry(entry, host_findings):
    req = entry.get("request") or {}
    resp = entry.get("response") or {}
    url = req.get("url") or ""
    qs = " ".join(str(q.get("value", "")) for q in req.get("queryString") or [])
    body = (resp.get("content") or {}).get("text") or ""
    hdrs = {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in resp.get("headers") or []}
    req_hdrs = {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in req.get("headers") or []}
    host = re.sub(r"^https?://([^/]+).*", r"\1", url) or "?"
    slot = host_findings.setdefault(host, {"idor": [], "money": [], "jwt": [],
                                           "secrets": [], "cookies": [], "headers": []})

    # 1. IDOR-shaped coordinates
    for m in _IDOR_RX.finditer(url + " " + qs):
        slot["idor"].append(f"{url.split('?')[0]}  (id={m.group(1)})")
    # 2. money fields — server-trust candidates (race/mutation strikes)
    mm = _MONEY_RX.search(url + " " + qs)
    if mm:
        slot["money"].append(url.split("?")[0] + f"  champ={mm.group(0)}")
    elif _MONEY_RX.search(body[:2000]):
        fields = sorted({m.group(0).lower() for m in _MONEY_RX.finditer(body[:2000])})[:4]
        slot["money"].append(url.split("?")[0] + f"  champs={','.join(fields)}")
    # 3. JWTs — decode, judge
    for tok in set(_JWT_RX.findall(req_hdrs.get("authorization", "") + " " + body[:4000])):
        hdr = _b64d(tok.split(".")[0])
        payload = _b64d(tok.split(".")[1])
        flags = []
        alg = str(hdr.get("alg", ""))
        if alg.lower() in ("none", "", "hs256"):
            flags.append(f"alg={alg or '?'} faible")
        if "role" in payload or "admin" in str(payload).lower():
            flags.append("claim role/admin visible")
        if payload.get("exp") and payload["exp"] * 1000 < 4102444800000:
            flags.append("exp long-vie")
        slot["jwt"].append(f"{alg or '?'}: {str(payload)[:120]} {'; '.join(flags)}")
    # 4. secrets in responses
    for m in _SECRET_RX.finditer(body):
        slot["secrets"].append(m.group(0)[:80])
    # 5. cookie flags
    setc = [v for k, v in hdrs.items() if k == "set-cookie"]
    for c in setc:
        name = c.split("=")[0]
        missing = [f for f in ("Secure", "HttpOnly", "SameSite") if f.lower() not in c.lower()]
        if missing:
            slot["cookies"].append(f"{name} — sans {', '.join(missing)}")
    # 6. security headers (only flag once per host via headers slot)
    missing_h = [h for h in _SEC_HEADERS if h not in hdrs]
    if missing_h and resp.get("status") == 200:
        slot["headers"].append(f"{url.split('?')[0]} — sans {', '.join(missing_h)}")


@register(name="har_passive_scan",
          desc="PASSIVE VULN LENS: zero-request analysis of a HAR capture — "
               "IDOR-shaped ids (vary them), JWT weaknesses (alg none/HS256, "
               "role claims, stale exp), cookies missing Secure/HttpOnly/"
               "SameSite, missing security headers, secrets in responses, and "
               "price/credit/amount fields (server-trust: race/mutation "
               "candidates). Pure reading — safe under any ROE.",
          params={"type": "object", "properties": {
              "har_path": {"type": "string", "description": "path to .har file (uploads dir OK)"}},
              "required": ["har_path"]},
          danger="safe")
def har_passive_scan(har_path):
    if not har_path or not os.path.isfile(har_path):
        return f"TOOL ERROR [NO_HAR]: fichier introuvable: {har_path}"
    try:
        with open(har_path, encoding="utf-8", errors="replace") as f:
            har = json.load(f)
    except Exception as ex:
        return f"TOOL ERROR [BAD_HAR]: {str(ex)[:140]}"
    entries = (har.get("log") or {}).get("entries") or []
    if not entries:
        return "TOOL ERROR [EMPTY]: aucune entrée dans le HAR"
    host_findings = {}
    for e in entries:
        try:
            _analyze_entry(e, host_findings)
        except Exception:
            continue

    lines = [f"HAR PASSIVE SCAN — {len(entries)} entrées analysées, {len(host_findings)} hôtes."]
    total = 0
    sev_rank = {"jwt": 2, "secrets": 3, "money": 2, "idor": 2, "cookies": 1, "headers": 1}
    out_obj = {"hosts": {}}
    for host, slot in host_findings.items():
        hitlines = []
        for kind in ("secrets", "jwt", "money", "idor", "cookies", "headers"):
            vals = list(dict.fromkeys(slot[kind]))[:6]
            if vals:
                hitlines.append(f"  [{kind.upper()}]")
                for v in vals:
                    hitlines.append(f"   - {v[:150]}")
        if hitlines:
            total += len(hitlines)
            out_obj["hosts"][host] = {k: list(dict.fromkeys(v))[:8] for k, v in slot.items() if v}
            lines.append(f"\n● {host}")
            lines.extend(hitlines)
    if total == 0:
        lines.append("\nAucun signal passif — capture propre (ou capture trop courte: navigue plus).")
    # persist
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "reports", "har_passive_findings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return "\n".join(lines)
