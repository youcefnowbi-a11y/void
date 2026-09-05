"""TOOL: mission_globals — the datastore cascade editor (Phase 0.6).

Metasploit datastore, our shape: the agent sets mission-globals ONCE
(cookie, api key, sticky headers) and every tool call with a matching
missing param fills from it at the registry choke point. Determinism
first (law #3): explicit call args always win; the cascade only fills
holes, and the param→key map is curated in tools/__init__._CASCADE_KEYS.
"""
import json
from tools import register
from core import datastore


@register(
    name="mission_globals",
    desc="Set or read mission-global parameters (datastore cascade). "
         "Set once (auth_token, cookies, api_key, default_headers, proxy_url...) "
         "and later tool calls auto-fill missing matching params from it. "
         "Call args you pass explicitly always win.",
    params={"type": "object", "properties": {
        "action": {"type": "string", "enum": ["set", "get", "list", "unset"],
                   "description": "set: write globals; get: read one key; "
                                  "list: snapshot; unset: remove one"},
        "key": {"type": "string", "description": "datastore key (e.g. auth_token, cookies)"},
        "value": {"type": "string", "description": "value to set (scalars only, max 4KB)"},
        "layer": {"type": "string", "enum": ["mission", "session"],
                  "description": "mission (default) dies with the mission; session sticks across missions"}
    }, "required": ["action"]},
    danger="safe")
def mission_globals(action="list", key=None, value=None, layer="mission"):
    if action == "set":
        if not key:
            return json.dumps({"ok": False, "error": "key required for set"})
        datastore.set(key, value or "", layer=layer)
        return json.dumps({"ok": True, "action": "set", "key": key,
                           "layer": layer,
                           "cascade": [p for p, k in _cascade_map().items()
                                       if k == key]})

    if action == "get":
        if not key:
            return json.dumps({"ok": False, "error": "key required for get"})
        return json.dumps({"ok": True, "key": key,
                           "value": datastore.get(key)})

    if action == "unset":
        if not key:
            return json.dumps({"ok": False, "error": "key required for unset"})
        datastore.unset(key, layer=layer)
        return json.dumps({"ok": True, "action": "unset", "key": key})

    # list
    snap = datastore.all()
    masked = {k: (v[:6] + "…" if k in ("auth_token", "api_key", "cookies")
                  and len(v) > 6 else v) for k, v in snap.items()}
    return json.dumps({"ok": True, "action": "list", "globals": masked,
                       "mission": True}, ensure_ascii=False, indent=1)


def _cascade_map():
    from tools import _CASCADE_KEYS
    return _CASCADE_KEYS
