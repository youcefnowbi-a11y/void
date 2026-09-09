# -*- coding: utf-8 -*-
"""REDACTED :: CVSS 3.1 — deterministic base-score calculator.

LAWS:
  - NO LLM here. CVSS must be reproducible byte-for-byte: same finding,
    same vector, same score. The LLM classifies the vuln; this module
    turns the class into metrics deterministically.
  - Base metrics only (AV/AC/PR/UI/S/C/I/A) — temporal/environmental
    are retest or client-side decisions, out of scope for the sealed
    deliverable.
  - Vuln-class -> metric mapping is a KNOWLEDGE table (auditable,
    overridable per finding if the agent supplies explicit metrics).
"""
import math

# ── CVSS 3.1 constants (first.org specification) ────────────────────
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}
_UI = {"N": 0.85, "R": 0.62}
_C = {"H": 0.56, "L": 0.22, "N": 0.00}
_I = {"H": 0.56, "L": 0.22, "N": 0.00}
_A = {"H": 0.56, "L": 0.22, "N": 0.00}

_ROUNDUP_SIG = 100000.0


def _roundup(x):
    """CVSS 3.1 'Roundup' per the FIRST.org reference implementation:
    the smallest number >= x with ONE decimal place. (A 5-decimal ceil
    + round-half-even was wrong — it turned the classic changed-scope
    XSS vector 6.0067 into 6.0 instead of 6.1. Caught by the anchor
    battery, fixed against the spec's reference code.)"""
    int_input = int(math.floor(x * 100000 + 0.5))
    if int_input % 10000 == 0:
        return int_input / 100000.0
    return (math.floor(int_input / 10000.0) + 1) / 10.0


def base_score(av="N", ac="L", pr="N", ui="N", s="U",
               c="H", i="H", a="H"):
    """Compute the CVSS 3.1 base score (0.0-10.0)."""
    av = str(av).upper()[:1]
    ac = str(ac).upper()[:1]
    pr = str(pr).upper()[:1]
    ui = str(ui).upper()[:1]
    s = str(s).upper()[:1]
    c = str(c).upper()[:1]
    i = str(i).upper()[:1]
    a = str(a).upper()[:1]

    iss = 1.0 - (1.0 - _C[c]) * (1.0 - _I[i]) * (1.0 - _A[a])
    if s == "C":  # changed scope
        impact = 7.52 * (iss - 0.029) - 3.25 * pow(iss - 0.02, 15)
    else:        # unchanged
        impact = 6.42 * iss
    if impact <= 0:
        return 0.0
    pr_map = _PR_CHANGED if s == "C" else _PR_UNCHANGED
    exploitability = 8.22 * _AV[av] * _AC[ac] * pr_map[pr] * _UI[ui]
    if s == "C":
        score = _roundup(min(1.08 * (impact + exploitability), 10.0))
    else:
        score = _roundup(min(impact + exploitability, 10.0))
    return score


def vector(av="N", ac="L", pr="N", ui="N", s="U", c="H", i="H", a="H"):
    """Standard CVSS vector string for the sealed report."""
    return (f"CVSS:3.1/AV:{av.upper()}/AC:{ac.upper()}/PR:{pr.upper()}"
            f"/UI:{ui.upper()}/S:{s.upper()}/C:{c.upper()}"
            f"/I:{i.upper()}/A:{a.upper()}")


def severity_label(score):
    if score <= 0.0:
        return "NONE"
    if score < 4.0:
        return "LOW"
    if score < 7.0:
        return "MEDIUM"
    if score < 9.0:
        return "HIGH"
    return "CRITICAL"


