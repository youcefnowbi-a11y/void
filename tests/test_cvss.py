# -*- coding: utf-8 -*-
"""CVSS 3.1 battery: deterministic anchors against the FIRST.org spec.

Anchor scores verified by hand from the CVSS 3.1 section 7.1 formula +
the reference Roundup implementation (ceil to one decimal). Same input
-> same score, every machine, every run — that's the whole point of
a deterministic scorer in the sealed deliverable."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cvss import base_score, vector, severity_label, classify, VULN_CLASSES

ANCHORS = [
    (dict(av='N', ac='L', pr='N', ui='N', s='U', c='H', i='H', a='H'), 9.8),   # RCE-class
    (dict(av='N', ac='L', pr='N', ui='N', s='U', c='H', i='H', a='L'), 9.4),   # integrity-heavy
    (dict(av='N', ac='L', pr='N', ui='R', s='C', c='L', i='L', a='N'), 6.1),   # classic XSS (S:C)
    (dict(av='N', ac='L', pr='L', ui='N', s='U', c='H', i='H', a='H'), 8.8),   # auth'd RCE
    (dict(av='N', ac='L', pr='N', ui='N', s='U', c='N', i='N', a='H'), 7.5),   # avail-only
    (dict(av='N', ac='L', pr='N', ui='N', s='U', c='N', i='N', a='N'), 0.0),   # no impact
    (dict(av='N', ac='L', pr='N', ui='N', s='C', c='H', i='H', a='H'), 10.0), # Log4Shell-class
    (dict(av='L', ac='H', pr='H', ui='N', s='U', c='H', i='H', a='H'), 6.4),   # local priv (hand-verified)
    (dict(av='P', ac='H', pr='H', ui='R', s='U', c='L', i='N', a='N'), 1.6),   # physical floor
]

for args, expected in ANCHORS:
    got = base_score(**args)
    assert got == expected, f"{vector(**args)} -> {got}, want {expected}"

# determinism: same vector, 100 runs, byte-stable
for args, _ in ANCHORS:
    vals = {base_score(**args) for _ in range(100)}
    assert len(vals) == 1, f"non-deterministic: {vals}"

# severity bands
assert severity_label(0.0) == "NONE"
assert severity_label(3.9) == "LOW"
assert severity_label(4.0) == "MEDIUM"
assert severity_label(7.0) == "HIGH"
assert severity_label(9.0) == "CRITICAL"

# knowledge map: every class resolves + has remediation + OWASP ref
for cls in list(VULN_CLASSES) + ["totally-unknown-class"]:
    r = classify(cls)
    assert r["score"] >= 0.0
    assert r["remediation"] and len(r["remediation"]) > 40
    assert "A0" in r["owasp"] or ":" in r["owasp"]
    assert r["vector"].startswith("CVSS:3.1/AV:")

# agent override wins, base class stays intact
r = classify("sqli", ac="H")
assert r["metrics"]["ac"] == "H" and r["score"] < 9.8
assert classify("sqli")["score"] == 9.8  # map not mutated

print("[PASS] cvss: 9 anchors spec-true, 100-run determinism, 13 classes mapped")
