# -*- coding: utf-8 -*-
"""E2 — THE UNIFIED CAPABILITY VAULT (law 1: loader + vault, never monolith).

One read/write path over the three capability stores:
  play   → core.learned_plays   (data/learned/plays.json, uses-native)
  skill  → core.skills          (skills/*.md, usage counted here)
  forged → tools registry       (tools/forged_*.py, usage counted here)

The vault NEVER moves data — thin adapters over the native stores, plus a
usage/versioning metadata layer (data/learned/vault_meta.json, gitignored
like the rest of data/learned/). What it adds:
  • unified reuse score across kinds (plays carry uses natively; skills and
    forged tools get counted at load/execution)
  • versioned deposits: every deposit records content hash + mission
    provenance, so a capability's history is auditable
  • capability_block(): the ranked prompt block — the OPERATOR-AGENT SEES
    the vault, top-reuse first, instead of guessing what exists
Atomic writes (tmp+replace), corrupt-store degradation to honest empty,
hard caps so the block can never flood a prompt.
"""
import json
import os
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, "data", "learned", "vault_meta.json")
KINDS = ("play", "skill", "forged")
_META_LOCK = None  # late-bound threading.Lock (cheap, import-safe)
_MAX_VERSIONS = 8       # per capability
_MAX_BLOCK_CHARS = 2200


def _lock():
    global _META_LOCK
    if _META_LOCK is None:
        import threading
        _META_LOCK = threading.Lock()
    return _META_LOCK


def _load_meta():
    try:
        with open(META, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}  # corrupt / missing → honest empty, vault still works


def _save_meta(d):
    os.makedirs(os.path.dirname(META), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(META), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, META)  # atomic on both filesystems
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass


# ── usage scoring ────────────────────────────────────────────────────

def touch(kind, cap_id):
    """Count one USE of a capability. Plays self-count at harvest; this is
    the counter for skills (on load) and forged tools (on execute)."""
    if kind not in KINDS or not cap_id:
        return
    with _lock():
        d = _load_meta()
        u = d.setdefault("usage", {})
        rec = u.setdefault(f"{kind}:{cap_id}", {"uses": 0, "last_seen": 0})
        rec["uses"] += 1
        rec["last_seen"] = time.time()
        _save_meta(d)


def _usage(kind, cap_id):
    d = _load_meta()
    return (d.get("usage", {}).get(f"{kind}:{cap_id}", {}) or {}).get("uses", 0)


# ── inventory: one shape over three stores ───────────────────────────

def recall(kind=None):
    """Normalized inventory. Each item:
    {kind, id, score, payload} — score = proven reuse (plays: harvest uses;
    skills/forged: counted uses). A store failing degrades to its absence,
    never crashes the mission."""
    out = []
    if kind in (None, "play"):
        try:
            from core.learned_plays import _load
            for p in (_load() or {}).get("plays", []):
                if not (p.get("tool") or "").strip() or \
                        p.get("tool") == "?":
                    continue  # unattributable plays are not capabilities
                out.append({"kind": "play", "id": p.get("tool", "?"),
                            "score": int(p.get("uses", 1)),
                            "payload": p})
        except Exception:
            pass
    if kind in (None, "skill"):
        try:
            from core.skills import list_skills
            for s in list_skills() or []:
                out.append({"kind": "skill", "id": s.get("id", "?"),
                            "score": _usage("skill", s.get("id", "?")),
                            "payload": {"desc": s.get("desc", ""),
                                        "title": s.get("title", "")}})
        except Exception:
            pass
    if kind in (None, "forged"):
        try:
            from tools import _REGISTRY, _DISCOVERED
            if not _DISCOVERED:
                from tools import discover
                discover()
            for name, t in _REGISTRY.items():
                if name.startswith("forged_"):
                    out.append({"kind": "forged", "id": name,
                                "score": _usage("forged", name),
                                "payload": {"desc": t.get("desc", "")}})
        except Exception:
            pass
    return out


def top(n=12):
    inv = recall()
    # deterministic ranking: score desc, then kind, then id — a tie must
    # never reshuffle the block the agent memorized (prompt-cache stability
    # AND stable round-0 doctrine position both depend on it)
    inv.sort(key=lambda x: (-x["score"], x.get("kind", ""), str(x.get("id", ""))))
    return inv[:max(0, int(n))]


# ── versioned deposits ───────────────────────────────────────────────

def _content_hash(payload):
    import hashlib
    blob = payload if isinstance(payload, str) else \
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()[:12]


