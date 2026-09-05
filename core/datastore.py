"""VOIDFORGE :: datastore cascade (Phase 0.6 — metasploit datastore).

Metasploit's lesson (audit): the datastore is a layered KV cascade —
user → global → fallback → default — determinism first, model second.
One `set SESSION cookie_string` and every module consults the same
value; nobody re-passes it per call.

Our shape: a per-mission store the AGENT writes through a small tool
(mission_globals), and the registry's execute() fills MISSING call
params from it before the tool runs (call args always win — the cascade
only fills holes, never overrides an explicit choice). Batch_execute
inherits through the same choke point.

Layers (highest wins on read):
  mission   set this mission (via the tool or agent internals)
  session   cross-mission sticky values (operator config later)

The cascade mapping (param name → datastore key) is CURATED, closed,
and lives in tools/__init__._CASCADE — we only auto-fill params we
understand (credentials/headers/payload hosts), never guess.
"""
import threading

_LOCK = threading.Lock()
_STORE = {"mission": {}, "session": {}}
_MISSION = {"id": None}


def start_mission(mission_id):
    """Fresh mission layer per mission (call from agent.run's init)."""
    with _LOCK:
        _STORE["mission"] = {}
        _MISSION["id"] = mission_id


def set(key, value, layer="mission"):
    """Write a global. Value must be scalar/str-dict (JSON-able, small) —
    the store is for parameters, not blobs."""
    try:
        with _LOCK:
            if layer not in _STORE:
                layer = "mission"
            s = str(value)
            if len(s) > 4096:
                s = s[:4096]          # a cookie yes, a dump no
            _STORE[layer][str(key)] = s
    except Exception:
        pass


def get(key, default=None):
    """Cascade read: mission layer → session layer → default."""
    with _LOCK:
        for layer in ("mission", "session"):
            v = _STORE[layer].get(str(key))
            if v is not None:
                return v
    return default


def unset(key, layer="mission"):
    try:
        with _LOCK:
            _STORE[layer].pop(str(key), None)
    except Exception:
        pass


def all(layer=None):
    """Read-only snapshot (the tool's listing)."""
    with _LOCK:
        if layer:
            return dict(_STORE.get(layer) or {})
        out = {}
        for lay in ("session", "mission"):     # lower layers first
            out.update(_STORE.get(lay) or {})
        return out


def reset():
    """Test hygiene."""
    with _LOCK:
        _STORE["mission"] = {}
        _STORE["session"] = {}
        _MISSION["id"] = None
