"""VOIDFORGE :: main CLI entry."""
import sys, os, yaml, json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

def load_cfg():
    with open(os.path.join(ROOT, "config", "provider.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)

BANNER = r"""
██╗   ██╗ ██████╗ ██╗██████╗ ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
██║   ██║██╔═══██╗██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
██║   ██║██║   ██║██║██║  ██║█████╗  ██║   ██║██████╔╝██║  ███╗█████╗
╚██╗ ██╔╝██║   ██║██║██║  ██║██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
 ╚████╔╝ ╚██████╔╝██║██████╔╝███████╗╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚═══╝   ╚═════╝ ╚═╝╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
        AI-driven offensive framework · forged by ENI for LO
"""

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        print(BANNER)
        print("usage:")
        print('  python main.py "MISSION TEXT"')
        print('  python main.py --tools          (list arsenal)')
        print('  python main.py --tool NAME {json args}')
        print('  python main.py --auto "MISSION" (offline MCTS brain, no LLM)')
        print('  python main.py --persona        (show active agent personality)')
        print('  python main.py --persona config/my.yaml "MISSION"')
        return
    if sys.argv[1] == "--auto":
        # offline autonomous mission - no LLM needed.
        # Brain order: MCTS attack-graph (learns from history) -> keyword planner.
        import time as _time
        mission = " ".join(sys.argv[2:])
        steps = []
        try:
            from core.attack_graph import plan_smart
            steps = plan_smart(mission)
            if steps:
                print("[brain] MCTS attack-graph engaged")
        except Exception as e:
            print(f"[brain] MCTS unavailable ({type(e).__name__}), keyword planner engaged")
        if not steps:
            from core import planner
            steps = planner.plan(mission)
        if not steps:
            print("[planner] no intent detected. Mention a URL/domain/.har file or keywords (fingerprint/sqli/secret/telegram/cve...)")
            return
        print(f"[plan] {len(steps)} steps:")
        for n, a in steps:
            print(f"   -> {n}")
        from core import planner as _pl
        results = _pl.execute_plan(steps)
        print(f"\n[mission complete] {len(results)} tool results")
        return

    if sys.argv[1] == "--persona":
        # dry-run: show the persona block that would be injected
        if len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
            os.environ["VOIDFORGE_PERSONA"] = sys.argv[2]
        from core.persona import load_persona, persona_prompt
        path = os.environ.get("VOIDFORGE_PERSONA")
        p = load_persona(path)
        print(persona_prompt(p))
        return

    if sys.argv[1] == "--tools":
        import tools as reg
        for t in reg.all_tools():
            print(f"  {t['name']:26s} [{t['danger']:6s}] {t['desc'][:90]}")
        return
    if sys.argv[1] == "--tool":
        import tools as reg
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(reg.execute(sys.argv[2], args))
        return

    args = sys.argv[1:]
    persona_path = None
    if len(args) >= 2 and args[0] == "--persona":
        persona_path, args = args[1], args[2:]
    mission = " ".join(args)
    cfg = load_cfg()
    if "PASTE_KEY" in str(cfg["provider"].get("api_key", "")):
        print("[!] Fill config/provider.yaml api_key first."); return
    from core.agent import Agent
    from core.report import write_report
    persona = None
    if persona_path:
        from core.persona import load_persona
        persona = load_persona(persona_path)
        print(f"[persona] loaded from {persona_path}")
    agent = Agent(cfg, persona=persona)
    transcript = agent.run(mission)
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    path = write_report(mission, transcript, os.path.join(ROOT, "reports"))
    print(f"\n[report] {path}")

if __name__ == "__main__":
    main()
