# -*- coding: utf-8 -*-
"""K5 failover test: dead primary -> tokenrouter answers."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from core.llm import LLM

print("== 1. fleet composition ==")
llm = LLM("https://api.b.ai/v1", "sk-dead-test-key", "glm-5.3-flash")
print("   fleet:", [(u, m) for u, _, m in llm._fleet])
assert len(llm._fleet) == 2, "failover provider not mounted"
assert "tokenrouter" in llm._fleet[1][0]

print("== 2. dead primary -> failover answers ==")
r = llm.chat([{"role": "user", "content": "Reply with exactly: FAILOVER-OK"}],
             max_tokens=600)
print("   content:", repr(r.get("content"))[:80])
assert "FAILOVER-OK" in (r.get("content") or ""), r
assert llm._active_idx == 1, "active should memo the working provider"

print("== 3. memo: second call goes straight to the live one ==")
r2 = llm.chat([{"role": "user", "content": "Reply with exactly: MEMO-OK"}],
              max_tokens=600)
assert "MEMO-OK" in (r2.get("content") or ""), r2
print("   memo works:", repr(r2.get("content"))[:60])

print("\n[PASS] K5 FAILOVER — fleet rotation + memo, 3/3")
