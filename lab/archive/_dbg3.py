# -*- coding: utf-8 -*-
import json, sys
sys.path.insert(0, '.')
from tools.forge import forge_tool
code = """    domain = (domain or '').strip()
    if not domain:
        return json.dumps({'error': 'no domain'})
    return json.dumps({'domain': domain, 'fake_ip': '203.0.113.7'})"""
r = forge_tool(name='probe_resolver', desc='t', code=code,
               params={'type': 'object', 'properties': {'domain': {'type': 'string'}},
                       'required': ['domain']})
print("RESULT:", r)
import os
p = os.path.join('tools', 'forged_probe_resolver.py')
if os.path.exists(p):
    print("--- module ---")
    print(open(p, encoding='utf-8').read())
