"""VOIDFORGE :: hardened transport — one HTTP core for the whole arsenal.

Every tool should send traffic through here. What you get for free:
  - DNS resilience: system resolver first, Cloudflare DoH fallback on
    failure, 5-minute cache. A transient resolver death can never again
    kill a chain (the Supabase lesson).
  - Response caching: identical GETs within TTL return cache_hit=true.
  - Jittered exponential backoff on 429/502/503/504 honoring Retry-After.
  - Full redirect chains INCLUDING 307/308 (urllib balks on those).
  - Passive intel: every completed response feeds the active blackboard —
    nothing observed is ever wasted.
"""
import hashlib, json, os, random, re, socket, ssl, threading, time
import urllib.request, urllib.error, urllib.parse

_DNS_CACHE = {}          # host -> (ip, ts)
_DNS_TTL = 300
_RESP_CACHE = {}         # cache_key -> (response_dict, ts)
_RESP_TTL = 90
_lock = threading.Lock()
_installed = False

import random as _rnd

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

# ── wave2 P3: UA CONSISTENCY — random UA per request was our #1 bot tell.
# Same target host → same UA for the whole campaign (deterministic pick);
# process-level default frozen too. Source: captcha_proxies/SYNTHESE.md §1.3
# (camoufox/patchright consistency rules).
_SESSION_UA = _UA_POOL[_rnd.randrange(len(_UA_POOL))]
_UA_BY_HOST = {}

def _ua_for(host):
    """Tier C — l'identité opérationnelle parle d'abord (stable par cible,
    brûlée sur bloc). Fallback: le pool UA historique."""
    try:
        from core.op_identity import identity_for
        return identity_for(host, renew=True)["ua"]
    except Exception:
        pass
    host = (host or "").lower()
    if host not in _UA_BY_HOST:
        idx = int(hashlib.sha1(host.encode()).hexdigest(), 16) % len(_UA_POOL)
        _UA_BY_HOST[host] = _UA_POOL[idx]
    return _UA_BY_HOST[host]

def _ua():
    return _SESSION_UA

UA = _SESSION_UA  # backward compat for code that reads UA directly


# ── resilient DNS ────────────────────────────────────────────────
def _doh_resolve(host):
    """Resolve via Cloudflare DoH (bootstrapped by raw IP — no chicken/egg).
    The IP-pinned request skips hostname verification: the cert is for
    cloudflare-dns.com but we dial the literal IP, which we trust by pin."""
    import ssl
    ctx = ssl.create_default_context()
    # Don't disable verification — just skip hostname check for IP-pinned connection
    # The cert chain is still validated against the CA bundle
    ctx.check_hostname = False  
    ctx.verify_mode = ssl.CERT_REQUIRED
    for boot in ("1.1.1.1", "1.0.0.1"):
        try:
            url = f"https://{boot}/dns-query?name={host}&type=A"
            rq = urllib.request.Request(url, headers={"accept": "application/json",
                                                      "user-agent": _ua()})
            with urllib.request.urlopen(rq, timeout=6, context=ctx) as r:
                data = json.loads(r.read().decode())
            for ans in data.get("Answer", []):
                if ans.get("type") == 1:
                    return ans["data"]
        except Exception:
            continue
    return None


def _smart_getaddrinfo(host, port, *a, **kw):
    # Defer IPv6/explicit-family requests to the stock resolver.
    if a and a[0] == socket.AF_INET6:
        return socket._orig_getaddrinfo(host, port, *a, **kw)
    now = time.time()
    with _lock:
        cached = _DNS_CACHE.get(host)
        # X1.2 (audit-3): expired entries were never removed — a long-lived
        # FastAPI session accumulated thousands of dead host->IP mappings.
        # Purge stale entries opportunistically at write time (cheap: only
        # when the dict grows past a threshold).
        if cached and now - cached[1] < _DNS_TTL:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (cached[0], port))]
        if len(_DNS_CACHE) > 512:
            for _h in [h for h, (_, ts) in _DNS_CACHE.items()
                       if now - ts >= _DNS_TTL]:
                _DNS_CACHE.pop(_h, None)
    try:
        res = socket._orig_getaddrinfo(host, port, *a, **kw)
        # E-1: ne cacher QUE de l'AF_INET — stocker une IP v6 (résultat
        # AAAA-first) pour la rendre ensuite en tuple AF_INET = connect fail
        # sur tout hôte v6-first, pendant tout le TTL.
        v4 = next((r for r in (res or ()) if r[0] == socket.AF_INET), None)
        if v4 and v4[4][0]:
            with _lock:
                _DNS_CACHE[host] = (v4[4][0], now)
        return res
    except socket.gaierror:
        ip = _doh_resolve(host)
        if ip:
            with _lock:
                _DNS_CACHE[host] = (ip, now)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        raise


def install_resolver():
    """Patch getaddrinfo once process-wide so EVERY tool gains DoH fallback."""
    global _installed
    if _installed:
        return
    # R3-26: save+patch sous _lock — sans garde atomique, le 2e thread de
    # batch_execute sauvait la fonction DÉJÀ patchée comme _orig_getaddrinfo
    # → récursion infinie sur tout le trafic (DoH inclus) jusqu'au restart.
    with _lock:
        if not _installed and not hasattr(socket, "_orig_getaddrinfo"):
            socket._orig_getaddrinfo = socket.getaddrinfo
            socket.getaddrinfo = _smart_getaddrinfo
        _installed = True


# ── the fetch core ───────────────────────────────────────────────
# ── ROE global governor (engagement.yaml max_request_rate) ──
_ROE_LOCK = threading.Lock()
# X3.3 (audit-3): list.pop(0) is O(n) — every request shifted the whole
# window. deque.popleft is O(1).
from collections import deque as _deque
_ROE_WINDOW = _deque()  # timestamps of recent outbound calls (all tools, all threads)
_ROE_LIMIT = 120  # default; reloaded from engagement.yaml
_ROE_LOADED = [False]

