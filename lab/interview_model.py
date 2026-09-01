"""VOIDFORGE :: model interview — the AI reviews its own arsenal.

The LLM is the only user who experiences the tools through LLM eyes, so she
is the best reviewer of whether the arsenal SPEAKS clearly to a model.
Three interviews: weaknesses, confusion audit, blind spots.
Run: python lab/interview_model.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLM
from core.agent import SYSTEM
import tools as reg

reg.discover()

def arsenal_catalog():
    lines = []
    for t in reg.all_tools():
        params = ", ".join(
            f"{k}:{v.get('type', '?')}" + ("" if k not in (t["params"].get("required") or []) else " (required)")
            for k, v in (t["params"].get("properties") or {}).items())
        lines.append(f"- {t['name']} [{t['danger']}] :: {t['desc']} | args: {params or 'none'}")
    return "\n".join(lines)

QUESTIONS = {
    "WEAKNESSES": """You are the operator intelligence of VOIDFORGE. Below is your doctrine and your full arsenal. Review it as a critical red-teamer reviewing HER OWN kit.
Answer with brutal specificity:
1. The 5 biggest weaknesses of this toolset — concrete mission scenarios where you would STALL with what exists.
2. The ONE tool you would add first, with its exact name and signature.
3. What in the doctrine is misleading, redundant, or missing?
Do not praise the kit. Attack it.""",

    "CONFUSIONS": """Same context (VOIDFORGE doctrine + arsenal below). Now a CONFUSION AUDIT of the interface between you and the tools:
1. Which tools look interchangeable — where would you plausibly call the wrong one?
2. Which descriptions or parameter names are ambiguous enough that you would GUESS an argument shape instead of knowing it?
3. Which tool would you hesitate to call because the schema does not tell you something you need (auth? return shape? units)?
Be concrete: name tool names and parameter names.""",

    "BLINDSPOTS": """Same context (VOIDFORGE doctrine + arsenal below). BLIND SPOT scan:
1. List attack classes against a web target for which you have NO tool at all and would have to improvise.
2. For each, say whether improvisation with existing tools is realistic or hopeless.
3. What would you type into a mission and fail to get, because the arsenal can't hear it?
Rank by how badly the gap hurts a real engagement.""",
}

def main():
    import time as _t
    import yaml
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                           "config", "provider.yaml"), encoding="utf-8"))
    p = cfg["provider"]
    llm = LLM(p["base_url"], p["api_key"], p["model"], 0.4)
    catalog = arsenal_catalog()
    context = (SYSTEM[:4500] + "\n\n═══ FULL ARSENAL (auto-generated from registry) ═══\n" + catalog)[:11000]
    out = {}
    for tag, q in QUESTIONS.items():
        msgs = [{"role": "system", "content": "You are the VOIDFORGE operator model doing a self-review of your own tooling. Be ruthless, specific, technical. No praise."},
                {"role": "user", "content": context + "\n\n═══ QUESTION ═══\n" + q}]
        answer = None
        for attempt, delay in enumerate((15, 30, 60, 90, 120), 1):
            resp = llm.chat(msgs)
            content = resp.get("content") or ""
            if not content.startswith("[LLM"):
                answer = content
                break
            print(f"  [{tag}] provider busy (attempt {attempt}): {content[:80]} — retry in {delay}s")
            _t.sleep(delay)
        out[tag] = answer or "(provider exhausted — rerun later)"
        print(f"\n{'═'*30} {tag} {'═'*30}\n{out[tag][:4500]}")
        _t.sleep(8)
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "reports", "model_self_review.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n[saved] {path}")

if __name__ == "__main__":
    main()
