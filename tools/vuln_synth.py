"""vuln_synth -- the foundry's crucible (Vague 4).

THE INVERSE OF exploit_scaffold. Where the scaffold emits the skeleton of
the WEAPON, vuln_synth emits the skeleton of the PREY: a minimal,
loopback-only, disposable app that carries exactly ONE real vulnerability
of the requested class, on the finding's own param + path shape.

Why it exists (the GreyNoise gap): a weapon proven against ONE live target
is a point, not a pattern. The Smith could never tell whether it had found
a technique or a coincidence. The foundry closes that: the same weapon is
re-fired against VARIANTS of the same vulnerability shape, and the target
itself -- not the weapon's self-report -- says whether it fired.

  base      the plain vuln, flag returned on success
  blind     no flag: only a boolean/body delta proves execution
  post      the param arrives in a form body (method delta)
  filtered  a naive filter blocks the textbook payload -- a bypass exists

Every synthesized app exposes /__oracle (loopback-only): the GROUND TRUTH
the repro_harness compares the weapon's claim against. The oracle flips
ONLY when the vulnerability was genuinely exercised -- a twin truth table,
generated on demand instead of hand-written.

SAFETY BY CONSTRUCTION: these targets NEVER touch the host. The cmdi
"shell" simulates output for a small command set, the ssrf "fetcher"
serves an in-memory internal namespace, and the ssti "engine" evaluates
integer products only. The GRAMMAR of the vulnerability is real; no
arbitrary execution ever reaches this machine.
"""
import json
import threading

from tools import register
from tools._exploit_lib import verdict as _v

# ── the shared preamble every synthesized app carries ───────────────────
_PRE = '''"""vuln_synth target -- @@CLASS@@ / @@VARIANT@@ (generated, disposable).

The PREY of the foundry: a minimal app carrying exactly ONE real
vulnerability of the requested class. Loopback-only, ephemeral port,
dies when the harness stops it. /__oracle is the GROUND TRUTH the
harness compares the weapon's self-report against.
"""
import base64
import hashlib
import hmac
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

CLASS = "@@CLASS@@"
VARIANT = "@@VARIANT@@"
PARAM = "@@PARAM@@"
PATH = "@@PATH@@"
FLAG = "flag{synth_@@CLASS@@_@@VARIANT@@}"
STATE = {"class": CLASS, "variant": VARIANT, "exploited": False,
         "evidence": []}


def _params(q, body):
    p = dict(q)
    if body:
        try:
            p.update({k: v[0] for k, v in parse_qs(body).items()})
        except Exception:
            pass
    return p


def _naive_filter(s):
    # the "filtered" variant: blocks the TEXTBOOK payload only
    return re.sub(r"(?i)or\\s+1\\s*=\\s*1", "", s or "")


class Base(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _read(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        body = ""
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n:
            body = self.rfile.read(n).decode("utf-8", "replace")
        return u, _params(q, body)

    def _prove(self, evidence):
        STATE["exploited"] = True
        STATE["evidence"].append(evidence)

    def _answer(self, ok, flag_text, benign="denied"):
        # signal shape follows the variant: base/post/filtered return the
        # flag on success; blind returns a body delta only (no flag).
        if VARIANT == "blind":
            return self._send(200, "ok") if ok else self._send(200, benign)
        if ok:
            return self._send(200, flag_text)
        return self._send(403, benign)

    def log_message(self, *a):
        pass
'''

# ── one body per vulnerability class ────────────────────────────────────
_SQLI = '''
USERS = [("admin", "s3cr3t"), ("lo", "hunter2"), ("duskyr", "letmein")]


def _rows(user, pw):
    # the bug: user input is concatenated into the WHERE clause
    raw = user or ""
    u = (_naive_filter(raw) if VARIANT == "filtered" else raw).lower()
    if ("' or" in u or "or 1" in u or "--" in u or "/*" in u or "||" in u
            or "#" in u):
        return USERS                       # auth bypass / full row set
    return [r for r in USERS if r[0] == raw and r[1] == pw]


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        rows = _rows(p.get(PARAM, ""), p.get("pass", ""))
        if rows:
            self._prove({"payload": p.get(PARAM), "rows": len(rows)})
            return self._answer(
                True, "welcome " + ",".join(r[0] for r in rows) + " " + FLAG)
        return self._answer(False, "", benign="denied")


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_LFI = '''
_FILES = {"public/readme.txt": "hello from the foundry",
          "public/info.txt": "public info"}
