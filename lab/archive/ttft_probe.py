# -*- coding: utf-8 -*-
"""TTFT probe: time-to-first-token with the full VOIDFORGE context.
This is what the operator PERCEIVES with streaming active."""
import sys, os, time
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

first = [None]
n_deltas = [0]
def cb(piece):
    if first[0] is None:
        first[0] = time.time()
    n_deltas[0] += 1

t0 = time.time()
resp = llm.chat_stream(
    [{"role": "system", "content": FULL},
     {"role": "user", "content": "salut, ça va ?"}],
    max_tokens=1600, on_delta=cb)
total = time.time() - t0
ttft = (first[0] - t0) if first[0] else None
content = resp.get('content') or ''
print(f"TTFT (premier mot)   : {ttft:6.2f}s" if ttft else "TTFT: AUCUN STREAM (fallback bloquant)")
print(f"total                : {total:6.2f}s")
print(f"deltas reçus         : {n_deltas[0]}")
print(f"longueur réponse     : {len(content)} chars")
