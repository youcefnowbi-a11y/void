"""VOIDFORGE :: the compounding arsenal — learned plays.

Every mission that PROVES a working call-grammar (a 200 on a write verb, a
confirmed verdict, an impact chain) teaches the next mission. Plays are
harvested mechanically from tool_runs (the DB of every executed call) and the
workspace, stored per target in data/learned/plays.json (gitignored — the
private stockpile), and recalled into the agent's system prompt:
  - same-target plays are injected VERBATIM (she skips re-derivation),
  - cross-target plays are injected as ADAPTED templates (host generalized
    to {TARGET} — grammar transfers, the host is hers to re-solve).

This is the 0-day-stockpile analog: not exploits, but PROVEN PROCEDURES that
compound with every campaign instead of decaying like the frozen tools.
"""
import json
import os
import re
import sqlite3
import time
from urllib.parse import urlsplit, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "core", "missions.db")
STORE = os.path.join(ROOT, "data", "learned", "plays.json")

_WRITE_VERBS = ("POST", "PATCH", "PUT", "DELETE")


# ── store ─────────────────────────────────────────────────────────
def _load(store=STORE):
    try:
        with open(store, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("plays"), list):
            d.setdefault("proposals", {})
            return d
    except Exception:
        pass
    return {"plays": [], "proposals": {}}


def _save(d, store=STORE):
    os.makedirs(os.path.dirname(store), exist_ok=True)
    tmp = store + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, store)


def _dedupe_key(p):
    # l'IDENTITÉ d'un play = sa grammaire (host, méthode, path, body-shape,
    # outcome) — PAS l'outil qui l'a exécutée : le même appel vu via
    # data_extract puis batch_execute est UN play, pas deux.
    return (p.get("host"), p.get("kind"), p.get("method"),
            p.get("path"), p.get("body_keys") and tuple(p["body_keys"]) or (),
            (p.get("outcome") or "")[:80])


def merge_plays(existing, incoming):
    """Dedupe by identity; new → append; known → bump uses + last_seen."""
    index = {_dedupe_key(p): p for p in existing}
    added = 0
    for p in incoming:
        k = _dedupe_key(p)
        if k in index:
            old = index[k]
            old["uses"] = old.get("uses", 1) + 1
            old["last_seen"] = p.get("ts")
        else:
            index[k] = p
            existing.append(p)
            added += 1
    return added


# ── harvest: the DB of executed calls → plays ─────────────────────
def _iter_calls(args):
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return
    if not isinstance(args, dict):
        return
    calls = args.get("calls")
    if isinstance(calls, list):
        for c in calls:
            if isinstance(c, dict):
                yield (c.get("tool") or ""), (c.get("args") or {})
    else:
        yield "", args


def _play_from_call(tool, a, outcome, proof, ts, kind="grammar"):
    url = a.get("url") or ""
    if not url or "://" not in url:
        return None
    sp = urlsplit(url)
    host = sp.netloc.lower()
    if not host or host.startswith(("127.", "192.168.", "10.")):
        return None
    method = (a.get("method") or "GET").upper()
    path = sp.path or "/"
    # généralisation : tout jeton d'instance vivant dans le path (sess_xxx,
    # cs_live_xxx, uuid…) devient {ID} — le play est un TEMPLATE réutilisable,
    # pas un artefact de session mort.
    path = re.sub(r"(?<=/)[A-Za-z0-9_\-]{18,}(?=/|$)", "{ID}", path)
    qkeys = sorted(parse_qs(sp.query).keys())
    if qkeys:
        path += "?" + "&".join(k + "=" for k in qkeys)
    body = a.get("body")
    body_keys = sorted(body.keys()) if isinstance(body, dict) else []
    return {"ts": ts, "kind": kind, "host": host, "tool": tool or "?",
            "method": method, "path": path[:180],
            "body_keys": body_keys, "outcome": (outcome or "")[:160],
            "proof": (proof or "")[:120], "uses": 1, "last_seen": ts}


