"""Liste l'arsenal complet — le LLM doit savoir ce qui existe."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import all_tools, discover
discover()
ts = all_tools()
print(len(ts), "tools")
for t in sorted(ts, key=lambda x: x["name"]):
    d = t.get("desc", "")[:110]
    print(f"{t['name']} · {t.get('danger','safe')} · {d}")
