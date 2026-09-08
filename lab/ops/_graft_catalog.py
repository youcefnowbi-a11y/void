# -*- coding: utf-8 -*-
"""Graft the 2024-2026 threat-intel catalog into the grimoire feed as a new
domain (DIFF — interpretation differentials / modern web+AI tradecraft)."""
import io, json, re, time

CAT = r"C:\Users\youcefcheriet\D\deepseek-harness\threat-intel-catalog-2024-2026.md"
FEED = "data/grimoire.feed.json"
MAN = "data/grimoire_manifest.json"

src = io.open(CAT, encoding="utf-8").read()

# parse technique blocks: **X.Y Name** — description / Root cause: / Find it:
entries = []
for m in re.finditer(
        r"\*\*(\d+\.\d+)\s+([^*]+?)\*\*\s*[—-]\s*(.+?)(?=\n\*\*|\n##|\nAppendix|\Z)",
        src, re.S):
    num, name, body = m.group(1), m.group(2).strip(), m.group(3).strip()
    root = ""
    findit = ""
    rm = re.search(r"Root cause:\s*(.+?)(?=\nFind it:|\n[A-Z][a-z]+:|\Z)", body, re.S)
    fm = re.search(r"Find it:\s*(.+?)(?=\n[A-Z][a-z]+:|\Z)", body, re.S)
    if rm: root = " ".join(rm.group(1).split())
    if fm: findit = " ".join(fm.group(1).split())
    desc = " ".join(body.split("\n")[0].split())
    if not desc or len(desc) < 30:
        desc = root or findit
    section_num = num.split(".")[0]
    sec_names = {"1": "web-surface", "2": "weird-tricks", "3": "secrets",
                 "4": "auth-bypass", "5": "ai-era"}
    sec = sec_names.get(section_num, "misc")
    summary = desc if len(desc) < 400 else desc[:397] + "..."
    detection = ("RECON-SIGNAL: " + (findit[:380] if findit else "n/a")
                 + (" | ROOT-CAUSE: " + root[:200] if root else ""))
    entries.append({
        "id": f"GRM-DIFF-{int(float(num))*100+int(num.split('.')[1]):04d}",
        "name": name,
        "klass": "interpretation-differential",
        "mitre": "", "capec": "", "cwe": "",
        "difficulty": "hard",
        "reliability": "conditional",
        "blast_radius": "medium",
        "reversibility": "reversible",
        "requires_confirmation": False,
        "summary": summary,
        "detection": detection if len(detection) < 700 else detection[:697] + "...",
        "references": ["threat-intel-catalog-2024-2026.md (PortSwigger Top-10 2024+2025, HN-validated, zhero, WatchTowr, DEF CON 32)"],
        "atomic_coverage": [],
        "_source_file": "threat-intel-catalog-2024-2026.md",
        "_domain": "Interpretation differentials (modern web + AI-era tradecraft 2024-2026)",
        "_domain_code": "DIFF",
        "_section": sec,
    })

print("parsed techniques:", len(entries))

feed = json.load(io.open(FEED, encoding="utf-8"))
techs = feed["techniques"]
existing_ids = {t.get("id") for t in techs}
added = 0
for e in entries:
    if e["id"] not in existing_ids:
        techs.append(e)
        added += 1
feed["pack_meta"]["domains"] = sorted({t.get("_domain_code", "?") for t in techs})

# update the domain index if present
ix = feed.get("indexes") or {}
if isinstance(ix, dict) and "domains" in ix:
    ix["domains"] = feed["pack_meta"]["domains"]

json.dump(feed, io.open(FEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

man = json.load(io.open(MAN, encoding="utf-8"))
man["_meta"]["version"] = "1.5.0"
man["_meta"]["built_at"] = time.strftime("%Y-%m-%d")
man["provenance"]["verification_status"]["diff_domain"] = (
    "NEW 1.5.0 - GRM-DIFF-### (%d techniques): 2024-2026 interpretation-differential "
    "tradecraft grafted from the live-researched threat-intel catalog (PortSwigger "
    "community Top-10 2024+2025, HN point-validated AI incidents, zhero Next.js "
    "chains, WatchTowr 2026, DEF CON 32). Each record carries the recon-signal "
    "trigger in its detection field — the agent arms modules on disagreement "
    "surfaces (parser vs parser, cache vs origin, human-visible vs model-visible)." % added)
json.dump(man, io.open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("added:", added, "| total techniques:", len(techs))
