# -*- coding: utf-8 -*-
"""REDACTED :: report_pro — client-ready HTML engagement deliverable.

LAWS:
  - Sibling of the sealed markdown: write_report() stays the system of
    record; this renders the SAME findings for humans (bosses,
    clients, auditors). Never re-parses the .md — it consumes the
    same structures (findings list, ledger, engagement) directly.
  - STANDALONE: one .html file, CSS inline, zero network, zero JS
    deps. Opens on any machine, prints to PDF from the browser.
  - Deterministic: no LLM anywhere in this path. CVSS from core.cvss,
    remediation from the knowledge map, severity from the ledger.
  - Print CSS embedded — one click "Print / Save as PDF" and the
    document paginates cleanly (page breaks before findings).
"""
import os
import html as _html
from core.lang import L as _L
from core.cvss import classify

_SEV_COLORS = {
    "CRITICAL": "#e5484d",
    "HIGH": "#f76b15",
    "MEDIUM": "#ffb224",
    "LOW": "#46a758",
}

# map SEVERITY_RULES rule_kinds -> cvss vuln class
_KIND_TO_CLASS = {
    "secret": "secret_leak",
    "cloudkey": "secret_leak",
    "cred": "secret_leak",
    "jwt": "auth_bypass",
    "infra": "info_disclosure",
}

_CSS = """
  :root { --ink:#111418; --paper:#ffffff; --line:#e3e6ea; --dim:#5b6470; }
  * { box-sizing: border-box; margin:0; padding:0; }
  body { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
         color: var(--ink); background:var(--paper); line-height:1.55;
         font-size: 10.5pt; padding: 42px 48px; max-width: 210mm;
         margin: 0 auto; }
  .redacted-bar { display:inline-block; background:#111418; color:#111418;
                  padding:2px 14px; letter-spacing:2px; font-weight:700; }
  header.doc { border-bottom: 3px solid #111418; padding-bottom: 18px;
               margin-bottom: 26px; display:flex;
               justify-content:space-between; align-items:flex-end; }
  header.doc .brand { font-size: 15pt; font-weight: 800; letter-spacing: 3px; }
  header.doc .meta { text-align:right; color:var(--dim); font-size: 9pt; }
  h1 { font-size: 16pt; margin-bottom: 14px; letter-spacing:.5px; }
  h2 { font-size: 12pt; margin: 22px 0 10px; padding-bottom:6px;
       border-bottom: 1px solid var(--line); letter-spacing:1px; }
  h3 { font-size: 10.5pt; margin: 14px 0 6px; }
  .cover-strip { background:#111418; color:#fff; padding:20px 24px;
                 margin-bottom: 22px; }
  .cover-strip .t { font-size: 20pt; font-weight: 800; letter-spacing: 2px; }
  .cover-strip .s { color:#9aa4b2; font-size: 9.5pt; margin-top: 4px; }
  .exec-grid { display:flex; gap: 26px; align-items:flex-start; }
  .exec-stats { min-width: 240px; }
  .stat { border:1px solid var(--line); padding: 10px 14px; margin-bottom:8px; }
  .stat .n { font-size: 22pt; font-weight: 800; }
  .stat .lbl { color: var(--dim); font-size: 8.5pt; letter-spacing: 1.5px;
               text-transform: uppercase; }
  .donut-wrap { text-align:center; }
  .stat-line { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
  .pill { padding:3px 10px; border-radius: 3px; font-weight:700;
          font-size: 8.5pt; color:#fff; letter-spacing:1px; }
  table { width:100%; border-collapse: collapse; margin: 8px 0 14px;
          font-size: 9.5pt; }
  th { text-align:left; background:#f2f4f6; border:1px solid var(--line);
       padding: 6px 8px; font-size: 8.5pt; letter-spacing: 1px;
       text-transform: uppercase; }
  td { border:1px solid var(--line); padding: 6px 8px; vertical-align: top; }
  .sev-badge { display:inline-block; padding: 2px 8px; border-radius: 3px;
               color:#fff; font-weight:700; font-size: 8pt; letter-spacing:1px; }
  .cvss-score { font-weight: 800; font-size: 11pt; }
  code, .mono { font-family: 'Cascadia Code', Consolas, monospace;
                font-size: 8.5pt; background:#f4f5f7; padding: 1px 4px; }
  .rem { background:#f7f9f7; border-left: 3px solid #46a758;
         padding: 8px 12px; margin-top: 6px; font-size: 9.5pt; }
  .unver { border:1px dashed #f76b15; color:#a04a0f; padding: 6px 10px;
           font-size: 9pt; margin-top: 8px; }
  footer { margin-top: 30px; border-top: 2px solid #111418; padding-top:10px;
           color: var(--dim); font-size: 8.5pt; display:flex;
           justify-content: space-between; }
  @media print {
    body { padding: 0; font-size: 10pt; }
    .find-card { break-inside: avoid; page-break-inside: avoid; }
    h2 { break-before: auto; }
    .page-break { break-before: page; }
  }
"""


