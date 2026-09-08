# -*- coding: utf-8 -*-
"""Reports dir organization: old auto-generated mission reports +
telegram harvests -> reports/archive/ (evidence preserved, dir clean)."""
import os
import shutil
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

REP = "reports"
ARCH = os.path.join(REP, "archive")
os.makedirs(ARCH, exist_ok=True)

now = time.time()
CUTOFF = now - 2 * 86400  # keep last 48h live

moved = 0
for f in os.listdir(REP):
    p = os.path.join(REP, f)
    if not os.path.isfile(p):
        continue
    age = now - os.path.getmtime(p)
    # report_*.md auto-generated mission outputs — historical beyond 48h
    if f.startswith("report_") and age > CUTOFF:
        shutil.move(p, os.path.join(ARCH, f))
        moved += 1
        continue
    # telegram harvests + caches from past hunts — archive
    if f.endswith("_history.json") or f in ("breaker_cache.json",
                                             "tamper_matrix.json"):
        shutil.move(p, os.path.join(ARCH, f))
        moved += 1
        continue
    # the big intel exec summaries from past ecosystems — archive
    if f.endswith(".md") and age > CUTOFF and f not in ("README.md",):
        shutil.move(p, os.path.join(ARCH, f))
        moved += 1

print(f"archived {moved} files")
print("live in reports/:", sorted(os.listdir(REP)))
