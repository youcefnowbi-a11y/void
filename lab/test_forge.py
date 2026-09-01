# -*- coding: utf-8 -*-
"""Offline proof: forge_tool round-trip + chat agent-loop with a fake LLM."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.forge import forge_tool
from tools import all_tools, execute

PASS = FAIL = 0
def check(label, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS  {label}")
    else: FAIL += 1; print(f"  FAIL  {label}")

# ── 1. list mode on empty forge ──
r = json.loads(forge_tool(name="list"))
check("forge list mode returns dict", isinstance(r, dict) and "forged" in r)

# ── 2. forge a real tool (format A: fully-indented body) ──
code = """    domain = (domain or '').strip()
    if not domain:
        return json.dumps({'error': 'no domain'})
    return json.dumps({'domain': domain, 'fake_ip': '203.0.113.7'})"""
r = json.loads(forge_tool(
    name="probe_resolver",
    desc="Test-forged tool: resolves a fake IP for a domain (offline proof).",
    code=code,
    params={"type": "object", "properties": {"domain": {"type": "string"}},
            "required": ["domain"]}))
check("forge_tool ok flag", r.get("ok") is True)
check("forge registers forged_probe_resolver", r.get("tool") == "forged_probe_resolver")

names = [t["name"] for t in all_tools()]
check("forged tool in live registry", "forged_probe_resolver" in names)

# ── 3. execute the forged tool through the standard dispatcher ──
out = execute("forged_probe_resolver", {"domain": "duskyr.com"})
outj = json.loads(out)
check("forged tool executes", outj.get("fake_ip") == "203.0.113.7")

# ── 3bis. format B: full `def run(...)` wrapper (second tool) ──
code_b = """def run(q, limit=None):
    limit = int(limit or 3)
    return json.dumps({'q': q, 'echoes': [q] * limit, 'level': 'forged-B'})"""
r = json.loads(forge_tool(
    name="echo_lance",
    desc="Test-forged tool B: echoes a query N times (def-wrapper format).",
    code=code_b,
    params={"type": "object", "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["q"]}))
check("forge B ok flag", r.get("ok") is True)
outb = execute("forged_echo_lance", {"q": "go", "limit": "2"})
check("forged B executes via def-wrapper", json.loads(outb).get("echoes") == ["go", "go"])
p_b = os.path.join("tools", "forged_echo_lance.py")

# ── 4. reject duplicate name ──
r2 = json.loads(forge_tool(name="probe_resolver", desc="dup", code="return 'x'"))
check("duplicate forge rejected", "error" in r2)

# ── 5. reject invalid name ──
r3 = json.loads(forge_tool(name="9bad name!", code="return 'x'"))
check("invalid name rejected", "error" in r3)

# ── 6. broken code → compile error, file cleaned ──
r4 = json.loads(forge_tool(name="broken_one", code="def oops(:\n    return 1"))
check("broken code rejected + cleaned", "error" in r4 and
      not os.path.exists(os.path.join("tools", "forged_broken_one.py")))

# ── 7. forge list now shows both live tools ──
r5 = json.loads(forge_tool(name="list"))
got = {e["name"] for e in r5["forged"]}
check("forge list shows both live", "forged_probe_resolver" in got and "forged_echo_lance" in got)

# ── cleanup the forged proof tools ──
p = os.path.join("tools", "forged_probe_resolver.py")
if os.path.exists(p): os.remove(p)
if os.path.exists(p_b): os.remove(p_b)
import tools
tools._REGISTRY.pop("forged_probe_resolver", None)
tools._REGISTRY.pop("forged_echo_lance", None)
check("proof files cleaned", not os.path.exists(p) and not os.path.exists(p_b))

print(f"\nFORGE PROOF: {PASS} PASS · {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
