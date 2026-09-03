"""VOIDFORGE :: Shared constants and helpers for all tools."""
import os, time, urllib.request, urllib.error, urllib.parse

VOIDFORGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(VOIDFORGE_ROOT, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36"
UA = {"User-Agent": USER_AGENT}


def _pacer_for(url):
    """Per-host adaptive pacer (token bucket + EWMA + AIMD). Silent no-op
    if mathcore is unavailable — tools never break because of it."""
    try:
        from core.mathcore import get_pacer
        return get_pacer(urllib.parse.urlsplit(url).netloc)
    except Exception:
        return None


def _get(url, headers=None, timeout=20, token=None):
    """HTTP GET wrapped in adaptive pacing: waits for a bucket token, then
    observes the outcome so the pacer converges to the max rate the target
    tolerates (backs off on 429/403/rtt-spikes, recovers on clean streaks)."""
    p = _pacer_for(url)
    if p:
        p.wait()
    t0 = time.perf_counter()
    status, body = _get_raw(url, headers=headers, timeout=timeout, token=token)
    if p:
        p.observe(status, time.perf_counter() - t0)
    return status, body


def _get_raw(url, headers=None, timeout=20, token=None):
    """Shared HTTP GET helper with optional auth and proxy support."""
    h = dict(UA)
    if headers:
        h.update(headers)
    if token:
        h["Authorization"] = f"Bearer {token}"
    rq = urllib.request.Request(url, headers=h)

    # Proxy support: if core.proxy is available and configured, use it
    try:
        from core.proxy import get_opener
        opener = get_opener()
        if opener:
            r = opener.open(rq, timeout=timeout)
            return r.status, r.read().decode(errors="replace")[:120000]
    except (ImportError, Exception):
        pass

    try:
        r = urllib.request.urlopen(rq, timeout=timeout)
        return r.status, r.read().decode(errors="replace")[:120000]
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode(errors="replace")[:8000]
    except Exception as ex:
        return -1, f"{type(ex).__name__}: {str(ex)[:80]}"


def _req(base, method, path, token=None, body=None, timeout=25):
    """HTTP request helper wrapped in adaptive pacing (same control loop
    as _get: token bucket wait + outcome observation per host)."""
    p = _pacer_for(base)
    if p:
        p.wait()
    t0 = time.perf_counter()
    status, out = _req_raw(base, method, path, token=token, body=body, timeout=timeout)
    if p:
        p.observe(status, time.perf_counter() - t0)
    return status, out


def _req_raw(base, method, path, token=None, body=None, timeout=25):
    """Shared HTTP request helper for API calls."""
    import json
    rq = urllib.request.Request(base.rstrip("/") + path, method=method)
    rq.add_header("User-Agent", USER_AGENT)
    if token:
        rq.add_header("Authorization", f"Bearer {token}")
        rq.add_header("apikey", token)
    if body is not None:
        rq.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode() if body is not None else None
    try:
        r = urllib.request.urlopen(rq, data=data, timeout=timeout)
        # V2 (audit 1.2): 800 chars amputated every API response at the
        # first page — JSON decode crashed mid-string. 120k now.
        return r.status, r.read().decode(errors="replace")[:120000]
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode(errors="replace")[:8000]
    except Exception as ex:
        return -1, f"{type(ex).__name__}: {str(ex)[:80]}"
