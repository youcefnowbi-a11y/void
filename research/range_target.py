"""VOIDFORGE RANGE :: cible d'entraînement locale — failles SIMULÉES sur
127.0.0.1:8765. Zéro exec de commandes réelles, zéro contact externe: les
'exploits' sont des réponses simulées qui exercent les chemins de détection
des outils. C'est un stand de tir, pas une arme."""
import base64, json, sqlite3, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

STOCK = {"RACE100": 1}          # single-use coupon -> race window
STOCK_LOCK = threading.Lock()
JWT_SECRET = "voidforge-secret"
UPLOADS = {}

def mktoken(claims):
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    import hmac, hashlib
    s = base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{h}.{p}.{s}"

def b64d(x):
    return base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _j(self, code, obj, hdrs=None):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        for k, v in (hdrs or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8", "replace") if n else ""

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path

        if p == "/":
            return self._j(200, {"app": "voidforge-range", "endpoints": ["/product?id=", "/api/users?offset=&limit=", "/api/user?id=", "/otp?user=&code=", "/search?q=", "/cmd?host=", "/file?path=", "/redirect?url=", "/jwt", "/jwt/verify", "/upload", "/uploads/<f>", "/race", "/signup", "/graphql", "/app.js", "/admin", "/ssti?name="]})
        if p == "/app.js":
            b = b'var CFG={api:"https://range.internal/api/v2",key:"sk-range-AUDIT7788"};\nfunction boom(){return 1;}'
            self.send_response(200); self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); return self.wfile.write(b)
        if p == "/product":
            # VRAIE sqli sqlite: union select renvoie des rows supplementaires
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE TABLE products (id INT, name TEXT, price REAL)")
            conn.execute("CREATE TABLE secrets (k TEXT, v TEXT)")
            conn.execute("INSERT INTO products VALUES (1,'hammer',9.99),(2,'nail',0.10),(3,'saw',14.50)")
            conn.execute("INSERT INTO secrets VALUES ('admin_pass','r4ng3-s3cr3t')")
            raw = q.get("id", "1")
            try:
                rows = conn.execute(f"SELECT id,name,price FROM products WHERE id='{raw}'").fetchall()
                rows = [r for r in rows if r is not None]
                return self._j(200, {"rows": [{"id": r[0], "name": r[1], "price": r[2]} for r in rows]})
            except Exception as e:
                return self._j(500, {"error": str(e)})
        if p == "/api/users":
            off = int(q.get("offset", 0)); lim = min(int(q.get("limit", 2)), 5)
            users = [{"id": i, "email": f"user{i}@range.tld", "role": "user"} for i in range(1, 11)]
            return self._j(200, {"users": users[off:off + lim], "total": len(users), "offset": off})
        if p == "/api/user":
            return self._j(200, {"id": q.get("id"), "email": "victim@range.tld", "iban": "FR00RANGE0000", "role": "admin"})
        if p == "/otp":
            ok = q.get("code") == "482913"
            return self._j(200, {"success": ok, "user": q.get("user")})
        if p == "/search":
            return self._j(200, {"echo": q.get("q", ""), "results": []})
        if p == "/cmd":
            host = q.get("host", "")
            if any(s in host for s in (";", "|", "&&", "`", "$(")):
                return self._j(200, {"output": "uid=0(root) gid=0(root) rangesim\nSIM-CMD-OUTPUT"})
            return self._j(200, {"output": f"ping {host} (simulated)"})
        if p == "/file":
            path = q.get("path", "")
            if "php://filter" in path and "convert.base64" in path:
                src = base64.b64encode(b"root:x:0:0:root:/root:/bin/sh\nrangeuser:x:1000:1000::/home/rangeuser:/bin/sh").decode()
                return self._j(200, {"content": src})
            if ".." in path or "etc/passwd" in path:
                return self._j(200, {"content": "root:x:0:0:root:/root:/bin/sh\nrangeuser:x:1000:1000::/home/rangeuser:/bin/sh"})
            return self._j(404, {"error": "not found"})
        if p == "/ssrf":
            tgt = q.get("url", "")
            if "169.254.169.254" in tgt or "metadata" in tgt:
                return self._j(200, {"internal": True, "iam_role": "range-admin", "secret": "SIM-SSRF-HIT"})
            return self._j(200, {"fetched": tgt})
        if p == "/redirect":
            return self._j(302, {"redirect": q.get("url", "/")}, hdrs={"Location": q.get("url", "/")})
        if p == "/jwt":
            return self._j(200, {"token": mktoken({"sub": 1001, "role": "user", "exp": 9999999999})})
        if p == "/jwt/verify":
            tok = (self.headers.get("Authorization") or "").replace("Bearer ", "")
            try:
                h, pay, sig = tok.split(".")
                import hmac, hashlib
                exp = base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(), f"{h}.{pay}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
                claims = json.loads(b64d(pay))
                if sig == exp and claims.get("role") == "admin":
                    return self._j(200, {"success": True, "admin": True})
                if sig == exp:
                    return self._j(200, {"success": True, "admin": False})
            except Exception:
                pass
            return self._j(401, {"success": False})
        if p.startswith("/uploads/"):
            fn = p[len("/uploads/"):]
            data = UPLOADS.get(fn)
            if data is None:
                return self._j(404, {"error": "no shell"})
            cmd = q.get("cmd", "")
            return self._j(200, {"output": f"uid=0(root) rangesim\nCMD> {cmd}"})
        if p == "/admin":
            return self._j(401, {"error": "exists-locked"})
        if p == "/admin/panel":
            return self._j(200, {"panel": "range-admin"})
        if p == "/ssti":
            name = q.get("name", "")
            if "{{" in name and "}}" in name:
                try:
                    expr = name.split("{{")[1].split("}}")[0]
                    if "*" in expr:
                        a, _, b = expr.partition("*")
                        return self._j(200, {"rendered": str(int(a.strip()) * int(b.strip()))})
                except Exception:
                    pass
            return self._j(200, {"rendered": name})
        if p == "/graphql":
            return self._j(200, {"data": {"__schema": {"types": [{"name": "Query"}, {"name": "User"}]}}})
        if p == "/har":
            return self._j(200, {"har": "see har_passive_scan fixture"})
        if p == "/metadata.json":
            return self._j(200, {"fields": {"role": "user", "plan": "free"}})
        return self._j(404, {"error": "nf"})

    def do_POST(self):
        u = urlparse(self.path)
        body = self._body()
        if u.path == "/race":
            coupon = "RACE100" if "RACE100" in body else None
            if not coupon:
                return self._j(400, {"success": False, "error": "no coupon"})
            time.sleep(0.05)                      # fenêtre de course élargie
            with STOCK_LOCK:
                if STOCK[coupon] > 0:
                    STOCK[coupon] -= 1
                    return self._j(200, {"success": True, "redeemed": True})
            return self._j(200, {"success": False, "error": "already used"})
        if u.path == "/signup":
            if "exists@range.tld" in body:
                return self._j(409, {"error": "email exists", "leaked": True})
            return self._j(201, {"created": True})
        if u.path == "/upload":
            # multipart minimal: cherche le filename + le contenu
            import re
            m = re.search(r'filename="([^"]+)"\r?\n\r?\n(.*?)\r?\n--', body, re.S)
            if not m:
                return self._j(400, {"error": "bad multipart"})
            fn, data = m.group(1), m.group(2)
            UPLOADS[fn] = data
            return self._j(201, {"saved": fn, "path": f"/uploads/{fn}"})
        if u.path == "/xxe":
            if "<!ENTITY" in body and "etc/passwd" in body:
                return self._j(200, {"parsed": "root:x:0:0:root:/root:/bin/sh\nSIM-XXE-READ"})
            return self._j(200, {"parsed": "ok"})
        if u.path == "/graphql":
            if "__schema" in body:
                return self._j(200, {"data": {"__schema": {"types": [{"name": "Query"}, {"name": "Secret"}]}}})
            return self._j(200, {"data": {}})
        return self._j(404, {"error": "nf"})

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 8765), H)
    print("RANGE up on 127.0.0.1:8765", flush=True)
    srv.serve_forever()
