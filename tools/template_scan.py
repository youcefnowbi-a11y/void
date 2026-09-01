"""TOOL: vf_template_scan - the internal nuclei.

A mini declarative scanner: YAML templates (id, info.severity, requests[].path,
matchers[]) in data/templates/. Each request fires against the target and the
matchers decide a hit: status codes, word lists, regexes. Findings persist to
reports/template_findings.json (deduped by id+url). This is the weapon that
scales our knowledge: every new technique becomes a template, not a code change.
"""
import json
import os
import re
import time
from urllib.parse import urlsplit

import yaml

from tools import register
from tools._exploit_lib import paced_send

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(ROOT, "data", "templates")
FINDINGS_PATH = os.path.join(ROOT, "reports", "template_findings.json")


def load_templates(only=None):
    """Parse every YAML multi-doc in data/templates/. Returns list of dicts."""
    wanted = None
    if only:
        wanted = {t.strip().lower() for t in re.split(r"[,\s]+", str(only)) if t.strip()}
    out = []
    if not os.path.isdir(TEMPLATES_DIR):
        return out
    for fn in sorted(os.listdir(TEMPLATES_DIR)):
        if not fn.endswith((".yaml", ".yml")):
            continue
        try:
            with open(os.path.join(TEMPLATES_DIR, fn), encoding="utf-8") as f:
                for doc in yaml.safe_load_all(f):
                    if not isinstance(doc, dict) or "id" not in doc:
                        continue
                    if wanted and str(doc["id"]).lower() not in wanted:
                        continue
                    out.append(doc)
        except Exception:
            continue
    return out


def evaluate(matchers, condition, status, body):
    """True when matchers agree (and|or). Supported: status, word, regex."""
    verdicts = []
    for m in matchers or []:
        t = m.get("type")
        if t == "status":
            want = m.get("status") or []
            if isinstance(want, int):
                want = [want]
            verdicts.append(status in want)
        elif t == "word":
            low = (body or "").lower()
            words = [w.lower() for w in (m.get("words") or [])]
            any_hit = any(w in low for w in words)
            verdicts.append(any_hit if m.get("condition", "any") == "any" else all(w in low for w in words))
        elif t == "regex":
            low = body or ""
            any_hit = any(re.search(rx, low, re.I) for rx in (m.get("regex") or []))
            verdicts.append(any_hit)
    if not verdicts:
        return False
    return all(verdicts) if (condition or "and") == "and" else any(verdicts)


def _join(base, path):
    split = urlsplit(base)
    root = f"{split.scheme}://{split.netloc}"
    return root + ("/" + path.lstrip("/") if path else "/")


@register(name="vf_template_scan",
          desc="INTERNAL NUCLEI: run declarative YAML templates (data/templates/) "
               "against a target — git leaks, .env, phpinfo, swagger, graphql "
               "introspection, actuator, debug endpoints. Every hit is a finding "
               "with severity. templates=all | id[,id2]. Extend the arsenal by "
               "writing templates, not code.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "target base URL"},
              "templates": {"type": "string", "description": "template id, comma list, or 'all'"},
              "timeout": {"type": "integer", "default": 12}},
              "required": ["url"]},
          danger="active")
def vf_template_scan(url, templates=None, timeout=12):
    tpl = load_templates(templates)
    if not tpl:
        return ("TOOL ERROR [NO_TEMPLATES]: rien dans data/templates/ "
                f"(filtre: {templates or 'all'})")
    hits, sent = [], 0
    for t in tpl:
        for req in (t.get("requests") or []):
            path = req.get("path") or "/"
            full = _join(url, path)
            st, body, dt = paced_send(full, method=(req.get("method") or "GET").upper(),
                                      timeout=int(timeout or 12))
            sent += 1
            if st < 0:
                continue
            if evaluate(t.get("matchers"), t.get("matchers-condition"), st, body):
                info = t.get("info") or {}
                ev = re.search(r"(<title>[^<]*</title>|.{0,60})", body or "")
                hits.append({
                    "id": t["id"],
                    "severity": (info.get("severity") or "medium").lower(),
                    "title": info.get("title") or t["id"],
                    "url": full,
                    "status": st,
                    "evidence": (ev.group(0) if ev else "")[:80],
                })
    # persist, dedup by (id, url)
    stored = []
    try:
        if os.path.exists(FINDINGS_PATH):
            with open(FINDINGS_PATH, encoding="utf-8") as f:
                stored = json.load(f)
    except Exception:
        stored = []
    seen = {(s.get("id"), s.get("url")) for s in stored}
    for h in hits:
        if (h["id"], h["url"]) not in seen:
            stored.append({**h, "ts": round(time.time(), 3)})
            seen.add((h["id"], h["url"]))
    try:
        os.makedirs(os.path.dirname(FINDINGS_PATH), exist_ok=True)
        with open(FINDINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(stored[-500:], f, ensure_ascii=False, indent=1)
    except Exception:
        pass

    lines = [f"TEMPLATE SCAN — {sent} requêtes, {len(tpl)} templates, {len(hits)} HITS."]
    if hits:
        lines.append("")
        for h in sorted(hits, key=lambda x: ("critical", "high", "medium", "low").index(
                x["severity"] if x["severity"] in ("critical", "high", "medium", "low") else "medium")):
            lines.append(f"[{h['severity'].upper()}] {h['id']} — st={h['status']} — {h['url']}")
            if h["evidence"]:
                lines.append(f"        preuve: {h['evidence']}")
    else:
        lines.append("Aucun hit — la surface reste propre sur ce pack.")
    return "\n".join(lines)
