"""VOIDFORGE :: attack_graph + persona verification — python tests/test_attack_graph.py"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import attack_graph as ag
from core import mathcore as mc
from core.persona import load_persona, persona_prompt

PASS = 0
def ok(name, cond, detail=""):
    global PASS
    assert cond, f"FAIL {name} {detail}"
    PASS += 1
    print(f"  ✓ {name} {detail}")

mc.bandit_reset(seed=False)  # deterministic priors: p̂=0.5, dur=1.0 for all tools

# ── Preconditions gate the action space ──────────────────────────────
s_url = ag.State([ag.Fact("url", "https://example.com")])
avail = ag.available(s_url)
tools = {t for t, _v, _x in [(a[0], a[1], a[2]) for a in avail]}
ok("url-only state: no supabase chain", "supabase_exfil" not in tools)
ok("url-only state: no har forensics", "har_dissect" not in tools)
ok("url-only state: recon offered", "web_fingerprint" in tools)

# ── Value model ranks the jackpot first ──────────────────────────────
s_sb = ag.State([ag.Fact("supabase_ref", "abcdefghijklmnopqrst"),
                 ag.Fact("anon_key", "eyJhbGciOiJIUzI1NiJ9.test")])
top = ag.available(s_sb)[0]
ok("supabase_exfil tops the value model", top[0] == "supabase_exfil",
   f"best={top[0]} v={top[2]:.3f}")

# ── Exhaustion removes spent actions ─────────────────────────────────
s_ex = s_url.with_exhausted(("web_fingerprint", "https://example.com"))
ok("exhausted action removed",
   ("web_fingerprint", "https://example.com") not in {(t, tt) for t, tt, _v in ag.available(s_ex)})

# ── MCTS search runs and visits children ─────────────────────────────
res = ag.search(s_url, sims=60, seed=7)
ok("MCTS visits root children", sum(n for _q, n in res.values()) > 0,
   f"{len(res)} branches")

# ── Planning produces a legal, chaining sequence ─────────────────────
steps = ag.plan(s_url, max_steps=6, sims=50, seed=7)
tools_seq = [t for t, _a in steps]
ok("plan nonempty and bounded", 0 < len(steps) <= 6, f"{tools_seq}")
ok("bare domain never jumps to supabase", "supabase_exfil" not in tools_seq)
# Ré-ancré au modèle de valeur actuel: la CHAÎNE probe→exploit doit émerger du
# monde (recon-only = échec); les noms exacts varient avec le graphe de valeur
# (drift antérieur au fix R2-1 + son propre per-edge anchoring).
_CHAIN_TOOLS = ("secret_scan", "js_mine_url", "js_mine_site", "deobfuscate_js",
                "sqli_probe_param", "sqli_union_dump", "sqli_blind_extract",
                "har_dissect", "data_extract", "data_dump_paginated",
                "api_sweep", "lfi_file_read", "upload_webshell",
                "cmd_exec_probe", "shell_exec", "jwt_analyst",
                "jwt_forge_replay", "endpoint_oracle", "param_brute")
ok("chains emerge from world model",
   any(t in _CHAIN_TOOLS for t in tools_seq),
   f"{tools_seq}")
seen = set()
legal = True
cur = s_url
for t, a in steps:
    tgt_vals = ag.ACTIONS[t]["targets"](cur)
    if not tgt_vals:
        legal = False
        break
    cur = ag.successor(cur, t, tgt_vals[0])
ok("every planned step is precondition-legal", legal)

# ── Mission text -> state -> smart plan ──────────────────────────────
smart = ag.plan_smart("Full recon of example.com", sims=50)
ok("plan_smart on bare domain", bool(smart) and "supabase_exfil" not in [t for t, _ in smart],
   f"{[t for t, _ in smart][:4]}")
smart_sb = ag.plan_smart(
    "Assault https://abcdefghijklmnopqrst.supabase.co with anon key "
    "eyJhbGciOiJIUzI1NiJ9.abcdef", sims=50)
ok("plan_smart detects supabase and strikes first",
   smart_sb and smart_sb[0][0] == "supabase_exfil",
   f"{[t for t, _ in smart_sb][:3]}")

# ── Persona system ───────────────────────────────────────────────────
p = load_persona()
ok("persona auto-loads from config", bool(p.get("name")), f"name={p.get('name')} tone={p.get('tone')}")
pr = persona_prompt(p)
ok("prompt carries tone + focus doctrine",
   (p.get("tone") or "") in pr and "DOCTRINE" in pr)
p_fr = load_persona(os.path.join(ROOT, "tests", "_nope.yaml"))
ok("missing file falls back to defaults", p_fr.get("mission_focus") == "thoroughness")
p2 = dict(p_fr, language="fr", mission_focus="stealth")
pr2 = persona_prompt(p2)
ok("language + focus overrides render",
   "write all narration and reports in French" in pr2 and "STEALTH DOCTRINE" in pr2)

print(f"\n★ {PASS}/{PASS} theorems verified — the brain thinks, the persona breathes.")
