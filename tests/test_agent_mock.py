"""VERIFICATION: agent loop end-to-end with a mock LLM (no API key needed).
Proves: mission -> model plans -> tool_calls parsed -> registry executes ->
results fed back -> final summary. The exact same code path runs with a real LLM."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MockLLM:
    """Simulates a model that calls one tool then writes a summary."""
    def __init__(self, *a, **k):
        self.step = 0
    def chat(self, messages, tools=None):
        self.step += 1
        if self.step == 1:
            return {"content": None, "tool_calls": [
                {"id": "call_1", "name": "web_fingerprint",
                 "args": {"url": "https://example.com"}}]}
        return {"content": "EXECUTIVE SUMMARY: fingerprint captured via tool chain. Loop verified.",
                "tool_calls": []}

# patch LLM into agent without touching agent.py logic
import core.agent as ca
ca.LLM = MockLLM

from core.agent import Agent
agent = Agent({"provider": {"base_url": "mock", "api_key": "mock",
                            "model": "mock", "max_tool_rounds": 5}})
transcript = agent.run("verify loop integrity on example.com")

assert any(k == "tool" for k, _ in transcript), "no tool executed!"
assert any("EXECUTIVE SUMMARY" in t for k, t in transcript if k == "agent"), "no summary!"
print("[PASS] mock agent loop: plan -> tool_call -> registry execute -> feedback -> summary")
print(f"[transcript steps] {len(transcript)}")
