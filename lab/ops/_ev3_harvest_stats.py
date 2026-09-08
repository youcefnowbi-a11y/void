# -*- coding: utf-8 -*-
"""EV3: plays harvester + doctrine stats evaluation."""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# plays store
try:
    with io.open("data/learned/plays.json", encoding="utf-8") as f:
        store = json.load(f)
    if isinstance(store, dict):
        plays = store.get("plays") or []
    else:
        plays = store
    print(f"plays total: {len(plays)}")
    tgt = [p for p in plays if "playformto" in str(p.get("target", ""))]
    dus = [p for p in plays if "duskyr" in str(p.get("target", ""))]
    print(f"  playformto plays: {len(tgt)}")
    print(f"  duskyr plays: {len(dus)}")
    if plays:
        p0 = plays[-1]
        keys = list(p0.keys()) if isinstance(p0, dict) else "str"
        print(f"  last play keys: {keys}")
except Exception as ex:
    print("plays store read failed:", type(ex).__name__, str(ex)[:100])

# doctrine
try:
    from core import doctrine as _doc
    entries = None
    for attr in ("_ENTRIES", "entries", "ENTRIES"):
        entries = getattr(_doc, attr, None)
        if entries:
            break
    if not entries:
        _loaded = _doc.load() if hasattr(_doc, "load") else []
        entries = _loaded if isinstance(_loaded, list) else getattr(_doc, "_ENTRIES", [])
    print(f"doctrine entries: {len(entries)}")
    def _used(e):
        if isinstance(e, dict):
            return e.get("used", 0) or e.get("score", 0) or 0
        return 0
    top = sorted(entries, key=_used, reverse=True)[:5]
    for e in top:
        if isinstance(e, dict):
            txt = str(e.get("text") or e.get("rule") or e)[:80]
            print(f"  used {_used(e)}x: {txt}")
except Exception as ex:
    print("doctrine read failed:", type(ex).__name__, str(ex)[:100])

# grimoire stats
try:
    from tools.grimoire_query import grimoire_query
    r = grimoire_query("stats")
    d = json.loads(r) if isinstance(r, str) else r
    print("grimoire stats:", json.dumps(d)[:200])
except Exception as ex:
    print("grimoire stats failed:", type(ex).__name__, str(ex)[:100])
