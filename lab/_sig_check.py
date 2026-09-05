# -*- coding: utf-8 -*-
"""Validate hardened win-signature regexes against the REAL calib_A
transcript (the mission that originally minted these rules)."""
import json, re

lines = open('lab/calib_A/transcript.jsonl', encoding='utf-8').read().splitlines()
blob = ''
for l in lines[:600]:
    try:
        obj = json.loads(l)
        k, e = obj.get("kind", ""), obj.get("entry", "")
        if k == "error" or 'TOOL ERROR' in str(e)[:200]:
            continue
        blob += str(e)[:1500] + '\n'
    except Exception:
        pass
blob = blob[:400000]

SIGS = {
    'openapi': r'openapi[._-]?json.{0,120}?\\?"status\\?"\s*:\s*(200|403)',
    'admin':   r'X-Admin-Token.{0,200}?(path|line|match|match_no|hit)',
    'forge':   r'forge_tool.{0,60}?\\?"ok\\?"\s*:\s*true',
}
for nm, rx in SIGS.items():
    m = re.search(rx, blob, re.IGNORECASE | re.DOTALL)
    print(nm, '→', (m.group(0)[:100] if m else 'NO MATCH'))