def _esc(s):
    return _html.escape(str(s or ""), quote=True)


def _donut_svg(sev_counts):
    """Severity donut as pure SVG (no JS, prints perfectly)."""
    total = sum(sev_counts.values())
    if total == 0:
        return ""
    cx = cy = r = 52
    stroke = 16
    circ = 2 * 3.141592653589793 * r
    segs, offset = [], 0.0
    order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    for sev in order:
        val = sev_counts.get(sev, 0)
        if not val:
            continue
        frac = val / total
        dash = frac * circ
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{_SEV_COLORS[sev]}" stroke-width="{stroke}" '
            f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += dash
    return (
        f'<svg width="140" height="140" viewBox="0 0 140 140" role="img">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#e3e6ea" '
        f'stroke-width="{stroke}"/>'
        f'{"".join(segs)}'
        f'<text x="70" y="66" text-anchor="middle" font-size="26" '
        f'font-weight="800" fill="#111418">{total}</text>'
        f'<text x="70" y="84" text-anchor="middle" font-size="8.5" '
        f'letter-spacing="1.5" fill="#5b6470">{_L("pro_findings").upper()}</text>'
        f'</svg>'
    )


def _finding_card(idx, finding):
    """One finding: severity badge, evidence, CVSS block, remediation."""
    sev = finding.get("severity", "MEDIUM")
    kind = finding.get("rule_kind", "")
    cls = _KIND_TO_CLASS.get(kind, "default")
    cv = finding.get("cvss") or classify(cls)
    col = _SEV_COLORS.get(cv.get("severity", sev), _SEV_COLORS["MEDIUM"])
    ev = _esc((finding.get("evidence") or "")[:400])
    ctx = _esc(finding.get("context") or "")
    unv = ""
    if finding.get("unverified"):
        unv = (f'<div class="unver">⚠ {_L("pro_unverified_tag")} — '
               f'{_esc(finding.get("unverified") or "")}</div>')
    return f"""
<div class="find-card">
  <h3><span class="sev-badge" style="background:{col}">{_L('pro_' + sev.lower())}</span>
      &nbsp;{_esc(finding.get("title") or f'{_L("pro_findings").rstrip("s")} #{idx}')}</h3>
  <table>
    <tr><th style="width:130px">{_L("pro_severity")}</th>
        <td><span class="cvss-score" style="color:{col}">{cv["score"]:.1f}</span>
            &nbsp;·&nbsp; CVSS {_esc(cv["severity"])} &nbsp;·&nbsp;
            <span class="mono">{_esc(cv["vector"])}</span></td></tr>
    <tr><th>Evidence</th><td><span class="mono">{ev}</span></td></tr>
    <tr><th>Context</th><td>{ctx}</td></tr>
    <tr><th>{_L("pro_reference")}</th><td>OWASP {_esc(cv["owasp"])}</td></tr>
  </table>
  <div class="rem"><b>{_L("pro_remediation")}.</b> {_esc(cv["remediation"])}</div>
  {unv}
</div>"""


