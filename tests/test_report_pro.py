# -*- coding: utf-8 -*-
"""report_pro battery: client-ready HTML deliverable.

The markdown stays the system of record; this checks the sibling renders
deterministically: CVSS per finding, remediation blocks, donut SVG,
print CSS, standalone (zero external refs), and the FR knob."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile, shutil
from core.report import write_report, _extract_findings
from core import report_pro
from core.lang import set_language

TRANSCRIPT = [
    ("tool", "spa_crawl: admin panel /admin mapped, session flow noted"),
    ("tool", "secret_scan: AKIAIOSFODNN7EXAMPLE found in exposed config"),
    ("tool", "data_extract: postgres://appuser:hunter2@db.internal:5432/prod 200"),
    ("agent", "closing — evidence archived"),
]


def _gen():
    folder = tempfile.mkdtemp()
    try:
        md = write_report("engagement: probe target web", TRANSCRIPT, folder)
        htmls = [f for f in os.listdir(folder) if f.endswith(".html")]
        assert htmls, "pro report not generated alongside markdown"
        content = open(os.path.join(folder, htmls[0]), encoding="utf-8").read()
        return content
    finally:
        shutil.rmtree(folder, ignore_errors=True)


content = _gen()

# 1. deliverable structure
for marker in ["ENGAGEMENT REPORT", "EXECUTIVE SUMMARY", "TECHNICAL REPORT",
               "Remediation", "OWASP"]:
    assert marker in content, f"missing {marker}"

# 2. findings carry deterministic CVSS vectors + evidence
assert "CVSS:3.1/AV:" in content
assert "AKIAIOSFODNN7EXAMPLE" in content
assert content.count('class="find-card"') >= 2

# 3. donut present, standalone (no external URLs in src/href attrs)
assert "<svg" in content
import re
assert not re.search(r'(?:src|href)="https?://', content), "external ref in standalone doc"

# 4. print CSS embedded
assert "@media print" in content

# 5. FR knob flips the deliverable language
set_language("fr")
fr_content = _gen()
set_language("en")
for marker in ["SYNTHÈSE EXÉCUTIVE", "RAPPORT TECHNIQUE", "Remédiation"]:
    assert marker in fr_content, f"FR knob missing {marker}"
assert "SYNTHÈSE EXÉCUTIVE" not in content  # EN was truly EN

# 6. no findings -> honest empty state, no crash
folder = tempfile.mkdtemp()
try:
    md = write_report("quiet mission", [("agent", "nothing found")], folder)
    htmls = [f for f in os.listdir(folder) if f.endswith(".html")]
    c2 = open(os.path.join(folder, htmls[0]), encoding="utf-8").read()
    assert "No exploitable finding" in c2
finally:
    shutil.rmtree(folder, ignore_errors=True)

# 7. direct renderer call with enriched findings (rule_kind -> CVSS class)
findings, _sup = _extract_findings([("tool",
    "secret_scan: postgres://u:p@host:5432/db leaked in env dump")])
assert findings and findings[0]["rule_kind"] == "secret"
enriched = report_pro.write_pro_report("direct call", findings,
                                       [("secret_scan", 3)],
                                       tempfile.mkdtemp())
assert os.path.exists(enriched)

print("[PASS] report_pro: CVSS cards, donut, print CSS, standalone, "
      "FR knob, empty state, direct call")
