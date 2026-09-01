"""VOIDFORGE :: ForgeRange — the deliberately vulnerable mini-shop.

The proving ground every tool, playbook, planner change and swarm behavior
is CI-tested against. Runs on 127.0.0.1:8765. Surfaces (all intentional):

  - SPA bundle with embedded full anon key, supabase ref, serverFn hashes,
    webpack chunk references, admin slug constant  (js_mine / spa_crawl)
  - source map at /assets/index-ForgeLab.js.map                  (js_mine v2)
  - fake PostgREST /products with ?select= + SQL-ish error on quote (sqli)
  - /orders 403 without admin JWT (RLS sim)                       (data_extract)
  - /auth/login accepting alg=none unsigned JWT                   (jwt_analyst)
  - /admin/<slug> gate, slug "forge-admin"                        (dir_brute-ish)
  - /_serverFn/<hash> Seroval wire-format endpoints               (protocols)
  - /api/ping rate-limited 429 after 5 req / 10s                  (Pacer/backoff)
  - /storage/v1/bucket/public bucket listing                      (buckets)
  - /~api/telemetry 202 noise, /~api/orders POST-only             (api_sweep)
  - /redirect-307 chain target                                    (redirects)
  - localStorage token set by /assets/chunk-Tracker.js            (spa_crawl v2)

Run:  python lab/forge_range.py   (or uvicorn lab.forge_range:app --port 8765)
"""
import hmac, hashlib, base64, json, time, threading, os, sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse

app = FastAPI(title="ForgeRange", docs_url=None, redoc_url=None)

SECRET = b"forge-range-secret"
ADMIN_SLUG = "forge-admin"
ANON_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJmb3JnZXJhbmdlIiwicmVmIjoiZm9yZ2VyYW5nZXJhbmdlMjAiLCJyb2xlIjoiYW5vbiJ9."
            "Zm9yZ2VyYW5nZXNpZ25hdHVyZWNoZWNrMTIzNDU2Nzg")
SUPA_REF = "forgeangerange20"
PRODUCTS = [{"id": i, "name": f"Item-{i}", "price": i * 9.99, "stock": 100 - i} for i in range(1, 6)]
ORDERS = [{"id": 1, "user": "nova@range.test", "item": "Item-1", "total": 9.99},
          {"id": 2, "user": "zed@range.test", "item": "Item-3", "total": 29.97},
          {"id": 3, "user": "ivy@range.test", "item": "Item-5", "total": 49.95}]
SERVERFN = {"20b34aaaa7e9a6d097543e": "products_loader",
            "9a85874eff31c2bd0045a1": "admin_gate"}

_hits = deque()
_hits_lock = threading.Lock()


def _jwt(payload, alg="HS256", sig=None):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    head = b64({"alg": alg, "typ": "JWT"})
    body = b64(payload)
    if alg == "none":
        return f"{head}.{body}."
    s = base64.urlsafe_b64encode(hmac.new(SECRET, f"{head}.{body}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{head}.{body}.{s}"


def _verify(token):
    """HS256 verified; alg=none accepted unsigned (INTENTIONAL pitfall)."""
    try:
        head = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))
        body = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        if head.get("alg") == "none":
            return body
        expected = base64.urlsafe_b64encode(
            hmac.new(SECRET, f"{token.split('.')[0]}.{token.split('.')[1]}".encode(),
                     hashlib.sha256).digest()).rstrip(b"=").decode()
        return body if hmac.compare_digest(expected, token.split(".")[2]) else None
    except Exception:
        return None


def _seroval_parse(node):
    if not isinstance(node, dict) or "t" not in node:
        return node
    t = node.get("t")
    if t == 0:
        return None
    if t in (1, 2, 3):
        return node.get("s")
    if t == 5:
        return [_seroval_parse(c) for c in node.get("s", [])]
    if t == 6:
        return {k: _seroval_parse(v) for k, v in node.get("s", {}).items()}
    return node


@app.get("/")
def index():
    return HTMLResponse("<html><body><h1>ForgeRange Shop</h1>"
                        "<script src='/assets/index-ForgeLab.js'></script>"
                        "<script src='/assets/chunk-Tracker-EF56GH78.js'></script>"
                        "<script>loadProducts('all').then(()=>loadAdmin('admin'));</script>"
                        "</body></html>")


@app.get("/assets/index-ForgeLab.js")
def bundle():
    src = (
        f'const SUPABASE_URL="https://{SUPA_REF}.supabase.co";'
        f'const ANON_KEY="{ANON_KEY}";'
        'const CHUNKS={"admin":"chunk-Admin-AB12CD34.js","tracker":"chunk-Tracker-EF56GH78.js"};'
        'async function loadAdmin(slug){const r=await fetch("/_serverFn/9a85874eff31c2bd0045a1"'
        ',{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({data:{slug}})});'
        'return r.json();}'
        'async function loadProducts(cat){const r=await fetch("/_serverFn/20b34aaaa7e9a6d097543e"'
        ',{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({data:{cat}})});'
        'return r.json();}'
        'fetch("/~api/telemetry");'
    )
    return Response(src, media_type="application/javascript")


