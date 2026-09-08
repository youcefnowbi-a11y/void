# -*- coding: utf-8 -*-
"""EV3 retro-harvest: mint plays from existing mission ledgers."""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from core.learned_plays import harvest_from_ledger, STORE  # noqa: E402

with io.open(STORE, encoding="utf-8") as f:
    before = len(json.load(f).get("plays", []))
print("plays before:", before)

for target_dir in sorted(os.listdir("missions")):
    ledger = os.path.join("missions", target_dir, "ledger.jsonl")
    if not os.path.isfile(ledger):
        continue
    n_lines = sum(1 for _ in io.open(ledger, encoding="utf-8"))
    # lightweight pseudo-ws (harvest only touches ledger_path + reports
    # on proposal-mint, which we skip here)
    class _W:
        def __init__(self, t):
            self.ledger_path = ledger
            self.target = target_dir
            self.reports = os.path.join("missions", target_dir, "reports")
    n = harvest_from_ledger(_W(target_dir))
    print(f"  {target_dir}: {n_lines} ledger lines -> +{n} plays")

with io.open(STORE, encoding="utf-8") as f:
    after = json.load(f).get("plays", [])
print("plays after:", len(after))
hosts = {}
for p in after:
    hosts[p.get("host", "?")] = hosts.get(p.get("host", "?"), 0) + 1
for h, n in sorted(hosts.items(), key=lambda x: -x[1])[:10]:
    print(f"  {n:3d}x {h[:60]}")
