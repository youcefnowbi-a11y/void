# -*- coding: utf-8 -*-
"""observe77 — read-only live snapshot of the running mission.
DB truth: core/missions.db (core/state.py DB_PATH)."""
import sys, sqlite3, os
sys.path.insert(0, ".")
DB = os.path.join("core", "missions.db")
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
mid = db.execute("SELECT id, status, mode, started_at FROM missions "
                 "ORDER BY id DESC LIMIT 1").fetchone()
print(f"mission #{mid['id']} [{mid['status']}] {mid['mode']} "
      f"started {mid['started_at']}")
rows = db.execute(
    "SELECT round, tool_name, status, duration, substr(result_json,1,90) "
    "AS head FROM tool_runs WHERE mission_id=? ORDER BY id DESC LIMIT 16",
    (mid["id"],)).fetchall()
for r in reversed(rows):
    print(f"  r{r['round'] or '?'} {r['tool_name']} [{r['status']}] "
          f"{r['duration'] or 0}s {r['head'][:88]}")
n = db.execute("SELECT COUNT(*) FROM tool_runs WHERE mission_id=?",
               (mid["id"],)).fetchone()[0]
f = db.execute("SELECT COUNT(*) FROM findings WHERE mission_id=?",
               (mid["id"],)).fetchone()[0]
print(f"strikes: {n} | findings: {f}")
if os.path.exists("data/missions.db"):
    os.remove("data/missions.db")   # phantom DB created by my earlier miss
