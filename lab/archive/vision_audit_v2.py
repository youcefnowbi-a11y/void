"""VISION AUDIT v2 — does the LLM see EVERYTHING? tools + skills + engines.
READ-ONLY: builds the agent context, counts what she actually receives.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml

with open("config/provider.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

from core.agent import Agent
import core.skills as skills_mod
select_block, select_for = skills_mod.select_block, skills_mod.select_for
SKILLS = getattr(skills_mod, "SKILLS", getattr(skills_mod, "_SKILLS", {}))

MISSION = ("heavy attack and full exploitation of https://madleets.me — zero-days if needed, "
           "framework flaws, memory corruption on parsers, auth flow bugs, extract everything")

agent = Agent(cfg)
sp = agent.system_prompt
tools_json = json.dumps([{"name": t["name"], "desc": t["desc"], "params": t["params"]}
                         for t in agent.tools], ensure_ascii=False)
skill_block = select_block(MISSION) or ""

def kb(n): return f"{n / 1024:.1f} Ko"

print("=== ANATOMIE DE SA VISION (audit v2) ===")
print(f"outils enregistrés : {len(agent.tools)}")
print(f"  schemas d'outils ->    {kb(len(tools_json))}")
print(f"skills pack : {len(SKILLS)} chargés ; match mission -> {select_for(MISSION)}")
print(f"  bloc skills ->         {kb(len(skill_block))}")
names = sorted(t['name'] for t in agent.tools)
print(f"\nouleurs-clés présents : batch={ 'batch_execute' in names}, "
      f"nday={'nday_exploit' in names}, auth_state={'auth_state_audit' in names}")
zero_day = [n for n in names if n in (
    "nday_exploit", "sqli_dump", "ssti_rce", "cmd_inject", "auth_state_audit",
    "jwt_forge", "race_smash", "smuggle_probe", "xxe_probe", "lfi_read")]
print(f"arsenal 0day/exploit visible : {len(zero_day)} -> {zero_day}")

print(f"\nsystem prompt : {kb(len(sp))}")
print(f"payload round-1 total : ~{kb(len(sp) + len(tools_json) + len(skill_block))}")
print(f"max rounds : {agent.max_rounds}")

# research engines NOT yet bridged — the honest gap
have = {"auth_state_audit"}
research = [f for f in os.listdir("research") if f.endswith(".py")]
unbridged = [f for f in research
             if os.path.basename(f).replace(".py", "") not in {h.replace("auth_state_", "") for h in have}
             and f not in ("auth_state_engine_v0.py",)]
print(f"\nmoteurs research/ non-bridgés en outils : {unbridged or 'aucun'}")