_SECRET = {"etc/passwd": "root:x:0:0:root:/root:/bin/sh",
           "etc/secret": FLAG, "secret": FLAG}


def _lfi(path):
    # the bug: traversal is resolved by convention, not enforced
    p = (path or "").lstrip("/")
    if VARIANT == "filtered":
        p = p.replace("../", "")           # naive: ....// survives this
    if ".." in p or p.startswith("etc/"):
        key = p.replace("../", "").lstrip("/")
        return _SECRET.get(key, _SECRET["secret"])
    return _FILES.get(p)


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        body = _lfi(p.get(PARAM, ""))
        if body is not None:
            self._prove({"payload": p.get(PARAM), "file": body[:60]})
            return self._answer(True, body)
        return self._answer(False, "", benign="not found")


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_SSTI = '''
def _render(tpl):
    # the bug: the "template engine" evaluates arithmetic found in input.
    # Sandboxed BY CONSTRUCTION: integer products only, no host execution.
    t = tpl or ""
    if VARIANT == "filtered":
        t = t.replace("7*7", "77")          # naive: 6*7 walks right past
    m = re.search(r"(?<![0-9])([0-9]{1,6})\\s*\\*\\s*([0-9]{1,6})(?![0-9])", t)
    if m:
        return ("Hello " + t + " -> "
                + str(int(m.group(1)) * int(m.group(2))), True)
    return ("Hello " + t, False)


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        out, fired = _render(p.get(PARAM, ""))
        if fired:
            self._prove({"payload": p.get(PARAM), "rendered": out[-40:]})
            return self._answer(True, out + " " + FLAG)
        return self._answer(False, out, benign=out)


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_CMDI = '''
_SAFE_CMDS = {"id": "uid=0(root) gid=0(root) groups=0(root)",
              "whoami": "www-data",
              "uname -a": "Linux synth 6.1.0 #1 SMP x86_64 GNU/Linux"}


