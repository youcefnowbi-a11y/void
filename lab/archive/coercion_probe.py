"""Coercion probe: stringified LLM args must survive registry dispatch."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import _coerce_args

schema = {"concurrency": {"type": "integer"}, "headers": {"type": "object"},
          "body": {"type": "object"}, "deep": {"type": "boolean"},
          "ratio": {"type": "number"}}
a = {"concurrency": "20", "headers": "{\"x\": 1}", "body": "{}",
     "deep": "true", "ratio": "0.85", "keep": "untouched-string"}
_coerce_args(schema, a)
assert a["concurrency"] == 20, a
assert a["headers"] == {"x": 1}, a
assert a["body"] == {}, a
assert a["deep"] is True, a
assert a["ratio"] == 0.85, a
assert a["keep"] == "untouched-string", a
print("coercion: 6/6 OK ->", a)
