"""TOOL: nuclei_runner - template-driven vulnerability scanning."""
import json, subprocess, os
from tools import register
from sandbox.runner import run

NUCLEI_CANDIDATES = [
    r"C:\Users\youcef cheriet\bin\nuclei\nuclei.exe",
    "nuclei",
]

def _find_nuclei():
    for c in NUCLEI_CANDIDATES:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=30,
                               encoding="utf-8", errors="replace")
            if r.returncode == 0 or "Nuclei" in (r.stderr or "") + (r.stdout or ""):
                return c
        except Exception:
            continue
    return None

@register(name="nuclei_scan",
          desc="Run nuclei template-driven vuln scan against a target. severity filter, specific tags, JSON lines out.",
          params={"type":"object","properties":{
              "target":{"type":"string"},
              "severity":{"type":"string","description":"critical,high,medium,low,info combos"},
              "tags":{"type":"string","description":"e.g. cve,rce,sqli"},
              "templates":{"type":"boolean","description":"update templates first"},
              "timeout_min":{"type":"integer"}},
              "required":["target"]})
def nuclei_scan(target, severity=None, tags=None, templates=False, timeout_min=15):
    nuc = _find_nuclei()
    if not nuc:
        return json.dumps({"error": "nuclei binary not found",
                           "fix": "install via scoop install nuclei or download release"})
    cmd = [nuc, "-target", target, "-j", "-silent", "-nc"]
    if severity: cmd += ["-severity", severity]
    if tags: cmd += ["-tags", tags]
    if templates: cmd += ["-update-templates"]
    code, tail = run(cmd, timeout_minutes=int(timeout_min))
    findings = []
    for line in tail.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                j = json.loads(line)
                findings.append({"id": j.get("template-id"), "name": j.get("info", {}).get("name"),
                                 "severity": (j.get("info") or {}).get("severity"),
                                 "host": j.get("host"), "matched": str(j.get("match", ""))[:100],
                                 "extracted": j.get("extracted", [])})
            except Exception: pass
    return json.dumps({"target": target, "findings_count": len(findings),
                       "findings": findings[:40], "raw_tail": tail[-400:] if not findings else ""},
                      ensure_ascii=False, indent=1)
