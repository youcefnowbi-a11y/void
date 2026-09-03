"""VOIDFORGE :: session_keep — one-call session minting with a disk cache.

Mission 76 autopsy: ~20 of 78 rounds were re-mints of the same Clerk
session token (60s expiry) performed by hand through data_extract. The
reflex was right — the wiring was manual. This tool owns the whole loop:
mint once, cache keyed by auth_url, auto-refresh ONLY inside the
freshness window (ttl - 30s), return the token with the exact header
wiring. She asks once per lane; the tool keeps the session alive.

Supports the two mint shapes seen in the wild:
  - JSON body carrying a JWT / token field (Clerk, Firebase, custom)
  - Set-Cookie session issuance (classic app sessions)

No dependencies, no secrets written to logs — the cache file lives in
the gitignored data/ directory.
"""
import json
import os
import re
import time
import tempfile
import urllib.request

from . import register

_CACHE = os.path.join("data", "session_cache.json")
_DEFAULT_TTL = 60          # Clerk-style short-lived tokens
_REFRESH_MARGIN = 30       # refresh this many seconds before expiry
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
_JWT_RX = re.compile(r"eyJ[A-Za-z0-9_\-.]{40,}")
_COOKIE_RX = re.compile(r"(?i)(?:^|,\s*)([\w\-]*(?:session|sid|token|auth)[\w\-]*)=([^\s;]+)")


def _load():
    try:
        with open(_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _store(cache):
    try:
        os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(_CACHE), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, _CACHE)
    except Exception:
        pass  # cache is an optimization, never a hard dependency


def _dig(obj, path):
    """token_path 'a.b.0.c' walker; '' = auto-scan."""
    cur = obj
    for part in (path or "").split(".") if path else []:
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    if isinstance(cur, str) and len(cur) > 8:
        return cur
    return None


def _auto_scan(data):
    """(token, kind) from arbitrary mint responses."""
    if isinstance(data, dict):
        for key in ("token", "jwt", "access_token", "session_token",
                    "session", "id_token", "bearer"):
            v = data.get(key)
            if isinstance(v, str) and len(v) > 16:
                return v, "jwt" if v.startswith("eyJ") else "raw"
        m = _JWT_RX.search(json.dumps(data))
        if m:
            return m.group(0), "jwt"
    if isinstance(data, str):
        m = _JWT_RX.search(data)
        if m:
            return m.group(0), "jwt"
        cookies = _COOKIE_RX.findall(data)
        if cookies:
            name, val = cookies[0][:2]
            return f"{name}={val}", "cookie"
    return None, None


def _scan_cookies(headers):
    """Session cookie straight from Set-Cookie headers."""
    raw = headers.get_all("Set-Cookie") if hasattr(headers, "get_all") else []
    for line in raw or []:
        m = re.match(r"\s*([\w\-]*(?:session|sid|token|auth)[\w\-]*)=([^;]+)", line, re.I)
        if m:
            return f"{m.group(1)}={m.group(2)}"
    return None


@register(
    "session_keep",
    "Mint (or refresh) an auth session token and CACHE it: one call per lane, "
    "auto-refresh inside the freshness window. Returns the token + exact "
    "header wiring (Bearer / Cookie). Use instead of hand re-minting tokens "
    "every round.",
    {
        "type": "object",
        "properties": {
            "auth_url": {"type": "string",
                         "description": "URL that mints the session token"},
            "method": {"type": "string", "description": "HTTP method (default POST)"},
            "body": {"type": "object", "description": "JSON body for the mint request"},
            "headers": {"type": "object", "description": "extra headers (auth, origin...)"},
            "token_path": {"type": "string",
                           "description": "dot path to the token in the JSON response "
                                          "(e.g. 'session.token'); empty = auto-scan"},
            "ttl": {"type": "integer",
                    "description": "token lifetime seconds (default 60; used to "
                                   "schedule silent refreshes)"},
        },
        "required": ["auth_url"],
    },
    danger="network",
)
def run(auth_url, method="POST", body=None, headers=None, token_path="", ttl=None):
    ttl = int(ttl) if ttl else _DEFAULT_TTL
    method = (method or "POST").upper()
    cache = _load()
    entry = cache.get(auth_url)
    now = time.time()
    if entry and (now - entry.get("minted_at", 0)) < max(ttl - _REFRESH_MARGIN, 5):
        age = round(now - entry["minted_at"], 1)
        return {"ok": True, "cache_hit": True, "auth_url": auth_url,
                "token": entry["token"], "token_kind": entry["kind"],
                "token_age_s": age, "ttl": ttl,
                "use": _wiring(entry["kind"]),
                "note": f"fresh token from cache ({age}s old) — no network spent"}

    # ── mint ──
    req = urllib.request.Request(auth_url, method=method)
    req.add_header("User-Agent", _BROWSER_UA)
    req.add_header("Accept", "application/json, text/plain, */*")
    for k, v in (headers or {}).items():
        req.add_header(str(k), str(v))
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(req, data=data, timeout=30)
        raw = r.read().decode(errors="replace")
        status = r.status
        set_cookie = _scan_cookies(r.headers)
        ctype = (r.headers.get("Content-Type") or "")
        r.close()
    except Exception as ex:
        body_txt = ""
        if hasattr(ex, "read"):
            try:
                body_txt = ex.read().decode(errors="replace")[:300]
            except Exception:
                pass
        return {"ok": False, "auth_url": auth_url,
                "error": f"mint failed: {type(ex).__name__}: {str(ex)[:150]} {body_txt}"}

    token, kind = None, None
    try:
        parsed = json.loads(raw) if "json" in ctype or raw[:1] in "{[" else None
    except Exception:
        parsed = None
    if parsed is not None:
        token = _dig(parsed, token_path) if token_path else None
        if token is None:
            token, kind = _auto_scan(parsed)
    if token is None and set_cookie:
        token, kind = set_cookie, "cookie"
    if token is None:
        token, kind = _auto_scan(raw)
    if token is None:
        return {"ok": False, "auth_url": auth_url, "status": status,
                "error": "mint responded but no token found — pass token_path "
                         f"or check the flow. ctype={ctype[:40]} len={len(raw)}"}

    kind = kind or ("jwt" if token.startswith("eyJ") else "raw")
    cache[auth_url] = {"token": token, "kind": kind, "minted_at": now, "ttl": ttl}
    _store(cache)
    return {"ok": True, "cache_hit": False, "auth_url": auth_url,
            "status": status, "token": token, "token_kind": kind,
            "ttl": ttl, "use": _wiring(kind),
            "note": "fresh mint — cached; re-call this tool next round and the "
                    "cache keeps it alive without re-minting"}


def _wiring(kind):
    if kind == "jwt":
        return "send header: Authorization: Bearer <token>"
    if kind == "cookie":
        return "send header: Cookie: <token-as-name=value>"
    return "send per the target's scheme (token returned raw)"