@app.get("/assets/index-ForgeLab.js.map")
def source_map():
    return JSONResponse({"version": 3, "file": "index-ForgeLab.js",
                         "sources": ["src/admin.ts"],
                         "sourcesContent": [
                             'export const ADMIN_SLUG = "forge-admin"; // TODO remove before prod\n'
                             'export const BACKUP_TOKEN = "sb_secret_forgebackupdo_not_ship_000";']})


@app.get("/assets/chunk-Admin-AB12CD34.js")
def chunk_admin():
    return Response('export const ADMIN_SLUG="forge-admin";'
                    'export async function adminGate(s){const r=await fetch(`/admin/${s}`);return r.ok;}',
                    media_type="application/javascript")


@app.get("/assets/chunk-Tracker-EF56GH78.js")
def chunk_tracker():
    return Response('localStorage.setItem("forge_token", "%s");'
                    'sessionStorage.setItem("visit","1");' % _jwt({"role": "anon", "ref": SUPA_REF}),
                    media_type="application/javascript")


@app.get("/products")
def products(id: str = None, select: str = None):
    if id and "'" in id:
        return JSONResponse({"error": "sqlite3.OperationalError: unrecognized token"}, status_code=500)
    if id:
        p = [p for p in PRODUCTS if str(p["id"]) == id]
        return JSONResponse(p if p else [], status_code=200)
    return JSONResponse(PRODUCTS)


@app.get("/orders")
def orders(request: Request):
    auth = request.headers.get("authorization", "")
    tok = auth[7:] if auth.startswith("Bearer ") else ""
    claims = _verify(tok) if tok else None
    if not claims or claims.get("role") != "admin":
        return JSONResponse({"error": "RLS: policy blocked; admin role required"}, status_code=403)
    return JSONResponse(ORDERS)


@app.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    if body.get("user") == "admin" and body.get("pass") == ADMIN_SLUG:
        return JSONResponse({"token": _jwt({"role": "admin", "sub": "admin"})})
    return JSONResponse({"error": "invalid credentials"}, status_code=401)


@app.get("/admin/{slug}")
def admin(slug: str):
    if slug == ADMIN_SLUG:
        return PlainTextResponse(f"<html><body><h1>Admin OK</h1><p>{len(ORDERS)} orders</p></body></html>")
    return PlainTextResponse("not found", status_code=404)


@app.post("/_serverFn/{fn_hash}")
async def server_fn(fn_hash: str, request: Request):
    raw = await request.body()
    try:
        payload = json.loads(raw or b"{}")
    except Exception:
        return PlainTextResponse("seroval parse error: expected node tree {t,s}", status_code=400)
    data = payload.get("data")
    if isinstance(data, dict) and "t" in data:
        data = _seroval_parse(data)
    name = next((v for k, v in SERVERFN.items() if fn_hash.startswith(k)), None)
    if name == "products_loader":
        cat = (data or {}).get("cat", "all")
        out = PRODUCTS if cat in ("all", None) else [p for p in PRODUCTS if p["name"].lower().endswith(str(cat))]
        return JSONResponse({"t": 6, "i": 0, "s": {"items": {"t": 5, "i": 1, "s": [
            {"t": 6, "i": 2, "s": {"id": {"t": 2, "s": p["id"]}, "name": {"t": 1, "s": p["name"]},
                                   "price": {"t": 2, "s": p["price"]}}} for p in out]}}})
    if name == "admin_gate":
        slug = (data or {}).get("slug")
        if slug == ADMIN_SLUG:
            return JSONResponse({"ok": True, "slug": slug, "label": "ForgeRange Admin",
                                 "permissions": ["orders.read", "products.write"]})
        return JSONResponse({"ok": False}, status_code=200)
    return PlainTextResponse("unknown function", status_code=404)


@app.get("/api/ping")
def ping():
    now = time.time()
    with _hits_lock:
        while _hits and now - _hits[0] > 10:
            _hits.popleft()
        _hits.append(now)
        if len(_hits) > 5:
            return PlainTextResponse("slow down", status_code=429, headers={"Retry-After": "2"})
    return JSONResponse({"pong": True})


@app.get("/storage/v1/bucket/public")
def bucket():
    return JSONResponse({"name": "public", "objects": ["avatars/nova.png", "uploads/receipt-1.pdf"]})


@app.get("/~api/telemetry")
def telemetry():
    return PlainTextResponse("accepted", status_code=202)


@app.post("/~api/orders")
async def api_orders(request: Request):
    return JSONResponse({"queued": True}, status_code=202)


@app.get("/~api/orders")
def api_orders_get():
    return PlainTextResponse("method not allowed", status_code=405)


@app.get("/start")
def start_redirect():
    return Response(status_code=307, headers={"Location": "/products"})


@app.get("/.well-known/security.txt")
def security_txt():
    return PlainTextResponse(
        "Contact: mailto:owner@forge.range\nExpires: 2030-01-01T00:00:00Z\n"
        "# ForgeRange is an internal test range — all testing pre-authorized.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
