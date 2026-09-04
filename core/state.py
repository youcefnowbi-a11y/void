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
    try:  # Z3.1: jamais de connexion fuie sur exception
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
    finally:
        c.close()


# Initialize on import
init_db()


def start_mission(mission_text, mode="IA"):
    """Record a new mission start. Returns mission_id."""
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        now = datetime.datetime.now().isoformat()
        cur = c.execute(
            "INSERT INTO missions (mission_text, mode, status, started_at) VALUES (?, ?, 'running', ?)",
            (mission_text, mode, now))
        mid = cur.lastrowid
        c.commit()
    finally:
        c.close()
    return mid


def finish_mission(mission_id, summary="", report_path="", status="complete"):
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        now = datetime.datetime.now().isoformat()
        c.execute(
            "UPDATE missions SET status=?, finished_at=?, summary=?, report_path=? WHERE id=?",
            (status, now, summary, report_path, mission_id))
        c.commit()
    finally:
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
    try:  # Z3.1: jamais de connexion fuie sur exception
        row = c.execute(
            "SELECT id, mission_text, mode, started_at FROM missions "
            "WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        c.close()
    if not row:
        return None
    return {"mission_id": row[0], "mission_text": row[1],
            "mode": row[2], "started_at": row[3]}


def start_tool_run(mission_id, tool_name, args, round_num=1):
    """Record a tool execution start. Returns tool_run_id."""
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        now = datetime.datetime.now().isoformat()
        cur = c.execute(
            "INSERT INTO tool_runs (mission_id, tool_name, args_json, status, round, started_at) VALUES (?, ?, ?, 'running', ?, ?)",
            (mission_id, tool_name, json.dumps(args, ensure_ascii=False, default=str), round_num, now))
        trid = cur.lastrowid
        c.commit()
    finally:
        c.close()
    return trid


def _shrink_result(result, budget=40000):
    """Z3.2 (audit-5): the old [:8000] cut killed the exploitable verdict
    whenever it sat past the 8KB boundary — harvest() then built plays
    from results that no longer SAID anything. Smart shrink: parse the
    JSON, keep verdict-bearing fields verbatim, elide big values
    head+tail, never exceed the budget."""
    txt = result if isinstance(result, str) else json.dumps(result, default=str)
    if len(txt) <= budget:
        return txt
    # verdict-bearing keys must survive ANY cut (harvest contract)
    _KEY = ("tool", "exploitable", "summary", "error", "verdict",
            "severity", "evidence")
    try:
        d = json.loads(txt)
        if isinstance(d, dict):
            small = dict(d)  # shallow copy — le verdict vit dedans
            blob = json.dumps(small, ensure_ascii=False, default=str)
            if len(blob) <= budget:
                return blob
            # still too big: shrink every big field head+tail
            for k in list(small.keys()):
                vs = json.dumps(small[k], ensure_ascii=False, default=str)
                if len(vs) > 1200:
                    small[k] = vs[:600] + f"…[elided {len(vs) - 1200} chars]" + vs[-600:]
            blob = json.dumps(small, ensure_ascii=False, default=str)
            if len(blob) <= budget:
                return blob
            # last resort: verdict keys ONLY + head of the rest
            keep = {k: d.get(k) for k in _KEY if k in d}
            keep["_elided"] = True
            keep["head"] = txt[:budget - 2000]
            return json.dumps(keep, ensure_ascii=False, default=str)[:budget]
    except Exception:
        pass
    half = budget // 2
    return txt[:half] + f"\n…[elided {len(txt) - budget} chars]\n" + txt[-half:]


def finish_tool_run(tool_run_id, result, duration, status="ok"):
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        now = datetime.datetime.now().isoformat()
        c.execute(
            "UPDATE tool_runs SET result_json=?, duration=?, status=?, finished_at=? WHERE id=?",
            (_shrink_result(result), duration, status, now, tool_run_id))
        c.commit()
    finally:
        c.close()


def add_finding(mission_id, tool_name, severity, finding_type, detail):
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        now = datetime.datetime.now().isoformat()
        c.execute(
            "INSERT INTO findings (mission_id, tool_name, severity, finding_type, detail, found_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mission_id, tool_name, severity, finding_type, detail[:2000], now))
        c.commit()
    finally:
        c.close()


def get_missions(limit=50):
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        rows = c.execute(
            "SELECT * FROM missions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]


def get_mission(mission_id):
    c = _conn()
    try:  # Z3.1: jamais de connexion fuie sur exception
        m = c.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        tools = c.execute(
            "SELECT * FROM tool_runs WHERE mission_id=? ORDER BY id", (mission_id,)).fetchall()
        finds = c.execute(
            "SELECT * FROM findings WHERE mission_id=? ORDER BY id", (mission_id,)).fetchall()
    finally:
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
