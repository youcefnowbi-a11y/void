# -*- coding: utf-8 -*-
"""Reports cleanup pass 2: filename dates are the truth (mtimes were
reset by a workspace copy). report_YYYYMMDD_* — keep >= 20260905 live,
archive the rest. Deterministic, evidence preserved."""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

ARCH = os.path.join("reports", "archive")
os.makedirs(ARCH, exist_ok=True)

CUTOFF = "20260905"  # keep the last two hunting days live

moved = kept = 0
for f in list(os.listdir("reports")):
    p = os.path.join("reports", f)
    if not os.path.isfile(p) or not f.startswith("report_"):
        continue
    # report_YYYYMMDD_HHMMSS.md
    try:
        date = f[7:15]
    except Exception:
        continue
    if not date.isdigit():
        continue
    if date < CUTOFF:
        shutil.move(p, os.path.join(ARCH, f))
        moved += 1
    else:
        kept += 1

print(f"archived {moved} / kept live {kept}")
live = [f for f in os.listdir("reports") if os.path.isfile(os.path.join("reports", f))]
print(f"live files in reports/: {len(live)}")
for f in sorted(live)[:20]:
    print(" ", f)