def _plays_from_rows(rows, ts_default=None):
    """rows: [{round, tool_name, args_json, result_json, started_at}] → plays."""
    out = []
    for r in rows:
        ts = (r.get("started_at") or ts_default or "")[:19]
        # les batchs sérialisent leurs sous-résultats EN STRING → guillemets
        # échappés (\"status\": 200). Normaliser AVANT tout matching, sinon
        # la moitié des preuves rate silencieusement.
        res = (r.get("result_json") or "").replace('\\"', '"')
        args = r.get("args_json") or ""
        # proven write grammar: write verb + 200/201 in the same run
        proven_2xx = bool(re.search(r'"status":\s*2\d\d', res))
        proven_ok = '"success": true' in res or '"success":true' in res
        for tool, a in _iter_calls(args):
            m = (a.get("method") or "GET").upper()
            if m in _WRITE_VERBS and (proven_2xx or proven_ok):
                p = _play_from_call(tool, a, f"{m} accepted", "", ts)
                if p:
                    out.append(p)
        # verdict-contract wins (exploitable true/partial) — the strikes
        if re.search(r'"exploitable":\s*(true|"partial")', res, re.I):
            msum = re.search(r'"summary":\s*"([^"]{10,180})', res)
            for tool, a in _iter_calls(args):
                p = _play_from_call(tool, a, (msum.group(1) if msum else
                                              "verdict exploitable"),
                                    "", ts, kind="verdict")
                if p:
                    out.append(p)
    return out


def harvest(mission_id, ws=None, final_text=None, db_path=DB, store=STORE):
    """Harvest the finished mission into the arsenal. Returns count of NEW plays."""
    added = 0
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = [dict(r) for r in con.execute(
            "SELECT round, tool_name, args_json, result_json, started_at "
            "FROM tool_runs WHERE mission_id=? ORDER BY id", (mission_id,))]
        con.close()
        d = _load(store)
        incoming = _plays_from_rows(rows)
        if incoming:
            added = merge_plays(d["plays"], incoming)
            d["plays"].sort(key=lambda p: -(p.get("uses", 1)))
            if len(d["plays"]) > 400:
                d["plays"] = d["plays"][:400]
        # the agent's own NEXT MISSION PROPOSAL — persisted for the operator
        if final_text:
            idx = final_text.upper().find("NEXT MISSION PROPOSAL")
            if idx >= 0 and ws is not None:
                try:
                    sect = final_text[idx - 3:]
                    nxt = re.search(r"\n## ", sect[3:])
                    sect = sect[:3 + nxt.start()].strip() if nxt else sect.strip()
                    with open(os.path.join(ws.reports, "next_mission.md"),
                              "w", encoding="utf-8") as f:
                        f.write(sect[:6000])
                    d["proposals"][ws.target or "untitled"] = {
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "text": sect[:3000]}
                except Exception:
                    pass
        _save(d, store)
    except Exception as ex:
        print(f"[learned_plays] WARN harvest failed: {type(ex).__name__}: {ex}")
    return added


# ── recall: the arsenal speaks before round 0 ─────────────────────
def _fmt_play(p, generalize=False):
    host = "{TARGET}" if generalize else p["host"]
    bk = ",".join(p.get("body_keys") or [])
    body = f" body({bk})" if bk else ""
    return (f"- [{p['kind']}] {p['method']} https://{host}{p['path']}{body} "
            f"→ {p['outcome']} ({p['tool']}, uses={p.get('uses', 1)})")


def recall_block(mission_text, store=STORE, cap=2600):
    """FIELD MANUAL for the system prompt — prior campaigns speak first."""
    try:
        d = _load(store)
        plays = d.get("plays") or []
        if not plays:
            return ""
        from core.mission_workspace import extract_target
        target = extract_target(mission_text)
        same = [p for p in plays if target and p.get("host") == target]
        other = [p for p in plays if not target or p.get("host") != target]
        lines = ["FIELD MANUAL (learned plays — proven call grammars from "
                 "prior campaigns. Same-target entries are VERIFIED on this "
                 "host: reuse them directly instead of re-deriving; adapted "
                 "entries are grammar templates to re-solve against the new "
                 "target):", ""]
        n = 0
        for p in same[:14]:
            lines.append(_fmt_play(p))
            n += 1
        if same:
            lines.append("")
        for p in other[:6]:
            lines.append(_fmt_play(p, generalize=True) +
                         f" [adapted from {p['host']}]")
            n += 1
        prop = (d.get("proposals") or {}).get(target)
        if prop:
            lines += ["", "PREVIOUS CAMPAIGN'S NEXT-MISSION PROPOSAL "
                          f"({prop.get('ts', '')}):",
                      (prop.get("text") or "")[:1200]]
        blk = "\n".join(lines)
        return blk[:cap] if n else ""
    except Exception:
        return ""
