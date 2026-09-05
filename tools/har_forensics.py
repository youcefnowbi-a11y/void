"""TOOL: har_forensics - dissect HAR captures for keys, tokens, endpoints."""
import json, re
from tools import register

PATTERNS = {
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
    "bearer": re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-.=]{20,}"),
    "api_key": re.compile(r"(?i)(?:apikey|api_key|x-api-key)[\"'=:\s]+([A-Za-z0-9_\-\.]{16,})"),
    "aws": re.compile(r"(AKIA|ASIA)[A-Z0-9]{16}"),
    "stripe": re.compile(r"(sk|pk|whsec)_(live|test)_[A-Za-z0-9]{16,}"),
    "slack_bot": re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    "google": re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
}

def _resolve_har(har_path):
    import os
    if not har_path:
        return None
    if os.path.isabs(har_path) and os.path.exists(har_path):
        return har_path
    resolved = None
    try:
        from core.mission_workspace import get_active
        ws = get_active()
        if ws:
            candidates = [
                os.path.join(ws.dir, "captures", har_path),
                os.path.join(ws.dir, har_path),
                os.path.join(ws.dir, "captures", os.path.basename(har_path)),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c
    except Exception:
        pass
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for d in [os.getcwd(), base, os.path.join(base, "missions")]:
        for root, _, files in os.walk(d):
            if os.path.basename(har_path) in files:
                return os.path.join(root, os.path.basename(har_path))
    return None

@register(name="har_dissect",
          desc="Dissect a HAR file: host map, secrets (JWT/API keys), cookies, interesting endpoints.",
          params={"type":"object","properties":{"har_path":{"type":"string"}},
                  "required":["har_path"]})
def har_dissect(har_path):
    resolved = _resolve_har(har_path)
    if not resolved:
        return json.dumps({"error": f"HAR file not found: {har_path}",
                           "hint": "Provide absolute path or filename from captures/ folder"})
    har_path = resolved
    # Ω3.1 (audit-6): Capped read with context manager
    with open(har_path, encoding="utf-8", errors="replace") as f:
        raw = f.read(25_000_000)
    try:
        entries = (json.loads(raw).get("log") or {}).get("entries") or []
    except Exception as ex:
        return f"TOOL ERROR [BAD_HAR]: {str(ex)[:140]} — HAR malformé ou non-JSON"
    hosts, secrets, endpoints = {}, [], set()
    for i, e in enumerate(entries):
        u = e.get("request", {}).get("url", "")
        m = re.match(r"https?://([^/]+)", u)
        if m: hosts[m.group(1)] = hosts.get(m.group(1), 0) + 1
        blob = json.dumps(e.get("request", {})) + str((e.get("response", {}).get("content") or {}).get("text", "")[:50000])
        for name, pat in PATTERNS.items():
            for mm in pat.finditer(blob):
                secrets.append({"type": name, "match": mm.group(0)[:160], "req_index": i, "url": u[:120]})
        if re.search(r"pro|vip|admin|auth|user|payment|token|key", u, re.I):
            req_m = e.get("request", {}).get("method", "GET")
            resp_st = e.get("response", {}).get("status", "")
            endpoints.add(f"{req_m} {u[:140]} [{resp_st}]")
    return json.dumps({
        "total_requests": len(entries),
        "hosts": sorted(hosts.items(), key=lambda x: -x[1])[:15],
        "secrets_found": len(secrets),
        "secrets_sample": secrets[:25],
        "sensitive_endpoints": sorted(endpoints)[:30],
    }, ensure_ascii=False, indent=1)

@register(name="har_tokens",
          desc="Extract full Authorization/JWT tokens from a HAR file (returns unique values). Subset of har_dissect — use when you only need credentials.",
          params={"type":"object","properties":{"har_path":{"type":"string"}},
                  "required":["har_path"]})
def har_tokens(har_path):
    resolved = _resolve_har(har_path)
    if not resolved:
        return f"TOOL ERROR [NO_HAR]: fichier introuvable: {har_path}"
    with open(resolved, encoding="utf-8", errors="replace") as f:
        raw = f.read(25_000_000)
    found = set()
    for m in re.finditer(r'"name":\s*"[Aa]uthorization",\s*"value":\s*"([^"]+)"', raw):
        found.add(m.group(1))
    for m in PATTERNS["jwt"].finditer(raw):
        found.add(m.group(0))
    return json.dumps(sorted(found)[:20], ensure_ascii=False, indent=1)