def _roe_limit():
    global _ROE_LIMIT  # fix: sans ceci, le return lit un local jamais bindé au 2e appel
    if not _ROE_LOADED[0]:
        try:
            import yaml as _y
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             os.pardir, "config", "engagement.yaml")
            with open(p, encoding="utf-8") as f:
                d = _y.safe_load(f) or {}
            _ROE_LIMIT = int(((d.get("engagement") or {})
                              .get("rules_of_engagement") or {})
                             .get("max_request_rate") or 120)
        except Exception:
            pass
        _ROE_LOADED[0] = True
    return _ROE_LIMIT

def _roe_gate():
    """Block until an outbound slot opens — global, every transport call.
    E1: the active profile may SHAPE the wait (jitter envelope) but can
    never loosen the ROE limit — the governor stays above everything."""
    lim = _roe_limit()
    prof = _profile()
    j = prof.get("jitter") or [1.0, 1.0]
    try:
        lo, hi = abs(float(j[0])), abs(float(j[1]))
    except Exception:
        lo, hi = 1.0, 1.0
    wait = 0.25 * max(1.0, min(lo, hi) + (max(lo, hi) - min(lo, hi)) *
                      random.random())
    while True:
        with _ROE_LOCK:
            now = time.time()
            while _ROE_WINDOW and now - _ROE_WINDOW[0] >= 60.0:
                _ROE_WINDOW.popleft()   # X3.3: O(1) au lieu de O(n)
            if len(_ROE_WINDOW) < lim:
                _ROE_WINDOW.append(now)
                return
        time.sleep(wait)


# ── E1: malleable traffic profiles — the detection surface is DATA ──
# config/transport.yaml → transport.profiles.<name>: {headers: {Name: value,
# ordered by declaration for reference}, header_order: [..], referer: "...",
# origin: "...", jitter: [lo, hi], ua_family: "chrome|firefox|safari|any"}
# Resolution precedence: tool headers > profile > identity > defaults.
# The profile may SET headers; it NEVER rewrites User-Agent after identity
# (single-writer rule) and NEVER loosens the ROE limit (governor stays above).
_PROFILE = [None]          # resolved profile cache (per process)
_PROFILE_LOADED = [False]
_PROFILE_LOCK = threading.Lock()

# the ONLY header op_identity owns — profiles never touch it post-identity
_IDENTITY_OWNED = {"User-Agent", "Accept-Language"}


def _load_profile():
    if _PROFILE_LOADED[0]:
        return _PROFILE[0]
    with _PROFILE_LOCK:
        if _PROFILE_LOADED[0]:
            return _PROFILE[0]
        _PROFILE_LOADED[0] = True
        try:
            import yaml as _y
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             os.pardir, "config", "transport.yaml")
            with open(p, encoding="utf-8") as f:
                d = _y.safe_load(f) or {}
            t = d.get("transport") or {}
            name = t.get("profile") or ""
            profs = t.get("profiles") or {}
            prof = profs.get(name) if name and isinstance(profs, dict) else None
            if isinstance(prof, dict):
                prof = dict(prof)
                prof["__name"] = name
                _PROFILE[0] = prof
        except Exception:
            _PROFILE[0] = None
    return _PROFILE[0]


def _profile():
    return _load_profile() or {}


def profile_hash():
    """Short fingerprint of the ACTIVE traffic shape (for the ROE header):
    which profile is on duty + a hash of its declared shape. Data, not code."""
    prof = _profile()
    if not prof:
        return "default"
    shape = json.dumps({k: v for k, v in prof.items()
                        if not k.startswith("__")}, sort_keys=True,
                       ensure_ascii=False, default=str)
    import hashlib as _h
    return f"{prof.get('__name', '?')}:{_h.sha1(shape.encode()).hexdigest()[:8]}"


def _apply_profile(h: dict, host: str, scheme: str = "https"):
    """Layer the active profile onto the built header dict. AUDIT E1-A2:
    writes NOTHING but real headers — any dunder/meta key placed in h
    would be sent on the wire verbatim by urllib.Request. Single-writer:
    identity already wrote UA/Accept-Language; tool headers (applied by
    the caller AFTER this) win over both."""
    prof = _profile()
    if not prof:
        return
    hdrs = prof.get("headers") or {}
    if isinstance(hdrs, dict):
        for k, v in hdrs.items():
            if k not in _IDENTITY_OWNED:
                h[k] = v
    for gk in ("Referer", "Origin"):
        gv = prof.get(gk.lower())
        if gv and isinstance(gv, str):
            # {TARGET} generalized to the CURRENT scheme + host (not
            # always https — AUDIT E1-A3)
            h.setdefault(gk, gv.replace("{TARGET}", f"{scheme}://{host}"))


def transport_posture() -> str:
    """One-line live posture for the OPERATOR-AGENT prompt block (the LLM
    must SEE the transport law it operates under: profile shape, egress,
    identity). Failure degrades to empty string, never crashes run()."""
    try:
        prof = _profile()
        name = prof.get("__name") if prof else None
        ph = profile_hash()
        from core.scrub import egress_summary
        eg = egress_summary()
        try:
            from core.op_identity import summary as _is
            ids = _is()
            idn = f"{len(ids.get('live', []))} live / " \
                  f"{len(ids.get('burned', []))} burned"
        except Exception:
            idn = "n/a"
        mode = (eg or {}).get("mode", "direct")
        exits = len((eg or {}).get("exits", []) or [])
        shape = name if name else "default (no profile)"
        return (f"TRANSPORT POSTURE: traffic profile {shape} [{ph}] — "
                f"one profile per campaign, chosen OPERATOR-side, never "
                f"flipped mid-flight; egress {mode}"
                + (f" ({exits} exits, sticky per target)" if exits else "")
                + f"; op identity {idn} — burn on block is automatic, "
                f"never forge identity headers yourself.")
    except Exception:
        return ""


