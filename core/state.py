"""VOIDFORGE :: Mission state persistence (SQLite).
Stores mission history, tool runs, and findings for dashboard queries + crash recovery."""
import sqlite3, json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "missions.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    """Create tables if they don't exist."""
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_text TEXT NOT NULL,
            mode TEXT DEFAULT 'IA',
            status TEXT DEFAULT 'running',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            summary TEXT,
            report_path TEXT
        );
        CREATE TABLE IF NOT EXISTS tool_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            args_json TEXT,
            result_json TEXT,
            duration REAL,
            status TEXT DEFAULT 'running',
            round INTEGER DEFAULT 1,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            FOREIGN KEY (mission_id) REFERENCES missions(id)
        );
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER NOT NULL,
            tool_name TEXT,
            severity TEXT DEFAULT 'info',
            finding_type TEXT,
            detail TEXT,
            found_at TEXT NOT NULL,
            FOREIGN KEY (mission_id) REFERENCES missions(id)
        );
    """)
    c.commit()
    c.close()


# Initialize on import
init_db()


def start_mission(mission_text, mode="IA"):
    """Record a new mission start. Returns mission_id."""
    c = _conn()
    now = datetime.datetime.now().isoformat()
    cur = c.execute(
        "INSERT INTO missions (mission_text, mode, status, started_at) VALUES (?, ?, 'running', ?)",
        (mission_text, mode, now))
    mid = cur.lastrowid
    c.commit()
    c.close()
    return mid


def finish_mission(mission_id, summary="", report_path="", status="complete"):
    c = _conn()
    now = datetime.datetime.now().isoformat()
    c.execute(
        "UPDATE missions SET status=?, finished_at=?, summary=?, report_path=? WHERE id=?",
        (status, now, summary, report_path, mission_id))
    c.commit()
    c.close()


def sweep_stale_missions():
    """Reconciliation sweep at boot: a crash leaves 'running' rows forever —
    mark them 'interrupted' so the DB tells the truth again."""
    try:
        c = _conn()
        cur = c.execute(
            "UPDATE missions SET status='interrupted', "
            "finished_at=? WHERE status='running'",
            (datetime.datetime.now().isoformat(),))
        c.commit()
        c.close()
        return cur.rowcount
    except Exception:
        return 0


def get_running_mission():
    """The latest running mission row, or None."""
    c = _conn()
    row = c.execute(
        "SELECT id, mission_text, mode, started_at FROM missions "
        "WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    if not row:
        return None
    return {"mission_id": row[0], "mission_text": row[1],
            "mode": row[2], "started_at": row[3]}


def start_tool_run(mission_id, tool_name, args, round_num=1):
    """Record a tool execution start. Returns tool_run_id."""
    c = _conn()
    now = datetime.datetime.now().isoformat()
    cur = c.execute(
        "INSERT INTO tool_runs (mission_id, tool_name, args_json, status, round, started_at) VALUES (?, ?, ?, 'running', ?, ?)",
        (mission_id, tool_name, json.dumps(args, ensure_ascii=False, default=str), round_num, now))
    trid = cur.lastrowid
    c.commit()
    c.close()
    return trid


def finish_tool_run(tool_run_id, result, duration, status="ok"):
    c = _conn()
    now = datetime.datetime.now().isoformat()
    result_trunc = result[:8000] if isinstance(result, str) else json.dumps(result, default=str)[:8000]
    c.execute(
        "UPDATE tool_runs SET result_json=?, duration=?, status=?, finished_at=? WHERE id=?",
        (result_trunc, duration, status, now, tool_run_id))
    c.commit()
    c.close()


def add_finding(mission_id, tool_name, severity, finding_type, detail):
    c = _conn()
    now = datetime.datetime.now().isoformat()
    c.execute(
        "INSERT INTO findings (mission_id, tool_name, severity, finding_type, detail, found_at) VALUES (?, ?, ?, ?, ?, ?)",
        (mission_id, tool_name, severity, finding_type, detail[:2000], now))
    c.commit()
    c.close()


def get_missions(limit=50):
    c = _conn()
    rows = c.execute(
        "SELECT * FROM missions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_mission(mission_id):
    c = _conn()
    m = c.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
    tools = c.execute(
        "SELECT * FROM tool_runs WHERE mission_id=? ORDER BY id", (mission_id,)).fetchall()
    finds = c.execute(
        "SELECT * FROM findings WHERE mission_id=? ORDER BY id", (mission_id,)).fetchall()
    c.close()
    if not m:
        return None
    return {
        "mission": dict(m),
        "tool_runs": [dict(t) for t in tools],
        "findings": [dict(f) for f in finds],
    }
# R2-11 : le doublon get_running_mission (shape full-row qui écrasait la
# version curated ci-dessus) a été supprimé — server.py ne consomme que
# mission_id/mission_text/mode/started_at, tous présents dans la 1ʳᵉ shape.