def write_pro_report(mission, findings, ledger, folder, engagement=None,
                     unverified=None, stats=None):
    """Render the client-ready HTML deliverable. Returns the path.

    findings: list from report._extract_findings (severity, evidence,
    context, rule_kind); each gets CVSS + remediation attached here.
    ledger: [(tool_name, count)] from report._tool_ledger.
    unverified: list of claim strings flagged by verify_report_claims.
    """
    engagement = engagement or {}
    ts = engagement.get("generated") or _now()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"report_pro_{_stamp()}.html")

    # ── enrich findings with CVSS (deterministic) ───────────────
    enriched = []
    for f in findings:
        item = dict(f)
        cls = _KIND_TO_CLASS.get(item.get("rule_kind", ""), "default")
        item["cvss"] = classify(cls)
        enriched.append(item)

    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in enriched:
        s = f["cvss"]["severity"]
        sev_counts[s] = sev_counts.get(s, 0) + 1
    sev_counts = {k: v for k, v in sev_counts.items() if v or k == "LOW"}

    n_find = len(enriched)
    n_tools = sum(n for _, n in ledger)
    donut = _donut_svg(sev_counts)

    scope_in = ", ".join((engagement.get("scope") or {}).get("in_scope", [])
                         or ["—"])
    client = _esc(engagement.get("client") or "—")

    cards = "\n".join(_finding_card(i + 1, f)
                      for i, f in enumerate(enriched)) or \
        f'<p style="color:var(--dim)">{_L("pro_findings_none")}</p>'

    unv_block = ""
    if unverified:
        lis = "".join(f"<li><span class='mono'>{_esc(u)}</span></li>"
                      for u in unverified[:20])
        unv_block = (f'<h2>{_L("pro_unverified_tag")} — '
                     f'{len(unverified)}</h2><ul>{lis}</ul>')

    ledger_rows = "".join(
        f"<tr><td><span class='mono'>{_esc(name)}</span></td>"
        f"<td style='text-align:right'>{n}</td></tr>"
        for name, n in ledger[:30])

    pills = "".join(
        f'<span class="pill" style="background:{_SEV_COLORS[sev]}">'
        f'{sev} × {n}</span>'
        for sev, n in sev_counts.items() if n)

    doc = f"""<!DOCTYPE html>
<html lang="{_lang_attr()}">
<head>
<meta charset="utf-8">
<title>REDACTED — {_esc(mission[:80])}</title>
<style>{_CSS}</style>
</head>
<body>
<header class="doc">
  <div>
    <div class="brand"><span class="redacted-bar">████████</span> REDACTED</div>
    <div style="color:var(--dim); font-size:9pt; margin-top:4px">
      autonomous offensive engagement platform</div>
  </div>
  <div class="meta">
    {_L("pro_generated")}: {ts}<br>
    {_L("pro_scope")}: {_esc(scope_in[:120])}
  </div>
</header>

<div class="cover-strip">
  <div class="t">ENGAGEMENT REPORT</div>
  <div class="s">{_esc(mission[:160])}</div>
</div>

<h2>{_L("pro_exec_summary")}</h2>
<div class="exec-grid">
  <div class="exec-stats">
    <div class="stat"><div class="n">{n_find}</div>
      <div class="lbl">{_L("pro_findings")}</div></div>
    <div class="stat"><div class="n">{n_tools}</div>
      <div class="lbl">{_L("pro_arsenal")}</div></div>
    <div class="stat-line">{pills}</div>
  </div>
  <div class="donut-wrap">{donut}</div>
  <div style="flex:1">
    <p>{_L("pro_exec_intros")}</p>
    <table>
      <tr><th style="width:140px">Client</th><td>{client}</td></tr>
      <tr><th>Authorization ref</th>
          <td>{_esc(engagement.get("authorization_ref") or "—")}</td></tr>
      <tr><th>Intensity</th>
          <td>{_esc((engagement.get("rules_of_engagement") or {})
                    .get("intensity") or "—")}</td></tr>
      <tr><th>Window</th>
          <td>{_esc((engagement.get("rules_of_engagement") or {})
                    .get("timing_window") or "—")}</td></tr>
    </table>
  </div>
</div>

<div class="page-break"></div>
<h2>{_L("pro_tech_report")} — {_L("pro_findings")}</h2>
{cards}

{unv_block}

<div class="page-break"></div>
<h2>{_L("pro_arsenal")}</h2>
<table>
  <tr><th>Module</th><th style="text-align:right">Executions</th></tr>
  {ledger_rows}
</table>

<footer>
  <span>{_L("pro_printed_by")}</span>
  <span>████ REDACTED ████████████</span>
</footer>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


def _now():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _stamp():
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _lang_attr():
    from core.lang import get_language
    return "fr" if get_language() == "fr" else "en"