# ── vuln-class knowledge map ────────────────────────────────────────
# Each class -> (metrics tuple, remediation text, OWASP 2021 ref).
# Auditable table: the agent may override per-finding with explicit
# metrics when the wire evidence justifies it (e.g. AC:H for a race).
VULN_CLASSES = {
    "sqli": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="H", i="H", a="H"),
        "remediation": (
            "Use parameterized queries / prepared statements everywhere — "
            "never concatenate user input into SQL. Reject and log "
            "malformed input server-side. For legacy code, an allowlist "
            "input validator is an interim control, not a fix."),
        "owasp": "A03:2021-Injection",
    },
    "rce": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="H", i="H", a="H"),
        "remediation": (
            "Eliminate OS command invocation with user-controlled data. "
            "Where execution is required, use allowlist dispatch tables, "
            "shell-free APIs, and never pass raw strings. Run the service "
            "as an unprivileged user in a restricted container."),
        "owasp": "A03:2021-Injection",
    },
    "ssti": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="H", i="H", a="H"),
        "remediation": (
            "Never pass user input to the template engine's compile path. "
            "Use logic-less templates for user-rendered content; keep "
            "server-side logic out of template variables. Sandboxed "
            "renderers are the last line, not the fix."),
        "owasp": "A03:2021-Injection",
    },
    "auth_bypass": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="H", i="H", a="L"),
        "remediation": (
            "Enforce authorization server-side on every request — never "
            "trust client-supplied identity or role claims. Centralize "
            "the check in middleware; fail closed on missing context."),
        "owasp": "A01:2021-Broken Access Control",
    },
    "idor": {
        "metrics": dict(av="N", ac="L", pr="L", ui="N", s="U",
                        c="H", i="L", a="N"),
        "remediation": (
            "Bind every object access to the authenticated session: "
            "object-level checks (not just route-level), indirect "
            "references (UUIDs, not sequential IDs), and cross-tenant "
            "tests in CI."),
        "owasp": "A01:2021-Broken Access Control",
    },
    "secret_leak": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="H", i="H", a="H"),
        "remediation": (
            "Rotate the exposed credential immediately (assume "
            "compromised since exposure). Move secrets to a vault or "
            "server-side env — never in client bundles, public repos, or "
            "frontend code. Add secret scanning to CI."),
        "owasp": "A07:2021-Identification and Authentication Failures",
    },
    "ssrf": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="C",
                        c="H", i="L", a="N"),
        "remediation": (
            "Allowlist outbound destinations at the network layer; deny "
            "the server access to its own metadata endpoints and internal "
            "ranges. Validate scheme+host server-side before any fetch; "
            "never follow redirects to private space."),
        "owasp": "A10:2021-SSRF",
    },
    "race": {
        "metrics": dict(av="N", ac="H", pr="N", ui="N", s="U",
                        c="L", i="H", a="L"),
        "remediation": (
            "Make grant/idempotency paths atomic: row-level locks or "
            "single-statement conditional updates (UPDATE ... WHERE "
            "state=expected). Re-check the precondition INSIDE the "
            "transaction, not before it."),
        "owasp": "A04:2021-Insecure Design",
    },
    "xss": {
        "metrics": dict(av="N", ac="L", pr="N", ui="R", s="U",
                        c="L", i="N", a="N"),
        "remediation": (
            "Context-aware output encoding on every render path (HTML, "
            "attribute, JS, URL each differ). Adopt a CSP without "
            "unsafe-inline as a second line. Treat framework autoescaping "
            "as a floor, not the ceiling."),
        "owasp": "A03:2021-Injection",
    },
    "lfi": {
        "metrics": dict(av="N", ac="L", pr="L", ui="N", s="U",
                        c="H", i="N", a="N"),
        "remediation": (
            "Map user input to an allowlist of files — never build paths "
            "from request data. Serve user content from object storage, "
            "not the filesystem. Normalize and reject traversal "
            "sequences server-side."),
        "owasp": "A01:2021-Broken Access Control",
    },
    "smuggle": {
        "metrics": dict(av="N", ac="H", pr="N", ui="N", s="C",
                        c="H", i="L", a="N"),
        "remediation": (
            "Normalize request framing at the edge: one parser, one "
            "authority — never let front and back disagree about "
            "Content-Length vs Transfer-Encoding. Reject both present, "
            "reject ambiguous encodings, close on framing errors."),
        "owasp": "A05:2021-Security Misconfiguration",
    },
    "info_disclosure": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="L", i="N", a="N"),
        "remediation": (
            "Strip debug headers, verbose errors, and stack traces from "
            "production responses. Inventory every public endpoint; "
            "return generic errors; log the detail server-side."),
        "owasp": "A05:2021-Security Misconfiguration",
    },
    "default": {
        "metrics": dict(av="N", ac="L", pr="N", ui="N", s="U",
                        c="L", i="L", a="N"),
        "remediation": (
            "Validate the affected component's trust boundaries server-"
            "side. Rotate anything the evidence shows exposed. Add a "
            "regression test replaying the exact wire exchange that "
            "demonstrated this issue."),
        "owasp": "A04:2021-Insecure Design",
    },
}


def classify(vuln_class, **overrides):
    """Resolve a vuln class to (metrics, vector, score, severity,
    remediation, owasp). Agent-supplied overrides win when explicit."""
    entry = VULN_CLASSES.get((vuln_class or "default").lower(), VULN_CLASSES["default"])
    metrics = dict(entry["metrics"])
    metrics.update({k: v for k, v in overrides.items() if v})
    score = base_score(**metrics)
    return {
        "metrics": metrics,
        "vector": vector(**metrics),
        "score": score,
        "severity": severity_label(score),
        "remediation": entry["remediation"],
        "owasp": entry["owasp"],
    }
