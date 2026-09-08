# -*- coding: utf-8 -*-
"""Smoke-test campaign wiring without firing."""
import sys, io
sys.path.insert(0, ".")
from core.swarm import PlannedSwarm, parse_plan_json, VERIFIER_PROMPT
from core.agent import Agent
import yaml

cfg = yaml.safe_load(io.open("config/provider.yaml", encoding="utf-8"))
plan = ('# ATTACK PLAN — test\n'
        '```json\n'
        '{"chains": [{"name": "recon-map", "priority": "HIGH", "target": "example.com", '
        '"subagent": "recon", "tools": ["web_fingerprint"], "rounds": 6}], '
        '"mode": "swarm", "max_subagents": 2}\n'
        '```')
p = parse_plan_json(plan)
print("plan json parsed:", len(p.get("chains", [])), "chain(s)")
sw = PlannedSwarm(cfg, plan)
print("planned swarm built: chains", len(sw.chains), "max_sub", sw.max_subagents)
print("Agent plan_mode tools:", len(Agent(cfg, plan_mode=True).tools), "(recon-only set)")
print("VERIFIER_PROMPT len:", len(VERIFIER_PROMPT))
print("WIRING OK")
