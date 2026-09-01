"""VOIDFORGE :: wire protocol codec — Seroval-style node trees + serverFn calls.

Implements the observed TanStack Start / Seroval wire format:
  {"t":1,"s":"text"}                    string
  {"t":2,"s":42}                        number
  {"t":3,"s":true}                      boolean
  {"t":0}                               null
  {"t":4}                               undefined
  {"t":5,"i":0,"s":[node,...]}          array
  {"t":6,"i":0,"s":{key: node,...}}     object (keys are plain strings)

The ForgeRange lab (lab/forge_range.py) parses exactly this format, so the
codec is CI-tested end to end. For exotic real targets, the ground truth
remains replay-mutation (tools/replay.py) — the app encodes its own traffic.
"""
import json

from tools._transport import fetch

NULL, STRING, NUMBER, BOOLEAN, UNDEFINED, ARRAY, OBJECT = 0, 1, 2, 3, 4, 5, 6


def seroval_encode(value, _idx=None):
    """Python value -> Seroval node tree."""
    if _idx is None:
        _idx = [0]
    if value is None:
        return {"t": NULL}
    if value is Ellipsis or isinstance(value, type(Undefined)):
        return {"t": UNDEFINED}
    if isinstance(value, bool):
        return {"t": BOOLEAN, "s": value}
    if isinstance(value, (int, float)):
        return {"t": NUMBER, "s": value}
    if isinstance(value, str):
        return {"t": STRING, "s": value}
    if isinstance(value, (list, tuple)):
        return {"t": ARRAY, "i": _idx[0], "s": [_seroval_child(v, _idx) for v in value]}
    if isinstance(value, dict):
        return {"t": OBJECT, "i": _idx[0],
                "s": {str(k): _seroval_child(v, _idx) for k, v in value.items()}}
    raise TypeError(f"seroval_encode: unsupported {type(value).__name__}")


class Undefined:
    __slots__ = ()


def _seroval_child(value, _idx):
    _idx[0] += 1
    node = seroval_encode(value, _idx)
    if "i" not in node and node["t"] in (ARRAY, OBJECT):
        node["i"] = _idx[0]
    return node


def seroval_decode(node):
    """Seroval node tree -> Python value."""
    if not isinstance(node, dict) or "t" not in node:
        return node
    t = node.get("t")
    if t == NULL:
        return None
    if t == UNDEFINED:
        return Undefined()
    if t in (STRING, NUMBER, BOOLEAN):
        return node.get("s")
    if t == ARRAY:
        return [seroval_decode(c) for c in node.get("s", [])]
    if t == OBJECT:
        return {k: seroval_decode(v) for k, v in node.get("s", {}).items()}
    return node


def tanstack_fn_call(base, fn_hash, data, content_type="application/json",
                     headers=None, timeout=20):
    """Call a TanStack Start server function with correct wire format.

    - application/json  -> body {"data": <plain json>}
    - application/x-seroval -> body {"data": <seroval node tree>}
    Returns the transport dict; parsed body in out["parsed"] when possible.
    """
    url = f"{base.rstrip('/')}/_serverFn/{fn_hash}"
    h = dict(headers or {})
    if content_type == "application/x-seroval":
        payload = {"data": seroval_encode(data)}
        body = json.dumps(payload)
    else:
        body = json.dumps({"data": data})
    h["Content-Type"] = content_type
    out = fetch(url, method="POST", headers=h, body=body, timeout=timeout, use_cache=False)
    parsed = None
    if out["status"] == 200 and out["body"]:
        try:
            j = json.loads(out["body"])
            parsed = seroval_decode(j) if isinstance(j, dict) and "t" in j else j
        except Exception:
            try:
                parsed = seroval_decode(json.loads(out["body"]))
            except Exception:
                parsed = None
    out["parsed"] = parsed
    return out
