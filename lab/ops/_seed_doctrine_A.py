# -*- coding: utf-8 -*-
"""Seed the doctrine from mission A's transcript — the wins A discovered
(openapi.json pattern, X-Admin-Token, forge-on-truncation) become the
law mission B starts under. This is the compounding test."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import doctrine as doc

# load A's transcript
tr = []
with open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "lab", "calib_A", "transcript.jsonl"),
        encoding="utf-8") as f:
    for line in f:
        try:
            o = json.loads(line)
            tr.append((o["kind"], o["entry"]))
        except Exception:
            pass

doc.reset()
doc.load()
before = len(doc._ENTRIES)
minted = doc.mint_wins(tr)
doc.save()
after = len(doc._ENTRIES)
print(f"seeded: {before} → {after} entries ({len(minted)} minted)")
for e in doc._ENTRIES:
    print(f"  [{e['origin']:11s}] {e['where']:12s} | {e['predicate'][:70]}")
