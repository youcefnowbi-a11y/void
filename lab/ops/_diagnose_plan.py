# -*- coding: utf-8 -*-
"""Diagnose why plan_doc extraction failed in campaign CP1."""
import sys, io, json
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# replay: what did the final assistant messages look like? we can't rerun
# the LLM — but we CAN check the mechanism. The events.jsonl carries the
# content of each agent_thinking. Read it and find the ATTACK PLAN message.
found = []
with io.open("lab/camp_CP1/events.jsonl", encoding="utf-8", errors="replace") as f:
    for line in f:
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "agent_thinking" and "ATTACK PLAN" in str(e.get("content", "")):
            found.append((e.get("_t"), e["content"][:150]))

print("events with ATTACK PLAN:", len(found))
for t, c in found:
    print(f"[{t}s]", c)

# so the content IS there in agent_thinking events. The campaign extracted
# from the returned transcript — let me reproduce the extraction logic:
# plan_doc = next((t for k, t in reversed(transcript) if k == "assistant" and
#                  ("ATTACK PLAN" in str(t) or '"chains"' in str(t))), None)
# KEY QUESTION: does run() append ("assistant", content) to transcript?
# From agent.py line 2072-2073: transcript.append(("agent", content)) — NOT "assistant"!
print()
print("ROOT cause: transcript tuples are ('agent', content), not ('assistant', content)")
print("The campaign searched k == 'assistant' — the kind is 'agent'")
