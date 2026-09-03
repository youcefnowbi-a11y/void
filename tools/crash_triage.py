"""TOOL: crash_triage - rank fuzz findings and map them to exploit modules.

Closes the zero-day loop: fuzz_attack_surface -> crash_triage -> the right
exploitation tool (sqli_union_dump, ssti_detect_rce, cmd_exec_probe, ...).
Dedupes by (error_class, path, payload-family) signature, scores
exploitability, and emits a ready-to-fire action plan.
"""
import json, math, os, re
from collections import OrderedDict

from tools import register
from tools._exploit_lib import verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINDINGS_PATH = os.path.join(ROOT, "reports", "fuzz_findings.json")


def _mission_scoped_default():
    """W8 (mission-77 autopsy): the OLD global default read whatever fuzz
    findings a PAST mission left on disk — cross-mission contamination
    dressed as fresh triage (duskyr.com findings surfaced inside a
    venice.ai run and got sealed as a CONFIRMED finding). The default now
    resolves INSIDE the active mission workspace first; the global file
    stays the operator-mode fallback (no mission running)."""
    try:
        from core import mission_workspace as _mw
        ws = _mw.get_active()
        d = getattr(ws, "dir", None) if ws is not None else None
        if d:
            return os.path.join(str(d), "fuzz_findings.json")
    except Exception:
        pass
    return FINDINGS_PATH


def _wilson_lower(k, n, z=1.96):
    """Wilson score LOWER bound at confidence z (95% default). The right way
    to rank "hit rate": 3/3 looks great at n=3 but its lower bound is 0.44 —
    small samples can no longer outrank statistically solid ones."""
    if n == 0:
        return 0.0
    ph = k / n
    den = 1 + z * z / n
    center = ph + z * z / (2 * n)
    margin = z * math.sqrt((ph * (1 - ph) + z * z / (4 * n)) / n)
    return max(0.0, (center - margin) / den)

# signal -> (exploitability weight, next tool, args hint builder)
MAP = [
    ("error:sql_mysql",        0.95, "sqli_union_dump", lambda f: {"url_template": None}),
    ("error:sql_pg",           0.95, "sqli_union_dump", lambda f: {"url_template": None}),
    ("error:sql_mssql",        0.95, "sqli_union_dump", lambda f: {"url_template": None}),
    ("error:sql_sqlite",       0.95, "sqli_union_dump", lambda f: {"url_template": None}),
    ("error:template_jinja",   0.97, "ssti_detect_rce", lambda f: {"url_template": None}),
    ("error:template_twig",    0.97, "ssti_detect_rce", lambda f: {"url_template": None}),
    ("error:template_smarty",  0.9,  "ssti_detect_rce", lambda f: {"url_template": None}),
    ("error:template_freemarker", 0.97, "ssti_detect_rce", lambda f: {"url_template": None}),
    ("error:python_traceback", 0.8,  "fuzz_attack_surface", lambda f: {"url": None, "target_param": f.get("param")}),
    ("error:java_stack",       0.75, "fuzz_attack_surface", lambda f: {"url": None, "target_param": f.get("param")}),
    ("error:serialization",    0.98, None, lambda f: {"note": "deserialization — manual PoC construction"}),
    ("error:path_leak",        0.7,  "lfi_file_read", lambda f: {"url_template": None}),
    ("reflected_unsanitized",  0.6,  None, lambda f: {"note": "reflected input — XSS/session surface"}),
    ("timing(",                0.75, "sqli_blind_extract", lambda f: {"url_template": None}),
    ("status_5xx",             0.5,  "fuzz_attack_surface", lambda f: {"url": None, "target_param": f.get("param")}),
]

FAMILY = [
    ("sqli",    r"(?:UNION|SELECT|OR|SLEEP|WAITFOR|')"),
    ("ssti",    r"\{\{|\$\{|<%="),
    ("path",    r"\.\./|win\.ini|php://|%2e%2e"),
    ("cmdi",    r"(?:;|&&|\|\||`)id"),
    ("proto",   r"\[\]|\{\}|\$gt|__proto__|null|true|-1"),
    ("overflow", r"A{10,}|%n%n|%s%s"),
]