# ── wave2 P1/P2: optional proxy pool — config/transport.yaml, OFF by default.
# Validation-real entries, health by fail_count, cooldown for sick exits,
# rotate-on-block (403/406/429 or WAF body) via a different exit. The ROE
# governor stays ABOVE the pool — a proxy never changes the allowed cadence.
_POOL = []
_POOL_LOADED = [False]
_STICKY = {}  # host -> proxy_url : un exit par cible, session-consistent
_WAF_SIGS = ("waf", "cloudflare", "sucuri", "captcha", "just a moment",
             "cf-mitigated", "attention required")

def _looks_blocked(body):
    low = (body or "").lower()[:1500]
    return any(s in low for s in _WAF_SIGS)

def _load_pool():
    if not _POOL_LOADED[0]:
        try:
            import yaml as _y
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             os.pardir, "config", "transport.yaml")
            with open(p, encoding="utf-8") as f:
                d = _y.safe_load(f) or {}
            for u in ((d.get("transport") or {}).get("proxies") or [])[:50]:
                if isinstance(u, str) and "://" in u:
                    _POOL.append({"url": u, "fail_count": 0, "cooldown_until": 0.0})
        except Exception:
            pass
        _POOL_LOADED[0] = True
    return _POOL

def _pool_next(exclude=None, host=None):
    """Least-failing healthy exit, excluding tried ones. None si pool vide.
    STICKY par cible : le même host réutilise le même exit tant qu'il est
    sain — les sessions authentifiées (cf_clearance, __session) sont liées
    à l'IP de sortie ; un exit qui change au milieu d'une campagne = détection
    instantanée. La rotation ne survit QUE sur blocage (mark False → exclus)."""
    pool = _load_pool()
    now = time.time()
    with _lock:
        cand = [e for e in pool
                if e["cooldown_until"] < now and e["url"] not in (exclude or set())]
        if not cand:
            if host:
                _STICKY.pop(host, None)
            return None
        sticky = _STICKY.get(host or "")
        if sticky and sticky in {c["url"] for c in cand}:
            return sticky
        pick = min(cand, key=lambda x: x["fail_count"])["url"]
        if host:
            _STICKY[host] = pick
        return pick

def _pool_mark(url, ok):
    with _lock:
        for e in _POOL:
            if e["url"] == url:
                if ok:
                    e["fail_count"] = 0
                else:
                    e["fail_count"] += 1
                    if e["fail_count"] >= 3:
                        e["cooldown_until"] = time.time() + 120.0  # 2 min de repos


_HOST_FAILS = {}   # host -> consecutive non-2xx count (identity-burn signal)
_HOST_FAILS_LOCK = threading.Lock()


def _mark_host_result(host, status, sub=False):
    """Tier C — 4 refus consécutifs sur une cible = l'identité parle mal.
    Burn : la prochaine requête part avec un accent neuf.

    AUDIT F2: tous les non-2xx ne se valent pas — 404 est le bruit NORMAL
    du dir_brute, pas un rejet d'identité ; seuls les rejets VRAIS
    (403/429/WAF, 5xx répétés) comptent. F7: les chemins récursifs
    (redirect follow / proxy rotation) re-marquent le même appel → flag
    _sub pour ne compter qu'une fois par requête de l'opérateur."""
    if sub:
        return
    n = 0
    try:
        host = host or ""
        hard_reject = status in (403, 407, 429, 503)
        soft_5xx = (status or 0) >= 500
        with _HOST_FAILS_LOCK:
            if 200 <= (status or 0) < 300 or status in (301, 302, 303, 404):
                _HOST_FAILS[host] = 0
                return
            if not (hard_reject or soft_5xx):
                return  # 4xx non-rejet (404 déjà traité) : ni strike ni reset
            n = _HOST_FAILS.get(host, 0) + 1
            _HOST_FAILS[host] = n
            if n >= 4:
                _HOST_FAILS[host] = 0
        if n >= 4:
            from core.op_identity import burn as _id_burn
            _id_burn(host, f"{status} x{n} consecutive")
    except Exception:
        pass


# ── Phase 0.3: per-host circuit breaker (nuclei hosterrorscache) ──────────
# Transport-death quarantine: 3 consecutive network-level failures
# (timeout / refused / reset / DNS — status -1) = the host is DOWN or
# blackholing us. Martyr-retrying it burns budget and pacer slots while
# the mission should pivot. Quarantine carries a CAUSE (the last
# exception class), expiry (probe again after it), and success-removes
# (nuclei discipline: a success clears the whole entry, not a count).
_TRANSPORT_FAILS = {}    # host -> {"count": int, "cause": str, "until": ts}
_TB_LOCK = threading.Lock()
_TB_THRESHOLD = 3        # consecutive transport deaths to quarantine
_TB_COOLDOWN = 300.0     # seconds a quarantined host stays dark (probe window)
_TB_MAX_HOSTS = 4096     # bound: a scan of a /24 must not OOM the breaker


def _tb_mark_locked(host, cause):
    e = _TRANSPORT_FAILS.get(host)
    if not e:
        e = {"count": 0, "cause": "", "until": 0.0}
        _TRANSPORT_FAILS[host] = e
    e["count"] += 1
    e["cause"] = str(cause or "transport")[:60]
    if e["count"] >= _TB_THRESHOLD:
        e["until"] = time.time() + _TB_COOLDOWN
    # bound: /24-scale scans must not OOM the breaker
    if len(_TRANSPORT_FAILS) > _TB_MAX_HOSTS:
        for k in sorted(_TRANSPORT_FAILS,
                        key=lambda k: _TRANSPORT_FAILS[k].get("until", 0)):
            _TRANSPORT_FAILS.pop(k, None)
            if len(_TRANSPORT_FAILS) <= _TB_MAX_HOSTS:
                break


def _tb_success(host):
    """nuclei discipline: success = FULL removal, not a decrement."""
    with _TB_LOCK:
        _TRANSPORT_FAILS.pop(host, None)


