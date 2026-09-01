"""TOOL: payload_library - the munitions depot.

Serves the local payload corpus (data/payloads/, seeded from
PayloadsAllTheThings + SecLists + internal seeds) filtered by vulnerability
class. The strategist PIOC HES from proven community ordnance instead of
improvising. Read-only, network-free, ROE-safe.
"""
import json
import os

from tools import register

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDX = os.path.join(_HERE, "data", "payloads", "index.json")
_BASE = os.path.join(_HERE, "data", "payloads")

_index_cache = [None, 0.0]


def _load_index():
    mtime = os.path.getmtime(_IDX) if os.path.exists(_IDX) else 0.0
    if _index_cache[0] is None or _index_cache[1] != mtime:
        try:
            with open(_IDX, encoding="utf-8") as f:
                _index_cache[0] = json.load(f)
            _index_cache[1] = mtime
        except Exception:
            _index_cache[0] = {"classes": {}}
    return _index_cache[0]


def _read_class(entry, limit):
    out, seen = [], set()
    for rel in entry.get("files", []):
        p = os.path.normpath(os.path.join(_BASE, rel))
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip().lstrip("\ufeff").strip()
                    if not line or line.startswith("#"):
                        continue
                    if line in seen:
                        continue
                    seen.add(line)
                    out.append(line[:200])
                    if len(out) >= limit:
                        return out
        except Exception:
            continue
    return out


@register(name="payload_library",
          desc="Serve proven payloads by vulnerability class (sqli, xss, lfi, cmd, "
               "ssti, nosql, open_redirect, proto_pollute, subdomains, dirs) from the "
               "local munitions depot (PayloadsAllTheThings + SecLists corpus). op=list "
               "shows classes; op=get returns up to `limit` payloads for `vclass`.",
          params={"type": "object", "properties": {
              "op": {"type": "string", "enum": ["list", "get"], "default": "list"},
              "vclass": {"type": "string",
                         "description": "payload class, see op=list"},
              "limit": {"type": "integer", "default": 40}},
              "required": []},
          danger="safe")
def payload_library(op="list", vclass=None, limit=40):
    idx = _load_index()
    classes = idx.get("classes") or {}
    if (op or "list") == "list":
        lines = ["MUNITIONS DEPOT — classes disponibles (source: PayloadsAllTheThings + SecLists):"]
        for cls, entry in classes.items():
            n = sum(sum(1 for _ in open(os.path.normpath(os.path.join(_BASE, rel)),
                                        encoding="utf-8", errors="replace"))
                    for rel in entry.get("files", [])
                    if os.path.isfile(os.path.normpath(os.path.join(_BASE, rel))))
            lines.append(f"- {cls}: ~{n} payloads ({entry.get('source', '?')})")
        return "\n".join(lines)

    entry = classes.get((vclass or "").lower())
    if not entry:
        return f"TOOL ERROR [UNKNOWN_CLASS]: '{vclass}' — classes: {', '.join(sorted(classes))}"
    limit = max(1, min(int(limit or 40), 200))
    payloads = _read_class(entry, limit)
    if not payloads:
        return f"TOOL ERROR [EMPTY]: no payloads found for '{vclass}' on disk"
    head = (f"[{vclass}] {len(payloads)} payloads — source: {entry.get('source', '?')}.\n"
            "Utilise-les telles quelles dans les outils de probe/fuzz (pas de mutation "
            "nécessaire — ce sont des ordonnances éprouvées).\n")
    return head + "\n".join(payloads)