def _family_of(payload):
    for name, rx in FAMILY:
        if re.search(rx, payload or ""):
            return name
    return "other"

@register(name="crash_triage_next",
          desc="ZERO-DAY: rank fuzz findings by exploitability, dedupe by signature, and emit the exact next-tool action plan. Run after fuzz_attack_surface.",
          params={"type": "object", "properties": {
              "path": {"type": "string", "description": "findings file; default reports/fuzz_findings.json"},
              "top": {"type": "integer", "default": 10}},
              "required": []},
          danger="safe")
def crash_triage_next(path=None, top=10):
    p = path or _mission_scoped_default()
    if not os.path.exists(p):
        return verdict("crash_triage_next", False,
                       "no findings file — run fuzz_attack_surface first")
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)

    # dedupe by signature
    sig_map = OrderedDict()
    for f in raw:
        sig = (f.get("url_path", "?"), f.get("param", "?"),
               _family_of(f.get("payload", "")))
        cur = sig_map.get(sig)
        if cur is None or f.get("severity", 0) > cur.get("severity", 0):
            f = dict(f)
            f["occurrences"] = (cur.get("occurrences", 1) + 1) if cur else 1
            sig_map[sig] = f

    ranked = []
    for sig, f in sig_map.items():
        weight, next_tool, build = 0.3, None, None
        for marker_, w, tool, builder in MAP:
            if any(s.startswith(marker_.split("(")[0]) or marker_ in s
                   for s in f.get("signals", [])):
                weight, next_tool, build = w, tool, builder
                break
        score = round(min(0.99, f.get("severity", 0.3) * 0.6 + weight * 0.4), 2)
        # Wilson-discounted ranking: raw severity × statistical confidence that
        # the finding is not a small-sample fluke.
        n_total = max(len(raw), 1)
        conf = _wilson_lower(f.get("occurrences", 1), n_total)
        entry = {"signature": "|".join(sig), "score": score,
                 "confidence": round(0.5 + 0.5 * conf, 2),
                 "payload": f.get("payload", "")[:120],
                 "signals": f.get("signals", []),
                 "occurrences": f.get("occurrences", 1)}
        if next_tool:
            args = build(f)
            entry["next_tool"] = next_tool
            if next_tool == "sqli_union_dump":
                entry["next_args"] = {"url_template": "<rebuild with {INJ} on the vulnerable param>"}
            elif next_tool == "ssti_detect_rce":
                entry["next_args"] = {"url_template": "<rebuild with {INJ} on the vulnerable param>"}
            elif next_tool == "lfi_file_read":
                entry["next_args"] = {"url_template": "<rebuild with {INJ}>"}
            elif next_tool == "sqli_blind_extract":
                entry["next_args"] = {"url_template": "<rebuild with {INJ}>",
                                      "subquery": "SELECT version()"}
            else:
                entry["next_args"] = args
        ranked.append(entry)

    ranked.sort(key=lambda r: -(r["score"] * r.get("confidence", 1.0)))
    top_hits = ranked[:top]
    # fuzz_seeds: the surviving payloads, keyed by param — feed straight back
    # into fuzz_attack_surface(seeds=...) for the next, smarter round.
    fuzz_seeds = {}
    for r in top_hits:
        try:
            pk = r["signature"].split("|")[1]
        except Exception:
            continue
        if pk not in ("?", "") and r.get("payload"):
            fuzz_seeds[pk] = r["payload"]
    return verdict("crash_triage_next", bool(top_hits),
                   (f"{len(top_hits)} triaged finding(s) — top score {top_hits[0]['score']} "
                    f"-> {top_hits[0].get('next_tool', 'manual review')}" if top_hits else
                    "findings file empty or nothing survived dedupe"),
                   evidence=[f"{r['signature']} ({r['score']}) -> {r.get('next_tool', 'manual')}"
                             for r in top_hits],
                   ranked=top_hits, fuzz_seeds=fuzz_seeds)
