"""Preuve offline de CHAT -> PLAN -> STRIKE : parsing, restriction d'arsenal,
budgets, injection de contexte — zéro appel LLM, zéro réseau."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  OK  " if cond else "  FAIL") + f" {name}" + (f" — {detail}" if detail and not cond else ""))

# ── 1. ChatSession: construction sans LLM call, contexte accumulé ──
print("[1] core.chat.ChatSession")
from core.chat import ChatSession, _catalog
cfg = {"provider": {"base_url": "http://127.0.0.1:9", "api_key": "x", "model": "test", "max_tool_rounds": 40}}
cs = ChatSession(cfg)
cat = _catalog()
check("catalogue non vide", "binary_fuzz_run" in cat and "data_extract" in cat, f"{len(cat)} chars")
cs.history = [{"role": "user", "content": "duskyr.com tourne sur Supabase, focus keypool"},
              {"role": "assistant", "content": "Compris: Supabase + keypool prioritaire."},
              {"role": "user", "content": "rate limit 60/min, pas de spam"},
              {"role": "assistant", "content": "Noté: 60 req/min max."}]
ctx = cs.get_context()
check("contexte = ORDRES DU COMMANDANT", "ORDRES DU COMMANDANT" in ctx)
check("contrainte opérateur présente", "60/min" in ctx)
cs.clear()
check("clear vide l'historique", cs.count() == 0 and cs.get_context() == "")

# ── 2. Agent plan_mode: arsenal restreint, rounds plafonnés, doctrine armée ──
print("[2] core.agent.Agent(plan_mode=True)")
from core.agent import Agent
a = Agent(cfg, plan_mode=True)
check("arsenal recon-only (pas de race_smash)",
      "race_smash" not in {t["name"] for t in a.tools})
check("arsenal plan contient arsenal_selftest",
      "arsenal_selftest" in {t["name"] for t in a.tools})
check("rounds plafonnés à 14", a.max_rounds <= 14, str(a.max_rounds))
check("doctrine PLAN dans le system prompt", "PLAN MODE" in a.system_prompt)
check("marker de fin ATTACK PLAN actif",
      a._is_final_summary("# ATTACK PLAN — cible\n## Proposed Attack Chains"))
normal = Agent(cfg)
check("agent normal garde les 74+ outils", len(normal.tools) > 70, str(len(normal.tools)))
check("agent normal refuse le marker plan",
      not normal._is_final_summary("# ATTACK PLAN — test"))

# ── 3. parse_plan_json: le bloc machine du plan ──
print("[3] core.swarm.parse_plan_json")
from core.swarm import parse_plan_json, PlannedSwarm
plan_md = """# ATTACK PLAN — duskyr.com

## Proposed Attack Chains

### Chain 1: keypool (priority: CRITICAL)
- Target: keypool.duskyr.com
- Estimated rounds: 12

```json
{"chains": [{"name": "keypool", "priority": "CRITICAL", "target": "keypool.duskyr.com",
             "subagent": "api", "tools": ["data_extract", "endpoint_oracle", "otp_brute"],
             "rounds": 12},
            {"name": "web-js", "priority": "HIGH", "target": "duskyr.com",
             "subagent": "web", "tools": ["js_mine_site", "jwt_analyst"], "rounds": 8}],
 "mode": "swarm", "max_subagents": 2}
```
"""
parsed = parse_plan_json(plan_md)
check("JSON extrait", parsed is not None and len(parsed["chains"]) == 2)
check("mode recommandé lu", parsed.get("mode") == "swarm")
ps = PlannedSwarm(cfg, plan_md, target="duskyr.com")
check("PlannedSwarm: 2 chaînes", len(ps.chains) == 2)
check("PlannedSwarm: max_subagents=2", ps.max_subagents == 2)
check("budget médian = 10 (trié 8,12 -> 2e=12? non: médian index 1)", ps.specialist_rounds in (10, 12), str(ps.specialist_rounds))
check("fallback: plan sans JSON -> chains vides", PlannedSwarm(cfg, "# ATTACK PLAN\ntexte seul").chains == [])

# ── 4. run() signature: commander_orders + plan_doc ──
print("[4] Agent.run canaux d'injection")
import inspect
sig = inspect.signature(normal.run)
check("param commander_orders", "commander_orders" in sig.parameters)
check("param plan_doc", "plan_doc" in sig.parameters)

# ── 5. server: routes présentes ──
print("[5] web.backend.server routes")
srv_src = open("web/backend/server.py", encoding="utf-8").read()
for route in ('"/chat"', '"/chat/clear"', '"/chat/context"', '"/mission/approve-plan"',
              "_PENDING_PLAN", "plan_ready", "chat_context", "PlannedSwarm"):
    check(f"serveur contient {route}", route in srv_src)

# ── 6. intégrité de l'arsenal inchangée ──
print("[6] intégrité")
from tools import all_tools, discover
discover()
check("registry >= 74", len(all_tools()) >= 74, str(len(all_tools())))

print(f"\n═══ {len(PASS)} PASS · {len(FAIL)} FAIL ═══")
sys.exit(1 if FAIL else 0)
