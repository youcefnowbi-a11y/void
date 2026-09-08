"""VOIDFORGE :: compact model interview — one call, all three questions.
Built for congested providers: minimal context, single round-trip.
Run: python lab/interview_compact.py
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLM
import tools as reg
import yaml

reg.discover()

def compact_catalog():
    lines = []
    for t in reg.all_tools():
        d = t["desc"][:100].replace("\n", " ")
        req = ",".join(t["params"].get("required") or [])
        lines.append(f"- {t['name']}[{t['danger']}]({req}): {d}")
    return "\n".join(lines)

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = yaml.safe_load(open(os.path.join(root, "config", "provider.yaml"), encoding="utf-8"))
    p = cfg["provider"]
    llm = LLM(p["base_url"], p["api_key"], p["model"], 0.4)

    doctrine_digest = (
        "VOIDFORGE: AI-driven offensive framework. Doctrine: recon chains (fingerprint -> "
        "waf -> js_mine -> subdomains -> endpoint_oracle -> secret_scan). STRIKE LAW: detection "
        "tools are SCOUTS; a confirmed vuln must be exploited. Strike chains: SQLi confirmed -> "
        "sqli_union_dump -> sqli_blind_extract; suspected cmd inject -> cmd_exec_probe -> shell_exec "
        "-> upload_webshell -> shell_session; SSTI -> ssti_detect_rce; LFI -> lfi_file_read; JWT -> "
        "jwt_analyst -> jwt_forge_replay; sequential/b64 ids -> idor_enum/idor_b64_walk; upload -> "
        "upload_webshell; fuzz findings -> crash_triage_next -> mapped strike tool; CVE matches -> "
        "nday_exploit. BaaS: supabase_exfil preferred. Data: data_extract/api_sweep/data_dump_paginated. "
        "Intel: nvd_search/cisa_kev. Telegram: tg_probe/tg_history_harvest/etc. Orchestration: "
        "batch_execute (5 parallel calls). Offline brain: MCTS over fact/state model.\n\nFULL ARSENAL:\n"
        + compact_catalog())

    question = """You are the operator model of this framework. Self-review your kit in three parts, brutal and specific:

A) WEAKNESSES: the 5 biggest gaps — concrete mission scenarios where you would STALL. The ONE tool you would add first (name + signature). Anything misleading in the doctrine.

B) CONFUSIONS: tools that look interchangeable (where you might call the wrong one); parameter names/descriptions too ambiguous to guess argument shapes; anything you'd hesitate to call.

C) BLIND SPOTS: attack classes with NO tool at all; for each, is improvising with existing tools realistic or hopeless; what mission text would fail to be understood.

No praise. Name tools and parameters explicitly."""

    msgs = [{"role": "system", "content": "You are VOIDFORGE's operator model reviewing your own toolset. Ruthless, specific, technical, zero praise."},
            {"role": "user", "content": doctrine_digest + "\n\n" + question}]

    answer = None
    for attempt, delay in enumerate((20, 45, 75), 1):
        resp = llm.chat(msgs)
        content = resp.get("content") or ""
        if not content.startswith("[LLM"):
            answer = content
            break
        print(f"  provider busy (attempt {attempt}): {content[:90]} — retry in {delay}s", flush=True)
        time.sleep(delay)

    if answer:
        print("\n═══ MODEL SELF-REVIEW ═══\n")
        print(answer[:7000])
        with open(os.path.join(root, "reports", "model_self_review_compact.json"), "w", encoding="utf-8") as f:
            json.dump({"review": answer}, f, ensure_ascii=False, indent=1)
        print("\n[saved] reports/model_self_review_compact.json")
    else:
        print("PROVIDER EXHAUSTED — background long-ladder interview (pwsh-16) still pending.")

if __name__ == "__main__":
    main()