def deposit(kind, payload, provenance=""):
    """Deposit/version a capability. kind=play delegates to the native
    merge (dedupe + uses bump); skill/forged record a version entry —
    {hash, provenance, ts} — capped at _MAX_VERSIONS per capability."""
    if kind not in KINDS:
        return {"error": f"unknown kind {kind}"}
    ts = time.time()
    h = _content_hash(payload)
    if kind == "play":
        try:
            # Y1.1 (audit-4): the old code merged into a FRESH dict from
            # _load() and never called _save — {"ok": True} while the
            # data evaporated with the local variable. Every vault
            # depositor was writing to /dev/null with a receipt.
            from core.learned_plays import merge_plays, _load, _save, STORE
            d = _load()
            added = merge_plays(d.setdefault("plays", []),
                                [payload] if isinstance(payload, dict)
                                else [])
            _save(d, STORE)
            # merge_plays returns the ADDED count (int) — the old len()
            # on it crashed post-save and the except turned the whole
            # deposit into {"error": ...} even though the write happened.
            return {"ok": True, "kind": kind, "merged": int(added)}
        except Exception as e:
            return {"error": f"play merge failed: {e}"}
    cap_id = (payload.get("id") if isinstance(payload, dict)
              else str(payload))[:80]
    with _lock():
        d = _load_meta()
        v = d.setdefault("versions", {}).setdefault(
            f"{kind}:{cap_id}", [])
        if not any(e.get("hash") == h for e in v):
            v.append({"hash": h, "provenance": (provenance or "")[:200],
                      "ts": ts})
            d["versions"][f"{kind}:{cap_id}"] = v[-_MAX_VERSIONS:]
        _save_meta(d)
    return {"ok": True, "kind": kind, "id": cap_id, "hash": h,
            "version_count": len(d["versions"][f"{kind}:{cap_id}"])}


def versions(kind, cap_id):
    d = _load_meta()
    return d.get("versions", {}).get(f"{kind}:{cap_id}", [])


# ── the prompt block: the LLM SEES the vault ─────────────────────────

def capability_block(cap=_MAX_BLOCK_CHARS):
    """Round-0 prompt block, ranked by proven reuse. Empty stores → empty
    string (the block simply doesn't appear). AUDIT E2-V2: a kind with
    zero proven use must STILL be visible (untried ≠ nonexistent) — one
    availability line per silent kind, else the LLM never learns the
    forged arsenal exists until it happens to use one."""
    rows = top(10)
    if not rows:
        return ""
    lines = ["═══ CAPABILITY VAULT (your arsenal, ranked by PROVEN reuse) ═══"]
    for r in rows:
        desc = (r["payload"].get("desc") or
                r["payload"].get("title") or
                r["payload"].get("grammar") or "")[:90]
        lines.append(f"- [{r['kind']}] {r['id']} "
                     f"(reuse={r['score']}) {desc}")
    shown = {(r["kind"]) for r in rows}
    # Y1.2 (audit-4): top(10) ranked purely by reuse buried skills and
    # forged tools below high-use plays — used-once capabilities were
    # invisible to the LLM. Every KIND now gets a guaranteed slot: the
    # top entry of any silent kind rides the block.
    inv = recall()
    for kind in ("skill", "forged"):
        if kind in shown:
            continue
        items = sorted((r for r in inv if r["kind"] == kind),
                       key=lambda r: -r["score"])
        if items:
            r = items[0]
            desc = (r["payload"].get("desc") or
                    r["payload"].get("title") or "")[:90]
            lines.append(f"- [{kind}] {r['id']} (reuse={r['score']}) {desc}"
                         f"  ← top of {len(items)} available {kind}s")
            shown.add(kind)
    for kind, label in (("forged", "forged tools"),
                        ("skill", "skills")):
        if kind in shown:
            continue
        items = [r for r in inv if r["kind"] == kind]
        if not items:
            continue
        untried = [r for r in items if r["score"] == 0]
        if untried:
            names = ", ".join(r["id"].replace("forged_", "")
                              for r in untried[:4])
            more = f" (+{len(untried) - 4} more)" if len(untried) > 4 else ""
            lines.append(f"- [{kind}] {len(items)} {label} available, "
                         f"none proven yet — e.g. {names}{more}")
    lines.append("Reuse beats re-derivation: play = proven call grammar on a "
                 "host; skill = composed expertise chain; forged = a tool the "
                 "platform forged for a past mission. High reuse = proven.")
    block = "\n".join(lines)
    return block[:cap]
