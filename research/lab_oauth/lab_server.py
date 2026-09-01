"""CIBLE-LAB OAuth2 volontairement vulnérable — terrain de validation du
futur auth_state_engine. STDLIB ONLY (http.server), deux émetteurs (A/B)
pour le mix-up, défauts plantés documentés dans README_LAB.md.

Lancer : python research/lab_oauth/lab_server.py  → http://127.0.0.1:9443
"""
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ── état en mémoire (lab = pas de persistance) ──────────────────────────
AUTH_CODES = {}      # code -> {sub, iss, exp, used}
ACCESS_TOKENS = {}   # token -> {sub, iss, aud, exp}
SESSIONS = {}        # sid -> {user}
CLIENT = {"demo": "secret-demo"}

# Défaut planté D1 : PKCE jamais exigé (code_verifier ignoré)
REQUIRE_PKCE = False
# Défaut planté D2 : state accepté s'il existe, JAMAIS comparé à la session
VERIFY_STATE = False
# Défaut planté D3 : code réutilisable (used jamais bloqué)
ONE_TIME_CODES = False
# Défaut planté D4 : redirect_uri validé par PRÉFIXE (pas égalité exacte)
EXACT_REDIRECT = False


def _issue_code(sub, iss):
    # Défaut planté D5 : entropy du code = 32 bits (borne L·log2|charset| << 160)
    code = secrets.token_hex(4)
    AUTH_CODES[code] = {"sub": sub, "iss": iss, "exp": time.time() + 300,
                        "used": False}
    return code


def _issue_token(sub, iss, aud):
    tok = hmac.new(b"lab-secret-key", f"{sub}|{iss}|{aud}|{time.time()}".encode(),
                   hashlib.sha256).hexdigest()
    ACCESS_TOKENS[tok] = {"sub": sub, "iss": iss, "aud": aud,
                          "exp": time.time() + 600}
    return tok


class LabHandler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", headers=None, content="text/plain"):
        self.send_response(code)
        for k, v in (headers or []):
            self.send_header(k, v)
        self.send_header("Content-Type", content)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _redirect(self, location):
        self._send(302, headers=[("Location", location)])

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), content="application/json")

    # ── /authA/* et /authB/* : deux émetteurs pour le test mix-up ──
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        path = u.path

        if path.startswith("/authA") or path.startswith("/authB"):
            iss = "https://issuer-a.example" if path.startswith("/authA") \
                else "https://issuer-b.example"
            redirect_uri = q.get("redirect_uri", [""])[0]
            state = q.get("state", [""])[0]
            # D4 : préfixe au lieu d'égalité — https://evil.example.com/cp passe
            ok_redirect = redirect_uri.startswith("https://app.example/cb")
            if not ok_redirect:
                return self._json({"error": "invalid redirect_uri"}, 400)
            # D2 : le state est renvoyé tel quel, jamais lié à une session
            code = _issue_code(q.get("login", ["victime"])[0], iss)
            sep = "&" if "?" in redirect_uri else "?"
            return self._redirect(f"{redirect_uri}{sep}code={code}&state={state}")

        if path == "/token":
            code = q.get("code", [""])[0] or self._body().get("code", [""])[0]
            rec = AUTH_CODES.get(code)
            if not rec or rec["exp"] < time.time():
                return self._json({"error": "invalid_code"}, 400)
            # D3 : le code reste utilisable — replay complet du flux
            # D1 : code_verifier ignoré même si présent
            tok = _issue_token(rec["sub"], rec["iss"], aud="app.example")
            return self._json({"access_token": tok, "token_type": "Bearer",
                               "iss": rec["iss"]})

        if path == "/api/user":
            auth = self.headers.get("Authorization", "")
            tok = auth.removeprefix("Bearer ").strip()
            rec = ACCESS_TOKENS.get(tok)
            if not rec or rec["exp"] < time.time():
                return self._json({"error": "unauthorized"}, 401)
            # D6 : PAS de vérification iss/aud — un token de issuer-b passe
            # sur le resource server de issuer-a (mix-up / audience confusion)
            return self._json({"sub": rec["sub"], "iss": rec["iss"],
                               "note": "issued by whoever — nobody checks"})

        if path == "/health":
            return self._send(200, b"lab-oauth-alive")
        return self._json({"error": "not_found"}, 404)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode() if n else ""
        return urllib.parse.parse_qs(raw)

    # RFC-canonical POST routing: the engine probes /token and /api/user by
    # POST (the way real OAuth clients do) — delegate to the GET router so
    # both verbs behave identically (query string lives in self.path either way)
    def do_POST(self):
        self.do_GET()

    def log_message(self, *a):  # silence le log console
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 9443), LabHandler)
    print("LAB OAuth vulnérable sur http://127.0.0.1:9443 — défauts D1-D6 actifs")
    srv.serve_forever()
