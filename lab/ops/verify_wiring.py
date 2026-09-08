"""VOIDFORGE :: wiring proof — the new strike layer, verified live.
Run: python lab/verify_wiring.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools as reg
reg.discover()
from core import attack_graph as ag
from core.agent import SYSTEM
from core.swarm import SPECIALIST_ROLES
from core.planner import plan

NEW = ['race_smash', 'smuggle_probe', 'proto_pollute', 'xxe_probe',
       'redirect_cast', 'c2_pulse']
regd = {t['name']: t for t in reg.all_tools()}
print('arsenal total :', len(regd))
print()
hdr = f"{'outil':<16}{'registre':<10}{'schema':<9}{'MCTS':<7}{'doctrine':<10}{'swarm':<28}{'danger'}"
print(hdr)
print('-' * len(hdr))
for n in NEW:
    t = regd.get(n)
    print(f"{n:<16}"
          f"{'oui' if t else 'NON':<10}"
          f"{'oui' if t and t['params'].get('properties') else 'NON':<9}"
          f"{'oui' if n in ag.ACTIONS else 'NON':<7}"
          f"{'oui' if n in SYSTEM else 'NON':<10}"
          f"{','.join(r for r, sp in SPECIALIST_ROLES.items() if n in sp['tools']) or '-':<28}"
          f"{t['danger'] if t else '-'}")
print()
p = plan('race condition sur http://x.com/login puis smuggle et xxe xml sso redirect')
print('planner offline reconnait :', sorted(set(t for t, _ in p) & set(NEW)))
