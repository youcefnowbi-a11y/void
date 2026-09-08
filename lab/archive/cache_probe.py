# -*- coding: utf-8 -*-
"""Cache probe: same full-context call TWICE — if call 2 is fast, the provider
prefix-caches; if identical-slow, there is no caching and context cost is paid
on every single message."""
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

for i in (1, 2, 3):
    msgs = [{"role": "system", "content": FULL},
            {"role": "user", "content": "réponds juste: ok"}]
    t0 = time.time()
    llm.chat(msgs)
    print(f"call {i}: {time.time()-t0:6.2f}s")
