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
    # F1 discipline, réaffirmée: un tool vide = play INATTRIBUABLE = pas de
    # play. (L'ancien `tool or "?"` a minté un play orphelin uses=11 dans le
    # stockpile venice — trouvé par l'audit E2 de la vault.)
    tool = (tool or "").strip()
    if not tool:
        return None
    url = a.get("url") or ""
    if not url or "://" not in url:
        return None
    sp = urlsplit(url)
    host = sp.netloc.lower()
    if not host:
        return None
    first_label = host.split(":")[0].split(".")[0]
    if (host.startswith(("127.", "192.168.", "10.", "169.254."))
            or first_label == "localhost"
            or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host)):
        return None  # AUDIT F9: jamais de play depuis une adresse privée
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
    """rows: [{round, tool_name, args_json, result_json, started_at}] → plays.

    AUDIT F1: les batchs sérialisent un résultat PAR APPEL dans
    results[i]["result"] (string échappée) — l'ordre d'exécution = l'ordre
    des calls. L'attribution est donc PAR ITEM, jamais par ligne : un
    web_fingerprint 200 dans le même batch qu'un POST 403 ne fabrique plus
    de play fantôme. Sans forme reconnaissable, seule une ligne à UN appel
    est attribuable honnêtement."""
    out = []

    def _call_play(tool, a, item_res, ts):
        m = (a.get("method") or "GET").upper()
        ok_write = m in _WRITE_VERBS and (
            re.search(r'"status":\s*2\d\d', item_res) or
            '"success": true' in item_res or '"success":true' in item_res)
        if ok_write:
            p = _play_from_call(tool, a, f"{m} accepted", "", ts)
            if p:
                out.append(p)
        if re.search(r'"exploitable":\s*(true|"partial")', item_res, re.I):
            msum = re.search(r'"summary":\s*"([^"]{10,180})', item_res)
            p = _play_from_call(tool, a, (msum.group(1) if msum else
                                          "verdict exploitable"),
                                "", ts, kind="verdict")
            if p:
                out.append(p)

    for r in rows:
        ts = (r.get("started_at") or ts_default or "")[:19]
        row_res = r.get("result_json") or ""
        args = r.get("args_json") or ""
        calls = list(_iter_calls(args))
        # forme batch reconnue → attribution par item (l'ordre = les calls)
        items = None
        try:
            parsed = json.loads(row_res)
            if isinstance(parsed, dict) and isinstance(
                    parsed.get("results"), list):
                items = parsed["results"]
        except Exception:
            items = None
        if items is not None and len(items) == len(calls):
            for (tool, a), it in zip(calls, items):
                if not isinstance(it, dict):
                    continue
                item_res = (it.get("result") or "").replace('\\"', '"')
                _call_play(tool, a, item_res, ts)
        elif len(calls) == 1:
            # ligne mono-appel : le résultat EST cet appel (échappements
            # normalisés). AUDIT E2-V3: _iter_calls ne connaît pas le nom
            # de l'outil (il ne voit que args_json) → yield vide — le nom
            # VÉRITÉ est celui de la ligne (tool_name). L'ancien fallback
            # `tool or "?"` mintait tous les plays mono sous un tool
            # fantôme "?" (le play Clerk uses=11 du stockpile était un
            # play légitime mal nommé — l'audit vault l'a démasqué).
            tool, a = calls[0]
            tool = tool or (r.get("tool_name") or "").strip()
            _call_play(tool, a, row_res.replace('\\"', '"'), ts)
        # sinon (batch non reconnu, N appels) → pas d'attribution : mieux
        # vaut un arsenal petit et VRAI qu'un arsenal riche et menteur.
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
        # the agent's own NEXT MISSION PROPOSAL — persisted for the operator.
        # GUARD (op question 2026-09-02): a refusal is a BROKEN brain, its
        # words are not doctrine — the proposal layer eats completed-mission
        # speech only; the plays themselves stay wire-evidence (tool_runs),
        # which a refusal cannot fake.
        if final_text:
            try:
                from core.framing import is_refusal
                refused = is_refusal(final_text)
            except Exception:
                refused = False
            idx = (final_text.upper().find("NEXT MISSION PROPOSAL")
                   if not refused else -1)
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
    if generalize:
        # AUDIT F6: pas de prose d'une autre cible en round 0 — la structure
        # transfère, le texte de la cible A ne doit pas encadrer la cible B.
        return (f"- [{p['kind']}] {p['method']} https://{host}{p['path']}{body} "
                f"({p['tool']}, uses={p.get('uses', 1)}) [adapted from {p['host']}]")
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

        # AUDIT F3: la mission dit "venice.ai", les plays vivent sur
        # "outerface.venice.ai" — un play est SAME-TARGET dès que son host
        # EST la cible ou un SOUS-DOMAINE de la cible. Sinon le rappel
        # verbatim ne tire jamais et tout finit "adapted" à tort.
        def _same(h):
            if not target or not h:
                return False
            return h == target or ("." in target and h.endswith("." + target))

        same = [p for p in plays if _same(p.get("host"))]
        other = [p for p in plays if not _same(p.get("host"))]
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
            lines.append(_fmt_play(p, generalize=True))
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
