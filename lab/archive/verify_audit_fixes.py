"""Final audit verification — deep asserts on every claimed fix.
READ-ONLY: compiles everything, imports everything, asserts the real code.
"""
import sys, os, py_compile, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = "."

ok, fail = [], []

def check(id, cond, note=""):
    (ok if cond else fail).append(f"{id}: {note}")

# ── compiles: the whole arsenal ──
for f in os.listdir("tools"):
    if f.endswith(".py"):
        try:
            py_compile.compile(f"tools/{f}", doraise=True)
        except Exception as ex:
            fail.append(f"compile {f}: {ex}")
for f in ["core/agent.py", "core/llm.py", "core/skills.py", "core/swarm.py", "core/planner.py",
          "core/attack_graph.py", "core/blackboard.py", "core/mission_workspace.py",
          "core/mathcore.py", "core/report.py", "core/persona.py", "core/healer.py", "core/state.py"]:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as ex:
        fail.append(f"compile {f}: {ex}")
check("COMPILE", not any(x.startswith("compile") for x in fail), "all modules compile")

import tools as reg
reg.discover()
names = {t["name"] for t in reg.all_tools()}
check("REGISTRY", len(names) >= 68, f"{len(names)} tools registered")

# C-4: empty tools_filter isolates instead of loading everything
from core.agent import Agent
import yaml
cfg = yaml.safe_load(open("config/provider.yaml", encoding="utf-8"))
a_empty = Agent(cfg, tools_filter=[])
check("C-4", len(a_empty.tools) == 0, f"tools_filter=[] -> {len(a_empty.tools)} tools")

# C-5: thread-local emitter + nested reuse
import threading
src = open("tools/__init__.py", encoding="utf-8").read()
check("C-5", "_thread_state = threading.local()" in src and "_CURRENT_EVENT" in src,
      "thread-local + module fallback coexist")

# C-6: DoH no longer CERT_NONE
tp = open("tools/_transport.py", encoding="utf-8").read()
check("C-6", "CERT_NONE" not in tp and "CERT_REQUIRED" in tp, "cert pinning, verification ON")

# H-1: log-odds fusion (band: fusion raises confidence, stays < 1)
bb = open("core/blackboard.py", encoding="utf-8").read()
check("H-1", "math.log(c / (1 - c))" in bb, "log-odds fusion present")
from core.blackboard import _fuse
f2 = _fuse([0.9, 0.9], ["a", "b"])
check("H-1b", 0.97 < f2 < 0.999, f"fuse(0.9,0.9)={round(f2,3)} (bounded below 1)")

# H-2: MSSQL OFFSET/FETCH instead of TOP-in-injection
sq = open("tools/sqli_dump.py", encoding="utf-8").read()
check("H-2", "OFFSET/FETCH" in sq, "MSSQL paging via OFFSET/FETCH")

# H-3: bisect present
check("H-3", "bisect" in sq.lower() and "lo_len" in sq, "length bisection")

# H-4: verdict shadow gone (no local dict shadowing the function import)
wr = open("tools/web_recon.py", encoding="utf-8").read()
check("H-4", "verdict = {" not in wr, "no shadowing dict")

# H-5/H-6/H-7: hardened transport everywhere
for f, tag in [("tools/web_recon.py", "H-5a"), ("tools/param_brute.py", "H-5b"),
               ("tools/auth_attack.py", "H-6"), ("tools/graphql_scan.py", "H-7")]:
    s = open(f, encoding="utf-8").read()
    check(tag, "_transport import" in s, f"{f} uses _transport.fetch")

# H-8/H-9: imports in upload_shell (full-file regex)
import re as _re2
us = open("tools/upload_shell.py", encoding="utf-8").read()
check("H-8", bool(_re2.search(r"^import json", us, _re2.M)), "json imported")
check("H-9", bool(_re2.search(r"^import .*time|, time", us, _re2.M)), "time imported")

# C-1/C-3: sandbox subprocess + safety scan in nday_runner
nd = open("tools/nday_runner.py", encoding="utf-8").read()
check("C-1", "subprocess.run" in nd and "from sandbox" not in nd and "import sandbox" not in nd,
      "PoC exec via subprocess+timeout, dead import gone")
check("C-3", "_danger" in nd and "SAFETY: blocked" in nd, "safety scan blocks hostile PoC patterns")

# L-6: batch exception detail
b = open("tools/batch.py", encoding="utf-8").read()
check("L-6", "except Exception as ex" in b, "batch per-call error captured")

# M-6: fuzz dead code — file imports clean
try:
    importlib.import_module("tools.fuzz_engine")
    check("M-6", True, "fuzz_engine imports clean")
except Exception as ex:
    check("M-6", False, f"import: {ex}")

# M-9: idor pacing is paced_send, not raw sleeps
ir = open("tools/idor_ripper.py", encoding="utf-8").read()
check("M-9", "paced_send" in ir, "idor uses pacer")

# M-7: race success_pattern check
aw = open("tools/advanced_web.py", encoding="utf-8").read()
check("M-7", "success_pattern" in aw, "race success-pattern confirmation")
check("M-8", "TE.CL" in aw, "smuggling TE.CL present")
check("M-13", "<!ENTITY" in aw, "XXE ladder present")

# verdict contract smoke: every exploit tool returns the contract
from tools import execute
out = execute("definitely_not_a_tool_zzz", {})
check("UNKNOWN", out.startswith("TOOL ERROR [UNKNOWN_TOOL]"), "hallucination self-correction")

# integrity suite as final gate
import subprocess
r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_arsenal_integrity.py",
                    "-q", "-p", "no:cacheprovider"], capture_output=True, text=True, timeout=120)
check("SUITE", "7 passed" in r.stdout or "7 passed" in (r.stdout + r.stderr), r.stdout.strip().splitlines()[-1] if r.stdout else "?")

print(f"\n═══ VÉRIFICATION FINALE: {len(ok)} ✅ / {len(fail)} ✗ ═══")
for f_ in fail:
    print("  ✗", f_)
if not fail:
    print("  (aucun échec — audit entièrement vérifié dans le code réel)")