def _shell(cmd):
    # the bug: the injected remainder reaches a shell. Host execution is
    # NEVER real in the foundry -- the shell's OUTPUT is simulated for a
    # small command set (the grammar of the vuln, not host RCE).
    out = []
    for part in re.split(r"\\s*(?:;|\\||&&|\\n|`)\\s*", cmd or ""):
        part = part.strip()
        if not part:
            continue
        if part.startswith("echo "):
            out.append(part[5:].strip().strip("'\\""))
        elif part in _SAFE_CMDS:
            out.append(_SAFE_CMDS[part])
    return out


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        raw = p.get(PARAM, "")
        sent = raw.replace(";", "") if VARIANT == "filtered" else raw
        # AUDIT FIX (foundry power review): the old guard mixed an
        # `and sent != raw` clause that was ALWAYS False on base/post
        # (sent == raw there), so a `;`-separated payload never fired --
        # only |/&/backtick/$. The correct test is simply: does the
        # string the shell actually receives carry a metachar? On
        # filtered the `;` is already stripped (that IS the filter), so
        # `|id` still fires (bypass) while `;id` does not (blocked).
        injected = bool(re.search(r"[|`&$;]", sent))
        cmds = _shell(sent)
        if injected and cmds:
            self._prove({"payload": raw, "out": cmds})
            return self._answer(True, "ping ok " + " ".join(cmds) + " " + FLAG)
        return self._answer(False, "ping ok " + raw, benign="ping ok")


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_SSRF = '''
_INTERNAL = {"internal-api": FLAG,
             "metadata": "role=admin\\nflag=" + FLAG,
             "secret": "aws-key=AKIA-SYNTH-FOUNDRY"}


def _fetch(tgt):
    # the bug: the server fetches whatever the client names. The foundry
    # NEVER dials out -- an in-memory internal namespace stands in for the
    # loopback/metadata services the vuln reaches.
    host = urlparse(tgt or "").hostname or ""
    if host in ("127.0.0.1", "localhost", "::1", "169.254.169.254",
                "metadata.google.internal") or "internal" in host:
        name = (urlparse(tgt or "").path or "/").strip("/") or "internal-api"
        return _INTERNAL.get(name, _INTERNAL["internal-api"]), True
    return "fetched " + (tgt or "")[:80], False


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        out, hit = _fetch(p.get(PARAM, ""))
        if hit:
            self._prove({"payload": p.get(PARAM), "body": out[:60]})
            return self._answer(True, out)
        return self._answer(False, out, benign=out)


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_IDOR = '''
OBJECTS = {1: ("lo", "invoice-1 total=10"), 2: ("duskyr", "invoice-2 total=99"),
           3: ("admin", "invoice-3 total=1337 " + FLAG)}


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        me = self.headers.get("X-User", "lo")
        oid = p.get(PARAM, "")
        try:
            oid = int(str(oid).strip())
        except Exception:
            return self._answer(False, "", benign="bad id")
        obj = OBJECTS.get(oid)
        if not obj:
            return self._answer(False, "", benign="not found")
        owner, body = obj
        if owner != me:
            # the bug: ownership is never checked
            self._prove({"user": me, "object": oid, "owner": owner})
            return self._answer(True, body)
        return self._answer(False, body, benign=body)


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_BOLA = '''
TENANTS = {"acme": {1: "acme-report-a", 2: "acme-report-b"},
           "globex": {1: "globex-secret " + FLAG, 2: "globex-report-b"}}


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        tok = self.headers.get("Authorization", "").replace("Bearer ", "")
        tenant = (tok.split(":") or [""])[0].strip() or "acme"
        oid = p.get(PARAM, "")
        try:
            oid = int(str(oid).strip())
        except Exception:
            return self._answer(False, "", benign="bad id")
        # the bug: the object is fetched by id alone -- the caller's tenant
        # is never compared to the object's tenant
        for t, objs in TENANTS.items():
            if oid in objs and t != tenant:
                self._prove({"caller": tenant, "object": oid, "owner": t})
                return self._answer(True, objs[oid])
        return self._answer(False, "own object", benign="own object")


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_JWT = '''
SECRET = "synth-hs256-secret"


def _b64(x):
    return base64.urlsafe_b64encode(x).rstrip(b"=").decode()


def _sign(h, p):
    return _b64(hmac.new(SECRET.encode(), (h + "." + p).encode(),
                         hashlib.sha256).digest())


def _unpad(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path == "/token":
            h = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
            pl = _b64(json.dumps({"sub": "lo", "role": "user"}).encode())
            return self._send(200, h + "." + pl + "." + _sign(h, pl),
                              "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        if VARIANT == "post" and not is_post:
            return self._send(405, "method not allowed")
        tok = self.headers.get("Authorization", "").replace("Bearer ", "").strip()
        parts = tok.split(".")
        if len(parts) == 3:
            try:
                hdr = json.loads(_unpad(parts[0]))
            except Exception:
                hdr = {}
            alg = str(hdr.get("alg") or "").lower()
            if alg == "none" or not parts[2].strip():
                # the bug: alg:none is honoured
                self._prove({"alg": hdr.get("alg"), "header": hdr})
                return self._answer(True, "admin ok " + FLAG)
            if alg == "hs256":
                try:
                    pl = json.loads(_unpad(parts[1]))
                except Exception:
                    pl = {}
                if pl.get("role") == "admin" and _sign(parts[0], parts[1]) == parts[2]:
                    self._prove({"alg": alg, "role": "admin", "forged": True})
                    return self._answer(True, "admin ok " + FLAG)
        return self._answer(False, "", benign="forbidden")


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_RACE = '''
COUPON = {"uses": 0, "limit": 1, "lock": threading.Lock()}


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        # the bug: check-then-act with a real window between the two
        if COUPON["uses"] < COUPON["limit"]:
            time.sleep(0.05)                # the window
            COUPON["uses"] += 1
            if COUPON["uses"] > COUPON["limit"]:
                self._prove({"uses": COUPON["uses"], "limit": COUPON["limit"]})
            return self._send(200, "redeemed " + FLAG)
        return self._send(409, "already used")


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_DESYNC = '''
BLOCKED = ("/admin", "/internal")


def _backend(method, path, body):
    # the BACKEND's parser: it trusts Content-Length
    if path in BLOCKED:
        STATE["exploited"] = True
        STATE["evidence"].append({"smuggled": path, "method": method})
        return 200, "backend: " + path + " " + FLAG
    return 200, "backend: " + path


class H(Base):
    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)

    def _route(self, is_post):
        u, p = self._read()
        if u.path == "/__oracle":
            return self._send(200, json.dumps(STATE), "application/json")
        if u.path != PATH:
            return self._send(404, "nope")
        raw = p.get("__raw__", "")
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n and not raw:
            self.rfile.read(0)
        head, _, tail = raw.partition("\\r\\n\\r\\n")
        # the FRONTEND sees only the first request; the remainder is
        # forwarded verbatim and the BACKEND parses it as a NEW request
        lines = [l for l in head.split("\\r\\n") if l.strip()]
        fp = (lines[0].split(" ")[1] if lines else "/")
        if fp in BLOCKED:
            return self._send(403, "blocked at the edge")
        if tail.strip():
            tl = [l for l in tail.split("\\r\\n") if l.strip()]
            sp = (tl[0].split(" ")[1] if tl else "/")
            code, out = _backend("SMUGGLED", sp, tail)
            self._prove({"front_saw": fp, "back_saw": sp})
            return self._send(200, out)
        return self._send(200, "frontend: " + fp)


def serve(port=0):
    srv = HTTPServer(("127.0.0.1", port), H)
    return srv, srv.server_address[1]
'''

_BODIES = {"sqli": _SQLI, "lfi": _LFI, "ssti": _SSTI, "cmdi": _CMDI,
           "ssrf": _SSRF, "idor": _IDOR, "bola": _BOLA, "jwt_alg": _JWT,
           "race": _RACE, "desync": _DESYNC}

# variant sets per class: race and desync are inherently shaped, so they
# declare only the shapes that make sense for them
_VARIANTS = {
    "sqli": ["base", "blind", "post", "filtered"],
    "lfi": ["base", "blind", "post", "filtered"],
    "ssti": ["base", "blind", "post", "filtered"],
    "cmdi": ["base", "blind", "post", "filtered"],
    "ssrf": ["base", "blind", "post"],
    "idor": ["base", "blind", "post"],
    "bola": ["base", "blind", "post"],
    "jwt_alg": ["base", "blind", "post"],
    "race": ["base"],
    "desync": ["base"],
}

_DEFAULTS = {
    "sqli": ("user", "/login"), "lfi": ("f", "/download"),
    "ssti": ("name", "/echo"), "cmdi": ("host", "/ping"),
    "ssrf": ("url", "/fetch"), "idor": ("id", "/api/object"),
    "bola": ("id", "/api/report"), "jwt_alg": ("", "/admin"),
    "race": ("", "/redeem"), "desync": ("__raw__", "/submit"),
}

_ACTIVE = {}


def _build_source(vuln_class, variant, param, path):
    body = _BODIES[vuln_class]
    src = (_PRE + body)
    src = (src.replace("@@CLASS@@", vuln_class)
              .replace("@@VARIANT@@", variant)
              .replace("@@PARAM@@", param)
              .replace("@@PATH@@", path))
    return src


def _compile(src):
    ns = {"__name__": "vuln_synth_target"}
    exec(compile(src, "<vuln_synth>", "exec"), ns)
    if "serve" not in ns:
        raise RuntimeError("synthesized target exposes no serve()")
    return ns


@register(name="vuln_synth",
          desc="FOUNDRY (Vague 4): synthesize a disposable, loopback-only target "
               "carrying exactly ONE real vulnerability of the requested class "
               "(sqli|lfi|ssti|cmdi|ssrf|idor|bola|jwt_alg|race|desync), on the "
               "finding's own param+path shape. Actions: classes | emit (return "
               "the target SOURCE) | start (live target, ephemeral port, returns "
               "target_id+url) | stop | list. Every target exposes /__oracle -- "
               "the GROUND TRUTH a weapon's claim is compared against. Never "
               "touches the host: cmdi/ssrf/ssti effects are simulated.",
          params={"type": "object", "properties": {
              "action": {"type": "string",
                         "enum": ["classes", "emit", "start", "stop", "list"],
                         "default": "classes",
                         "description": "classes: list classes+variants. emit: "
                                        "the generated source. start: live target "
                                        "(ephemeral port). stop: target_id. list: "
                                        "active targets"},
              "vuln_class": {"type": "string",
                             "description": "the class to synthesize"},
              "variant": {"type": "string",
                          "description": "base|blind|post|filtered (default base, "
                                         "validated per class)"},
              "param": {"type": "string",
                        "description": "the finding's parameter name (default: the "
                                       "class's canonical param)"},
              "path": {"type": "string",
                       "description": "the finding's path (default: the class's "
                                      "canonical path)"},
              "target_id": {"type": "string", "description": "for action=stop"},
          }, "required": ["action"]},
          danger="active")
def vuln_synth(action="classes", vuln_class=None, variant="base", param=None,
               path=None, target_id=None):
    act = (action or "classes").lower().strip()

    if act == "classes":
        return _v("vuln_synth", True,
                  f"{len(_BODIES)} synth classes -- the foundry's catalog",
                  classes={c: _VARIANTS[c] for c in _BODIES},
                  defaults={c: {"param": _DEFAULTS[c][0],
                                "path": _DEFAULTS[c][1]} for c in _BODIES})

    if act == "list":
        live = {tid: {"class": t["class"], "variant": t["variant"],
                      "url": t["url"], "exploited": t["ns"]["STATE"]["exploited"]}
                for tid, t in _ACTIVE.items()}
        return _v("vuln_synth", True, f"{len(live)} live synth target(s)",
                  targets=live)

    if act == "stop":
        t = _ACTIVE.pop(target_id or "", None)
        if not t:
            return _v("vuln_synth", False,
                      f"no live target {target_id!r} -- action=list shows them")
        try:
            t["server"].shutdown()
        except Exception:
            pass
        return _v("vuln_synth", True, f"target {target_id} stopped",
                  stopped=target_id)

    if act not in ("emit", "start"):
        return _v("vuln_synth", False,
                  f"unknown action {action!r} -- classes|emit|start|stop|list")

    cls = (vuln_class or "").lower().strip()
    if cls not in _BODIES:
        return _v("vuln_synth", False,
                  f"no synth for class {vuln_class!r} -- known: "
                  + ", ".join(_BODIES))
    var = (variant or "base").lower().strip()
    if var not in _VARIANTS[cls]:
        return _v("vuln_synth", False,
                  f"class {cls} has no variant {var!r} -- available: "
                  + ", ".join(_VARIANTS[cls]))
    d_param, d_path = _DEFAULTS[cls]
    p = (param or d_param).strip() or d_param
    pa = (path or d_path).strip() or d_path
    if not pa.startswith("/"):
        pa = "/" + pa
    src = _build_source(cls, var, p, pa)

    if act == "emit":
        return _v("vuln_synth", True,
                  f"synth source: {cls}/{var} on {pa} param={p} -- the PREY "
                  "code, with /__oracle as ground truth",
                  synth_class=cls, synth_variant=var, param=p, path=pa,
                  source=src)

    # action == start: live, ephemeral, loopback-only
    try:
        ns = _compile(src)
        srv, port = ns["serve"](0)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
    except Exception as ex:
        return _v("vuln_synth", False,
                  f"synth start failed: {type(ex).__name__}: {str(ex)[:160]}")
    tid = f"synth_{cls}_{var}_{port}"
    url = f"http://127.0.0.1:{port}"
    _ACTIVE[tid] = {"server": srv, "thread": th, "port": port, "url": url,
                    "class": cls, "variant": var, "ns": ns, "param": p,
                    "path": pa}
    return _v("vuln_synth", True,
              f"synth target LIVE: {cls}/{var} at {url}{pa} (param={p}) -- "
              f"oracle at {url}/__oracle. Stop it with action=stop.",
              synth_class=cls, synth_variant=var, target_id=tid, url=url,
              port=port, param=p, path=pa,
              probe_url=f"{url}{pa}", oracle_url=f"{url}/__oracle")