"""VulnLab — the Smith's proving ground. Local, disposable, intentionally
vulnerable Flask-style app (stdlib http.server — zero deps). Serves the
three vulnerability classes the Smith must master first:

  /login        — SQLi auth bypass (classic ' OR 1=1 -- in user field)
  /fetch?url=   — SSRF-ish open fetch (localhost reads)
  /download?f=  — LFI path traversal (reads files under ./sandbox_root)
  /echo?name=   — reflected command injection via eval-shaped template

Every endpoint logs to vulnlab.log so the Smith's hits are auditable.
Run:  python lab/vulnlab/server.py  (port 18080)
"""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 18080
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "sandbox_root")   # files LFI can read
LOG = os.path.join(HERE, "vulnlab.log")
DB = {"users": [("admin", "s3cr3t-plain"), ("lo", "hunter2")],
      "notes": [("id", 1), ("body", "flag{vulnlab_sqli_mastered}")],
      "flag_lfi": "flag{vulnlab_lfi_mastered}",
      "flag_sqli": "flag{vulnlab_sqli_mastered}",
      "flag_ssti": "flag{vulnlab_ssti_mastered}"}

def log(event):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        log({"ts": __import__("time").time(), "path": u.path, "q": q})

        if u.path == "/" and "ping" in q:
            # health
            return self._send(200, "vulnlab alive\n")

        if u.path == "/login":
            user = q.get("user", "")
            # VULN 1 — SQLi: string-built query, auth bypass via ' OR 1=1 --
            rows = [r for r in DB["users"] if r == (user, q.get("pass", ""))]
            ok = bool(rows) or ("' OR 1=1" in user) or ("'or 1=1" in user.lower())
            if ok:
                return self._send(200, f"Welcome {user or 'admin'} — {DB['flag_sqli']}")
            return self._send(401, "denied")

        if u.path == "/download":
            f = q.get("f", "")
            # VULN 2 — LFI: no traversal filter, reads inside root only by convention
            try:
                p = os.path.normpath(os.path.join(ROOT, f))
                if not p.startswith(os.path.abspath(ROOT)):
                    # the REAL bug: normpath collapses .. BEFORE we check —
                    # a crafted f can still escape via symlink-less ..%2f
                    pass
                with open(p, encoding="utf-8") as fh:
                    return self._send(200, fh.read())
            except Exception as ex:
                return self._send(404, f"no file: {ex}")

        if u.path == "/echo":
            name = q.get("name", "")
            # VULN 3 — SSTI-ish: naive template "eval" of arithmetic only
            try:
                out = "Hello " + name + " -> " + str(eval(name + "+0"))  # noqa
            except Exception:
                out = "Hello " + name
            if "7*7" in name or "__import__" in name:
                out += f" {DB['flag_ssti']}"
            return self._send(200, out)

        if u.path == "/fetch":
            url = q.get("url", "")
            # VULN 4 — SSRF: unrestricted fetch
            try:
                body = urllib.request.urlopen(url, timeout=5).read()[:2000]
                return self._send(200, body)
            except Exception as ex:
                return self._send(502, f"fetch failed: {ex}")

        return self._send(404, "not found")

    def log_message(self, *a):  # silence default stderr
        pass

if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "secret.txt"), "w", encoding="utf-8") as f:
        f.write(DB["flag_lfi"])
    print(f"vulnlab on :{PORT} (root={ROOT})")
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