def host_quarantined(host, refresh=False):
    """Is this host quarantined (transport-dead)? When refresh=True the
    stale entry (cooldown elapsed) is reaped so a later probe can retry.
    Returns None or {"host","cause","until","remaining_s"}."""
    if not host:
        return None
    with _TB_LOCK:
        e = _TRANSPORT_FAILS.get(host)
        if not e:
            return None
        if e.get("until", 0) > time.time():
            return {"host": host, "cause": e.get("cause"),
                    "until": e["until"],
                    "remaining_s": round(e["until"] - time.time(), 1)}
        if refresh:
            _TRANSPORT_FAILS.pop(host, None)
        return None


def _tb_observe(host, out):
    """Post-fetch bookkeeping: transport death marks, live host clears.
    Called from fetch()'s epilogue; never raises (a breaker that crashes
    the transport it guards is worse than no breaker). Status -1 is the
    only real transport-death signal on the wire path (budget-dead -2
    and breaker-skip -3 must NOT re-mark: they'd auto-perpetuate)."""
    try:
        host = host or ""
        st = (out or {}).get("status")
        if st == -1:
            with _TB_LOCK:
                _tb_mark_locked(host, str(out.get("body") or "")[:60])
        elif st and st > 0:
            _tb_success(host)
    except Exception:
        pass


def fetch_skips_quarantined(host):
    """Fast pre-check for batch tools: skip firing at a dark host.
    Reaps the stale entry so the cooldown expiry actually re-arms."""
    return host_quarantined(host, refresh=True) is not None


# ── wave2 P4: captcha hook — detection + solver auto-injection (OFF sans config)
# Source: captcha_proxies/SYNTHESE.md §1.1 — submit → poll → inject. Budget ROE
# style: 3 résolutions max par process, 1 tentative par (host, sitekey).
_CAPTCHA_CFG = [None]   # dict {provider, api_key, poll_timeout} | {"provider": "none"}
_CAPTCHA_CFG_LOADED = [False]
_CAPTCHA_DONE = set()   # (host, sitekey) déjà tentés
# X3.2 (audit-3): the budget was process-global [3] — the first mission
# that burned 3 solves left EVERY later target captcha-blind in a long-
# lived FastAPI session. Now: 3 per HOST, refilled when a new mission
# starts (mission boundary = fresh operational budget).
_CAPTCHA_BUDGET = {}   # host -> remaining solves

_CAPTCHA_COOKIE = {"turnstile": "cf-turnstile-response",
                   "hcaptcha": "h-captcha-response",
                   "recaptcha": "g-recaptcha-response"}
_CAPSOLVER_TYPE = {"turnstile": "AntiTurnstileTaskProxyLess",
                   "hcaptcha": "AntiHCaptchaTaskProxyLess",
                   "recaptcha": "ReCaptchaV2TaskProxyLess"}


def _captcha_cfg():
    if not _CAPTCHA_CFG_LOADED[0]:
        try:
            import yaml as _y
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             os.pardir, "config", "transport.yaml")
            with open(p, encoding="utf-8") as f:
                d = _y.safe_load(f) or {}
            _CAPTCHA_CFG[0] = (d.get("transport") or {}).get("captcha") or {"provider": "none"}
        except Exception:
            _CAPTCHA_CFG[0] = {"provider": "none"}
        _CAPTCHA_CFG_LOADED[0] = True
    return _CAPTCHA_CFG[0]


def _captcha_challenge(body):
    """(type, sitekey) si la réponse porte un challenge — sinon None."""
    low = (body or "").lower()
    m = re.search(r'(?:data-sitekey|sitekey)["\']?\s*[:=]\s*["\']?([0-9A-Za-z_\-]{20,})',
                  body or "", re.I)
    if not m:
        return None
    sitekey = m.group(1)
    if "turnstile" in low or "cf-turnstile" in low:
        return ("turnstile", sitekey)
    if "hcaptcha" in low:
        return ("hcaptcha", sitekey)
    if "recaptcha" in low or "g-recaptcha" in low:
        return ("recaptcha", sitekey)
    return None


