# -*- coding: utf-8 -*-
"""Latency diagnosis: where do the seconds go on a simple 'hi'?

Measures three calls against the LIVE provider:
  A. tiny system, no tools          -> provider floor (network + model TTFT)
  B. full VOIDFORGE system, no tools -> cost of the 47K context
  C. full VOIDFORGE system + tools   -> cost of the tool schemas (what /chat does)
Each call prints elapsed seconds and response length.
"""
import sys, os, time, json
sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from core.llm import LLM

cfg = yaml.safe_load(open('config/provider.yaml', encoding='utf-8'))
p = cfg['provider']
llm = LLM(p['base_url'], p['api_key'], p['model'], p.get('temperature', 0.3))

from core.chat import CHAT_SYSTEM, _CATALOG_HEADER, CHAT_TAIL, _catalog
try:
    from core.persona import persona_prompt, load_persona
    pp = persona_prompt(load_persona())
except Exception:
    pp = ''
FULL = CHAT_SYSTEM + '\n\n' + pp.strip() + '\n' + _CATALOG_HEADER + _catalog() + CHAT_TAIL
tiny = "You are a helpful assistant. Reply in one short sentence."

def run(label, system, tools=None):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": "hi"}]
    t0 = time.time()
    resp = llm.chat(msgs, tools=tools)
    dt = time.time() - t0
    content = (resp.get('content') or '')[:60].replace('\n', ' ')
    tcs = resp.get('tool_calls') or []
    print(f"{label}: {dt:6.2f}s | system {len(system):>6,} chars | reply {len(content)} chars | tool_calls {len(tcs)}")
    print(f"   reply: {content}")

run("A tiny   ", tiny)
run("B full   ", FULL)
specs = [{"name": "web_search", "desc": "web search", "params": {"type": "object", "properties": {"query": {"type": "string"}}}},
         {"name": "web_read", "desc": "read page", "params": {"type": "object", "properties": {"url": {"type": "string"}}}}]
run("C tools  ", FULL, tools=specs)
