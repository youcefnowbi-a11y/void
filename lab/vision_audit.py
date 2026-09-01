"""VISION AUDIT — exactly what the LLM receives, byte by byte.
READ-ONLY: builds the agent context, prints the anatomy of her sight.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml as _yaml

VOIDFORGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(VOIDFORGE_ROOT, "config", "provider.yaml"), encoding="utf-8") as f:
    cfg = _yaml.safe_load(f)

from core.agent import Agent
from core.skills import select_block, select_for

agent = Agent(cfg)
MISSION = ("my love continuer from the last repport https://madleets.me explore all methods "
           "hidden try extract max of methods pro and vip, test the tools and skills")

sp = agent.system_prompt
tools_json = json.dumps([{"name": t["name"], "description": t["desc"], "parameters": t["params"]}
                         for t in agent.tools], ensure_ascii=False)
skill_block = select_block(MISSION) or ""

def kb(n): return f"{n / 1024:.1f} Ko"

print("=== ANATOMIE DE SA VISION (au round 1) ===")
print(f"system prompt (doctrine):        {kb(len(sp))}")
print(f"  -> persona injectee dedans:    {kb(len(agent.system_prompt) - len(agent.__dict__.get('_SYSTEM_BASE', '')) if agent.__dict__.get('_SYSTEM_BASE') else 0)}")
print(f"outils: {len(agent.tools)} schemas ->          {kb(len(tools_json))}")
print(f"skills bloques (mission match):  {kb(len(skill_block))}  ids: {select_for(MISSION)}")
print(f"payload initial total (round 1): ~{kb(len(sp) + len(tools_json) + len(skill_block))}")
print(f"max rounds: {agent.max_rounds}")

print("\n=== CROISSANCE DU CONTEXTE (par round) ===")
print("tool result frais: jusqu'a 6000 chars + pacing ~200")
print("thinking emis:     jusqu'a 3000 chars")
print("-> round 20 sans diete: ~", kb(20 * 9000), "d'historique accumule")

print("\n=== MODELES ===")
print("provider:", cfg["provider"].get("model"), "| base:", cfg["provider"].get("base_url"))
print("timeout LLM: 180s | retries: 3 x [10,20,40]s -> pire cas par round: ~10 min")