def _captcha_solve(ctype, sitekey, pageurl, host=None):
    """Token via le provider configuré — None si non configuré/échec.
    X3.2: budget PER HOST (3 each), not process-global."""
    cfg = _captcha_cfg()
    provider, key = (cfg.get("provider") or "none"), (cfg.get("api_key") or "")
    _h = host or urllib.parse.urlsplit(pageurl or "").netloc or "unknown"
    if _CAPTCHA_BUDGET.get(_h, 3) <= 0:
        return None
    if provider == "none" or not key:
        return None
    _CAPTCHA_BUDGET[_h] = _CAPTCHA_BUDGET.get(_h, 3) - 1
    timeout = int(cfg.get("poll_timeout") or 120)
    try:
        if provider == "capsolver":
            rq = urllib.request.Request(
                "https://api.capsolver.com/createTask",
                data=json.dumps({"clientKey": key, "task": {
                    "type": _CAPSOLVER_TYPE[ctype], "websiteURL": pageurl,
                    "websiteKey": sitekey}}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(rq, timeout=20) as r:
                task_id = json.loads(r.read().decode()).get("taskId")
            if not task_id:
                return None
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(2)
                rq = urllib.request.Request(
                    "https://api.capsolver.com/getTaskResult",
                    data=json.dumps({"clientKey": key, "taskId": task_id}).encode(),
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(rq, timeout=20) as r:
                    res = json.loads(r.read().decode())
                if res.get("status") == "ready":
                    return (res.get("solution") or {}).get("token")
            return None
        # 2captcha (in.php/res.php, json=1)
        method = {"turnstile": "turnstile", "hcaptcha": "hcaptcha",
                  "recaptcha": "userrecaptcha"}[ctype]
        q = urllib.parse.urlencode({"key": key, "method": method,
                                    "sitekey": sitekey, "pageurl": pageurl, "json": 1})
        with urllib.request.urlopen(f"https://2captcha.com/in.php?{q}", timeout=20) as r:
            res = json.loads(r.read().decode())
        if str(res.get("status")) != "1":
            return None
        cid = res.get("request")
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(5)
            with urllib.request.urlopen(
                    f"https://2captcha.com/res.php?key={key}&action=get&id={cid}&json=1",
                    timeout=20) as r:
                res = json.loads(r.read().decode())
            if str(res.get("status")) == "1":
                return res.get("request")
        return None
    except Exception:
        return None


# ── wave2 P5: impersonation TLS/JA3 via curl_cffi (optionnelle) — le coup qui
# fait tomber les faux captchas (Cloudflare check TLS) sans jamais les résoudre.
_IMPERSONATE = [None, False]  # [profil, load_attempted]

def _imp_profile():
    if not _IMPERSONATE[1]:
        _IMPERSONATE[1] = True
        try:
            import yaml as _y
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             os.pardir, "config", "transport.yaml")
            with open(p, encoding="utf-8") as f:
                d = _y.safe_load(f) or {}
            prof = (d.get("transport") or {}).get("impersonate") or None
            if prof and prof != "none":
                import importlib.util as _iu
                if _iu.find_spec("curl_cffi") is not None:
                    _IMPERSONATE[0] = str(prof)
        except Exception:
            pass
    return _IMPERSONATE[0]


def _cache_key(method, url, headers, body):
    auth = ""
    hdr_digest = ""
    if headers:
        auth = "|".join(f"{k}={v}" for k, v in sorted(headers.items())
                        if k.lower() in ("authorization", "apikey", "cookie"))
        # C-T3: les headers NON-cred participent aussi à la clé — deux GET
        # même URL avec des headers différents (UA custom, X-Session, …)
        # ne doivent pas partager l'entrée de cache (bleed inter-sessions).
        try:
            hdr_digest = hashlib.blake2b(
                json.dumps(sorted(headers.items()), default=str).encode()
            ).hexdigest()[:8]
        except Exception:
            hdr_digest = ""  # headers non-serialisables → comportement d'avant
    raw = (f"{method}|{url}|{auth}|{hdr_digest}|"
           f"{json.dumps(body, sort_keys=True) if body else ''}")
    return hashlib.sha256(raw.encode()).hexdigest()


# ── R3-23/25: Retry-After honoré (delta-seconds OU HTTP-date), TOUJOURS borné —
# un 429 « Retry-After: 999999 » ne gare plus un tool call 11,5 jours.
_RETRY_AFTER_MAX = 30.0

def _retry_after_delay(ra, delay):
    """Délai d'attente dérivé de Retry-After; fallback = backoff jitteré."""
    ra = (ra or "").strip()
    if ra.isdigit():
        return min(float(ra), _RETRY_AFTER_MAX)
    if ra:
        try:
            import email.utils as _eu
            from datetime import timezone as _tz
            dt = _eu.parsedate_to_datetime(ra)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)  # "-0000" = UTC naive (RFC 7231)
            delta = dt.timestamp() - time.time()
            if delta > 0:
                return min(delta, _RETRY_AFTER_MAX)
            return 0.0  # date déjà passée → retry immédiat
        except Exception:
            pass
    return delay * (1 + random.random())


# ── R3-25: budget wall-clock global de fetch() — toute la chaîne (retries,
# redirects, captcha, rotation proxy) partage la même deadline; à expiration on
# rend le dernier état avec error="budget_exceeded" au lieu de dormir encore.
_FETCH_BUDGET_S = 300.0

def _budget_out(url, redirect_chain, attempts, status=-1, headers=None):
    return {"status": status, "body": "", "headers": headers or {}, "size": 0,
            "url": url, "final_url": url, "redirect_chain": redirect_chain,
            "cache_hit": False, "attempts": attempts,
            "error": "budget_exceeded"}


# ── R3-31: ces headers ne sont JAMAIS rejoués vers un autre host (redirect)
_CRED_HDRS = ("authorization", "proxy-authorization", "cookie", "apikey",
              "api-key", "x-api-key", "x-auth-token", "x-csrftoken",
              "x-xsrf-token")


def _resp_cache_evict_locked():
    """E-5: eviction simple (à appeler sous _lock) — sans purge les entrées
    expirées restaient dans le dict pour toujours (croissance illimitée).
    X1.3: cap 500 -> 300 (entries now hold compact bodies, but volume
    still bounds memory)."""
    if len(_RESP_CACHE) <= 300:
        return
    now = time.time()
    for k in [k for k, (_, ts) in _RESP_CACHE.items() if now - ts >= _RESP_TTL]:
        _RESP_CACHE.pop(k, None)
    if len(_RESP_CACHE) > 300:  # encore trop → on jette les plus vieilles
        for k, _ in sorted(_RESP_CACHE.items(),
                           key=lambda kv: kv[1][1])[:len(_RESP_CACHE) - 300]:
            _RESP_CACHE.pop(k, None)


# ── Phase 0.4: in-flight coalescer (nuclei cluster-before-send, our shape).
# nuclei hashes single-request templates and fans ONE wire request to N
# matcher sets. Our fleet's duplication isn't sequential (the cache owns
# that) — it's SIMULTANEOUS: batch tools fire parallel probes on the same
# endpoint, swarm/inner strikes duplicate the same recon call. The
# coalescer: the first caller flies the request; concurrent identical
# callers join the same flight and receive the same response dict.
# Only for cacheable GETs (strikes with bodies / methods ≠ GET stay
# un-coalesced: side effects must hit the wire).
_INFLIGHT = {}          # cache_key -> threading.Event + shared out
_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT_MAX = 64      # bound concurrent coalesced flights


def _inflight_join(cache_key, make):
    """Join the flight for cache_key or become the flyer. make() runs the
    real fetch; joiners block on the event and receive a copy of the
    response. The flyer pops the flight entry in finally and passes the
    result through the box BEFORE setting the event (joiners waking on a
    corpse flight re-fly solo). Only called for GETs (see fetch)."""
    if not cache_key:
        return make()
    with _INFLIGHT_LOCK:
        slot = _INFLIGHT.get(cache_key)
        if slot is not None:
            joiner_ev, joiner_box = slot
        elif len(_INFLIGHT) < _INFLIGHT_MAX:
            ev = threading.Event()
            box = []
            _INFLIGHT[cache_key] = (ev, box)
            flyer = True
        else:
            flyer = False
            joiner_ev = None
            joiner_box = None
    if slot is None:
        if flyer:
            # ── flyer path: run the request, publish, wake joiners ──
            out = None
            try:
                out = make()
            finally:
                with _INFLIGHT_LOCK:
                    ev, box = _INFLIGHT.pop(cache_key, (None, None))
                if ev is not None and out is not None:
                    box.append(out)
                    ev.set()
                elif ev is not None:
                    ev.set()      # corpse wake: joiners re-fly solo
            return out
        return make()          # at flight capacity: solo
    # ── joiner path: block for the flyer's result ──
    joiner_ev.wait(timeout=180)
    if joiner_box:
        return dict(joiner_box[0])
    return make()              # corpse flight (timeout/expiry): fly solo


def _cache_store_locked(cache_key, out):
    """Shared cache-write for the coalescer flyer and fetch()'s epilogue
    (Phase 0.4: the flyer runs the wire body but never reaches fetch()'s
    epilogue — the cache write is factored out so joiners and later
    callers both benefit). Caller holds no lock; this takes _lock."""
    if not cache_key or (out or {}).get("status") != 200:
        return
    with _lock:
        _compact = dict(out)
        if len(_compact.get("body") or "") > 40_000:
            _compact["body"] = _compact["body"][:40_000] + "…[cache-compacted]"
            _compact["cache_compacted"] = True
        _RESP_CACHE[cache_key] = (_compact, time.time())
        _resp_cache_evict_locked()  # E-5: purge des expirées + cap


def fetch(url, method="GET", headers=None, body=None, timeout=25,
          use_cache=True, retries=2, _redirects=0, redirect_chain=None,
          _proxy_tried=None, deadline=None, _nocoalesce=False,
          _coalesce_key=None):
    """One HTTP call with everything on. Returns a dict:
    {status, body, headers, size, url, final_url, redirect_chain, cache_hit, attempts}
    Proxy pool (config/transport.yaml) + rotate-on-block are transparent.
    deadline: budget wall-clock partagé par toute la chaîne (défaut 300 s)."""
    install_resolver()
    if deadline is None:
        deadline = time.time() + _FETCH_BUDGET_S
    redirect_chain = list(redirect_chain or [])
    # ── W15 (mission-79 autopsy): body + default-GET = GET-with-body,
    # and the body never reaches the wire (FastAPI answers 422 "Field
    # required" on a strike that was never truly sent). A body present
    # with no explicit method IS a POST. ──
    if body is not None and str(method).upper() == "GET":
        method = "POST"
    method = method.upper()
    host = urllib.parse.urlsplit(url).netloc
    _scheme = urllib.parse.urlsplit(url).scheme or "https"
    h = {"User-Agent": _ua_for(host)}
    # Tier C — l'accent linguistique de l'identité (cohérent tout le cycle
    # de vie de la cible).
    try:
        from core.op_identity import identity_for
        _il = identity_for(host, renew=True).get("lang")
        if _il:
            h["Accept-Language"] = _il
    except Exception:
        pass
    # E1 — la forme du trafic (profil malleable) se couche AVANT les
    # headers de l'outil: priorité finale = tool > profil > identité
    # (single-writer: le profil ne touche JAMAIS UA/Accept-Language).
    # AUDIT E1-A2: aucun pointeur méta ne transite par h (tout h part
    # sur le fil tel quel via urllib.Request).
    try:
        _apply_profile(h, host, scheme=_scheme)
    except Exception:
        pass
    if headers:
        h.update({k: v for k, v in headers.items()})

    # E-3: cache-hit checké AVANT _roe_gate — un GET déjà caché ne doit ni
    # bloquer ni consommer un slot du rate global.
    cache_key = None
    if method == "GET" and use_cache and _redirects == 0 and not _proxy_tried:
        cache_key = _cache_key(method, url, headers, None)
        with _lock:
            hit = _RESP_CACHE.get(cache_key)
        if hit and time.time() - hit[1] < _RESP_TTL:
            out = dict(hit[0])
            out["cache_hit"] = True
            return out
        # ── Phase 0.4: in-flight coalescing — concurrent identical GETs
        # join ONE wire flight (nuclei cluster-before-send, our shape).
        # The inner re-entry flies the real request with _nocoalesce=True
        # (no recursive join) and writes the cache itself via the shared
        # helper — joiners and the flyer all hold the same response.
        if not _nocoalesce:
            key = cache_key
            return _inflight_join(key, lambda: fetch(
                url, method=method, headers=headers, body=body,
                timeout=timeout, use_cache=False, retries=retries,
                _redirects=_redirects, redirect_chain=redirect_chain,
                _proxy_tried=_proxy_tried, deadline=deadline,
                _nocoalesce=True, _coalesce_key=key))

    # ── Phase 0.3: circuit breaker fast-skip — a quarantined (transport-
    # dead) host gets ONE synthetic refusal instead of a martyr volley.
    # Cache still serves (above); fresh wires are refused until cooldown.
    # Stale quarantine (cooldown elapsed) is reaped here → probe re-arms.
    _q = host_quarantined(host, refresh=True)
    if _q:
        try:
            from core import skip_ledger as _sl
            _sl.skip("quarantined", tool="transport",
                     detail=f"host {host} dark ({_q['cause']})")
        except Exception:
            pass
        return {"status": -3, "body": f"host quarantined (transport breaker): "
                                      f"{_q['cause']}",
                "headers": {}, "size": 0, "url": url, "final_url": url,
                "redirect_chain": redirect_chain, "cache_hit": False,
                "attempts": 0, "quarantine": _q}

    _roe_gate()  # ROE max_request_rate — global outbound discipline

    data = None
    if body is not None:
        data = json.dumps(body).encode() if isinstance(body, (dict, list)) else (
            body.encode() if isinstance(body, str) else body)
        h.setdefault("Content-Type", "application/json")

    # ── proxy selection (P1): direct first, pool on block-retry (P2) ──
    # sticky-per-host : sessions liées à l'IP de sortie, jamais de churn.
    _proxy_tried = set(_proxy_tried or ())
    proxy_url = _pool_next(exclude=_proxy_tried, host=host)
    if proxy_url:
        _proxy_tried.add(proxy_url)
        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(handler)
        rq_method = opener.open
    else:
        rq_method = urllib.request.urlopen

    prof = _imp_profile()  # P5: impersonation TLS/JA3 — off sans config
    attempt, delay = 0, 1.0
    while True:
        if time.time() > deadline:  # R3-25: budget épuisé → on rend la main
            return _budget_out(url, redirect_chain, attempt)
        attempt += 1
        if prof and attempt == 1:
            # P5 fast-path: TLS/JA3 fingerprint d'un vrai navigateur — la
            # majorité des checks CDN passent ICI, sans jamais voir un captcha.
            try:
                from curl_cffi import requests as _cr
                r = _cr.request(method, url, headers=h, data=data,
                                timeout=timeout, impersonate=prof,
                                proxies=({"http": proxy_url, "https": proxy_url}
                                         if proxy_url else None),
                                allow_redirects=False)
                if r.status_code not in (301, 302, 303, 307, 308):
                    # X1.1 (audit-3): unbounded read — a 20MB SPA/bundle was
                    # an OOM vector and a guaranteed provider 400 downstream.
                    # 500KB: generous for any legitimate page, lethal for
                    # memory bombs.
                    raw = r.text[:500_000]
                    out = {"status": r.status_code, "body": raw,
                           "headers": {k.lower(): v for k, v in r.headers.items()},
                           "size": len(raw), "url": url, "final_url": str(r.url),
                           "redirect_chain": redirect_chain, "cache_hit": False,
                           "attempts": 1, "impersonated": prof}
                    break
                # C-T1: la réponse 3xx curl EST le résultat — jamais de
                # re-send identique via urllib (double request). On suit le
                # redirect avec la MÊME logique que le chemin urllib
                # (HTTPError 3xx): chaîne + strip creds cross-host (R3-31) +
                # 307/308 + budget — donc urllib n'auto-suit plus en
                # contournant le strip.
                loc = r.headers.get("Location")
                if loc and _redirects < 5:
                    if time.time() > deadline:
                        return _budget_out(url, redirect_chain, attempt,
                                           status=r.status_code,
                                           headers={k.lower(): v
                                                    for k, v in r.headers.items()})
                    nxt = urllib.parse.urljoin(url, loc)
                    redirect_chain.append({"status": r.status_code,
                                           "from": url, "to": nxt})
                    m2 = "GET" if r.status_code in (301, 302, 303) else method
                    rbody = None if m2 == "GET" else body  # E-2: payload jamais sur un GET
                    rheaders = headers
                    if urllib.parse.urlsplit(nxt).netloc != host:
                        # R3-31: cross-host → les credentials restent à la maison
                        rheaders = {k: v for k, v in (headers or {}).items()
                                    if k.lower() not in _CRED_HDRS}
                    res = fetch(nxt, method=m2, headers=rheaders, body=rbody,
                                timeout=timeout, use_cache=use_cache,
                                retries=retries, _redirects=_redirects + 1,
                                redirect_chain=redirect_chain,
                                _proxy_tried=_proxy_tried, deadline=deadline,
                                _nocoalesce=True,
                                _coalesce_key=_coalesce_key)
                    # final-audit fix #6 (RZ07 on the curl_cffi lane): the
                    # sub-call returns EARLY, bypassing the epilogue publish —
                    # without threading the ORIGINAL coalesce key, the
                    # redirected final response was never cached under it
                    # (silent cache miss on every impersonated redirect).
                    res["redirect_status"] = r.status_code
                    return res
                # 3xx sans Location (ou budget redirects épuisé) → rendu tel quel
                raw = r.text
                out = {"status": r.status_code, "body": raw,
                       "headers": {k.lower(): v for k, v in r.headers.items()},
                       "size": len(raw), "url": url, "final_url": str(r.url),
                       "redirect_chain": redirect_chain, "cache_hit": False,
                       "attempts": 1, "impersonated": prof}
                break
            except Exception:
                pass  # curl_cffi absent/err — chemin urllib standard
        rq = urllib.request.Request(url, method=method, headers=h)
        try:
            r = rq_method(rq, data=data, timeout=timeout)
            # X1.1: same 500KB cap on the urllib path (the primary one).
            raw = r.read(500_000).decode(errors="replace")
            out = {"status": r.status, "body": raw,
                   "headers": {k.lower(): v for k, v in r.headers.items()},
                   "size": len(raw), "url": url, "final_url": r.geturl(),
                   "redirect_chain": redirect_chain, "cache_hit": False,
                   "attempts": attempt}
            break
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 502, 503, 504) and attempt <= retries:
                ra = ex.headers.get("Retry-After")
                d = _retry_after_delay(ra, delay)
                if time.time() + d > deadline:  # R3-25: jamais de sleep au-delà du budget
                    return _budget_out(url, redirect_chain, attempt, status=ex.code,
                                       headers={k.lower(): v for k, v in (ex.headers or {}).items()})
                time.sleep(d)
                delay *= 1.8
                continue
            loc = ex.headers.get("Location") if ex.code in (301, 302, 303, 307, 308) else None
            if loc and _redirects < 5:
                if time.time() > deadline:  # budget épuisé avant de suivre le redirect
                    return _budget_out(url, redirect_chain, attempt, status=ex.code,
                                       headers={k.lower(): v for k, v in (ex.headers or {}).items()})
                nxt = urllib.parse.urljoin(url, loc)
                redirect_chain.append({"status": ex.code, "from": url, "to": nxt})
                m2 = "GET" if ex.code in (301, 302, 303) else method
                rbody = None if m2 == "GET" else body  # E-2: jamais de payload sur un GET
                rheaders = headers
                if urllib.parse.urlsplit(nxt).netloc != host:
                    # R3-31: cross-host → les crédentials de campagne restent à la maison
                    rheaders = {k: v for k, v in (headers or {}).items()
                                if k.lower() not in _CRED_HDRS}
                res = fetch(nxt, method=m2, headers=rheaders, body=rbody,
                            timeout=timeout, use_cache=use_cache, retries=retries,
                            _redirects=_redirects + 1, redirect_chain=redirect_chain,
                            _proxy_tried=_proxy_tried, deadline=deadline,
                            _nocoalesce=True, _coalesce_key=_coalesce_key)
                res["redirect_status"] = ex.code
                return res
            raw = ""
            try:
                # X1.1: error bodies capped too — a misconfigured target
                # dumping a huge error page was the same OOM vector.
                raw = ex.read(200_000).decode(errors="replace")
            except Exception:
                pass
            out = {"status": ex.code, "body": raw,
                   "headers": {k.lower(): v for k, v in (ex.headers or {}).items()},
                   "size": len(raw), "url": url, "final_url": url,
                   "redirect_chain": redirect_chain, "cache_hit": False,
                   "attempts": attempt}
            break
        except Exception as ex:
            if attempt <= retries and isinstance(ex, (urllib.error.URLError, TimeoutError, ConnectionError)):
                time.sleep(delay * (1 + random.random()))
                delay *= 1.8
                continue
            out = {"status": -1, "body": f"{type(ex).__name__}: {str(ex)[:200]}",
                   "headers": {}, "size": 0, "url": url, "final_url": url,
                   "redirect_chain": redirect_chain, "cache_hit": False,
                   "attempts": attempt}
            break

    # ── P4/P2: bloqué → captcha hook si challenge, sinon rotate-on-block ──
    if _redirects == 0 and (out["status"] in (403, 406, 429)
                            or _looks_blocked(out.get("body"))):
        if proxy_url:
            _pool_mark(proxy_url, False)
        ch = _captcha_challenge(out.get("body") or "")
        if ch:
            key = (host, ch[1])
            if key in _CAPTCHA_DONE or _CAPTCHA_BUDGET.get(host, 3) <= 0:
                out["captcha_wall"] = {"type": ch[0], "sitekey": ch[1],
                                       "solved": False, "hint": "budget/tentative épuisée"}
            else:
                _CAPTCHA_DONE.add(key)
                tok = _captcha_solve(ch[0], ch[1], url, host=host)
                if tok:
                    cn = _CAPTCHA_COOKIE[ch[0]]
                    sep = "&" if "?" in url else "?"
                    h2 = dict(headers or {})
                    prev_cookie = h2.get("Cookie") or h2.get("cookie") or ""
                    h2["Cookie"] = (prev_cookie + f"; {cn}={tok}").lstrip("; ")
                    res = fetch(url + f"{sep}{cn}={tok}", method=method,
                                headers=h2, body=body, timeout=timeout,
                                use_cache=False, retries=retries,
                                _redirects=_redirects,
                                redirect_chain=redirect_chain,
                                _proxy_tried=_proxy_tried, deadline=deadline)
                    if res.get("status") == 200:
                        res["captcha_solved"] = True
                        res["captcha_type"] = ch[0]
                        return res
                    res["captcha_wall"] = {"type": ch[0], "sitekey": ch[1], "solved": False}
                    # Tier C — mur de captcha non résolu : l'identité est
                    # grillée sur cette cible, la prochaine requête parle
                    # avec un accent neuf (UA + langue régénérés).
                    try:
                        from core.op_identity import burn as _id_burn
                        _id_burn(host, f"captcha wall {ch[0]}")
                    except Exception:
                        pass
                    return res
                out["captcha_wall"] = {"type": ch[0], "sitekey": ch[1], "solved": False,
                                       "hint": "configure captcha.provider+api_key dans config/transport.yaml"}
                try:
                    from core.op_identity import burn as _id_burn
                    _id_burn(host, f"captcha wall {ch[0]} (unsolvable)")
                except Exception:
                    pass
            return out
        # pas de challenge → rotation proxy (P2) — exit suivant, sticky re-épinglé
        if _POOL and not proxy_url:
            alt = _pool_next(exclude=_proxy_tried, host=host)
            if alt:
                res = fetch(url, method=method, headers=headers, body=body,
                            timeout=timeout, use_cache=False, retries=retries,
                            _redirects=_redirects, redirect_chain=redirect_chain,
                            _proxy_tried=_proxy_tried, deadline=deadline,
                            _coalesce_key=_coalesce_key)
                res["proxy_used"] = alt
                res["rotated"] = True
                _pool_mark(alt, res["status"] in (200, 301, 302))
                return res
        if _POOL and proxy_url:
            alt = _pool_next(exclude=_proxy_tried, host=host)
            if alt:
                res = fetch(url, method=method, headers=headers, body=body,
                            timeout=timeout, use_cache=False, retries=retries,
                            _redirects=_redirects, redirect_chain=redirect_chain,
                            _proxy_tried=_proxy_tried | {proxy_url}, deadline=deadline,
                            _coalesce_key=_coalesce_key)
                res["proxy_used"] = alt
                res["rotated"] = True
                _pool_mark(alt, res["status"] in (200, 301, 302))
                return res
    elif proxy_url:
        _pool_mark(proxy_url, out["status"] in (200, 301, 302))

    if cache_key and out["status"] == 200:
        # X1.3 (audit-3) logic, factored into _cache_store_locked (Phase
        # 0.4: the coalescer flyer uses the same helper — one compaction
        # rule, one cap, one eviction, two entry points).
        _cache_store_locked(cache_key, out)
    _mark_host_result(host, out["status"])
    _tb_observe(host, out)   # Phase 0.3: transport breaker bookkeeping
    if _coalesce_key and out["status"] == 200:
        # Phase 0.4: the flyer reached the real epilogue — publish to the
        # coalescer's cache key so joiners/later callers hit the cache.
        _cache_store_locked(_coalesce_key, out)
    if 0 < out["size"] < 200_000:
        try:
            from core.blackboard import observe
            observe("transport", json.dumps({"url": url, "body": out["body"][:4000],
                                             "status": out["status"]}))
        except Exception:
            pass
    return out
