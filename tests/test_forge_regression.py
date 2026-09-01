"""VOIDFORGE :: forge regression — the 'diag_import returns null' bug.
A full-module forge (leading imports + module-level def run) used to nest a
second def inside the template's run() and return None. Both forms must
forge, hot-load, and RETURN strings."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import execute
from tools.forge import forge_tool

_FULL = '''import json

def run(**kwargs):
    return json.dumps({"IMPORT-OK": True, "args": kwargs})
'''

_BODY = '''    r = json.dumps({"BODY-OK": True})
    return r
'''

NAMES = ("forged_zz_diag_full", "forged_zz_diag_body")


def _cleanup():
    for n in NAMES:
        p = os.path.join("tools", f"{n}.py")
        if os.path.exists(p):
            os.remove(p)
        for m in list(sys.modules):
            if m.startswith(n):
                del sys.modules[m]


def setup_function(fn):
    _cleanup()


def teardown_function(fn):
    _cleanup()


def test_full_module_form_with_leading_import():
    res = json.loads(forge_tool(name="zz_diag_full",
                                desc="regression: leading import form",
                                code=_FULL))
    assert res.get("ok"), res
    out = execute("forged_zz_diag_full", {"x": 1})
    assert "IMPORT-OK" in out, out[:300]
    d = json.loads(out.split("→ NEXT")[0].strip())
    assert d["IMPORT-OK"] is True and d["args"]["x"] == 1


def test_body_form_still_works():
    res = json.loads(forge_tool(name="zz_diag_body",
                                desc="regression: body form",
                                code=_BODY))
    assert res.get("ok"), res
    out = execute("forged_zz_diag_body", {})
    assert "BODY-OK" in out, out[:300]


def test_full_module_returns_string_not_none():
    # the historical bug: outer run() returned None (null in tool_result)
    json.loads(forge_tool(name="zz_diag_full", desc="d", code=_FULL))
    out = execute("forged_zz_diag_full", {})
    assert isinstance(out, str) and out.strip() and "null" != out.strip()
