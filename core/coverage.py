"""VOIDFORGE :: Tier F — the depth driver (coverage orders + discovery signal).

Mission 76 autopsy: 78 rounds, ~40% of them session-token re-mints, the
EXPLOIT bench nearly cold (3 tool kinds) and the POST bench untouched —
while EVERY anti-stagnation mechanism in the loop measured EXECUTION
("tool ran ok"). None measured COVERAGE (which bench got touched) or
DISCOVERY (whether the run actually FOUND something). Goodhart did the
rest: she optimized exactly the metric we fed her.

This module adds the two missing metrics as pure, testable functions:

  1. COVERAGE ORDERS — every COVERAGE_PERIOD rounds the run loop counts
     her strikes per bench (tools._phases.PHASE_MAP) and any cold watched
     bench earns a hard USER-message order naming concrete untried tools.
     Each ignored order escalates the order (level 3+ carries REAL target
     URLs scraped from her own tool results — the offline brain's aim).
  2. DISCOVERY SIGNAL — regex verdict over a tool result: did this run
     find something (exploitable verdict, non-empty record_count, crash,
     vulnerable marker)? The bandit's reward becomes discovery-aware.

Pure stdlib, no imports from core.agent — the run loop calls in.
"""
import json
import re
from collections import Counter

COVERAGE_PERIOD = 6          # rounds between coverage audits
IGNORED_ESCALATION = 3       # ignored orders before targets are named

# watched benches: the strike lanes. recon/surface/adapt run themselves
# hungry; exploit and post-exploit are the lanes that die of politeness.
_WATCHED = ("exploit", "post-exploit")

# curated strike ladders per cold bench — most universal first. Filtered
# against the live registry before showing (nothing phantom is offered).
_EXPLOIT_LADDER = (
    "idor_enum", "jwt_forge_replay", "sqli_probe_param", "ssrf_probe",
    "proto_pollute", "smuggle_probe", "xxe_probe", "race_smash",
    "h2_race_attack", "otp_brute", "ssti_detect_rce", "cmd_exec_probe",
    "lfi_file_read", "redirect_cast", "auth_state_audit", "nday_exploit",
)
_POST_LADDER = (
    "privesc_enum", "c2_pulse", "deploy_watch",
    "crash_triage_rank", "crash_triage_next",
)
_LADDERS = {"exploit": _EXPLOIT_LADDER, "post-exploit": _POST_LADDER}

_BENCH_LABEL = {
    "exploit": "EXPLOIT",
    "post-exploit": "POST-EXPLOIT (C2 / persistence / privesc)",
}

# ── F5: discovery signal ────────────────────────────────────────────
_DISCOVERY_RX = re.compile(
    r'"exploitable"\s*:\s*(true|"partial"|partial)'      # fuzz/race/forge verdicts
    r'|"record_count"\s*:\s*([1-9]\d*)'                  # pulled records
    r'|"crashed"\s*:\s*true'                             # live fuzz crash
    r'|"vulnerable"\s*:\s*true'                          # probe verdicts
    r'|"verdict"\s*:\s*"(exploitable|vulnerable|confirmed)'  # oracle verdicts
    r'|"exploit_confirmed"\s*:\s*true',
    re.I,
)


def discovery_signal(out):
    """True when a tool result shows the run actually FOUND something."""
    if not out:
        return False
    return bool(_DISCOVERY_RX.search(str(out)))


_HONEST_NEG_RX = re.compile(
    r'"exploitable"\s*:\s*false'
    r'|"verdict"\s*:\s*"(clean|safe|blocked|not_vulnerable|missing)"'
    r'|all variants rejected'
    r'|"challenge_status"\s*:\s*40[23]',
    re.I,
)


def reward_signal(out):
    """Bandit reward: a DISCOVERY or an explicit structured negative verdict.
    A bare successful fetch (token mint, plain 200 scrape) no longer earns
    credit — the bandit must learn that FINDING something (or honestly
    closing a lane) is the game, not mere survival of the call.
    wave-2-B fix #6: refusal tails (TOOL ERROR) never earn either —
    the old regex could match text INSIDE an error tail."""
    if not out:
        return False
    s = str(out)
    if s.startswith(("TOOL ERROR", "TOOL DEFERRED")):
        return False
    if discovery_signal(out):
        return True
    tail = s[:400] if "[_healed:" not in s else s.split("[_healed:")[0][:400]
    return bool(_HONEST_NEG_RX.search(tail))


# ── F1: coverage accounting ─────────────────────────────────────────
def bench_counts(tool_names):
    """Histogram of bench usage from executed tool names."""
    from tools._phases import phase_for
    return Counter(phase_for(n) for n in tool_names)


def cold_benches(tool_names):
    """Watched benches with zero strikes so far."""
    c = bench_counts(tool_names)
    return [b for b in _WATCHED if c.get(b, 0) == 0]


def _untried_from_ladder(tool_names, bench, available):
    """Curated ladder for a bench, minus already-run, minus not-installed."""
    used = set(tool_names)
    return [t for t in _LADDERS.get(bench, ()) if t not in used and t in available]


def coverage_message(round_no, tool_names, total_rounds_label, available,
                     ignored=0, target_urls=()):
    """The COVERAGE ORDER user-message — or '' when nothing is cold.

    level = ignored+1 drives escalation: level 1-2 name untried tools,
    level 3+ (three ignored orders) also aim her at URLs she herself
    harvested and warn of offline-brain takeover."""
    cold = cold_benches(tool_names)
    if not cold:
        return ""
    lines = [f"[⚠ COVERAGE ORDER — round {round_no}/{total_rounds_label}]",
             "PHASE GUIDE audit: your strike coverage is LOPSIDED."]
    for b in cold:
        n = len(_untried_from_ladder(tool_names, b, available))
        label = _BENCH_LABEL[b]
        if n:
            tools_txt = ", ".join(_untried_from_ladder(tool_names, b, available)[:6])
            lines.append(f"- Bench {label}: COLD (0 strikes, {n} untried weapons). "
                         f"Fire one NOW: {tools_txt}.")
        else:
            lines.append(f"- Bench {label}: COLD (0 strikes). Justify in one line "
                         f"why this bench is impossible on this target, or fire it.")
    level = ignored + 1
    if level >= IGNORED_ESCALATION:
        lines.append(f"- {ignored} coverage orders IGNORED. Next ignored order = "
                     f"the offline brain picks your strike targets for you.")
        real = [u for u in target_urls if u][:5]
        if real:
            lines.append("- Real targets from YOUR OWN results: " +
                         " | ".join(real))
    lines.append("A cold bench without a written justification = mission incomplète.")
    return "\n".join(lines)


_URL_RX = re.compile(r"https?://[^\s\"'<>\\)]+")

# ── W2: honest ledger status ────────────────────────────────────────
_FAIL_EXIT_RX = re.compile(r"\bexit=([1-9]\d*)\b")
_OK_FALSE_RX = re.compile(r'"ok"\s*:\s*false')


def honest_status(out):
    """W2 (mission-76 autopsy): the ledger must not call a failed run a
    success. auth_state_audit died on 'exit=2 [stderr] target /health
    failed' and the ledger recorded [ok]; forged_siwx_signer returned
    {'ok': false, 'errors': [missing modules]} — also [ok]. Both are
    failures. Honest NEGATIVES (an 'exploitable': false verdict) stay
    'ok': closing a lane with evidence is work, not an error.
    wave-2-B fix #1 (HIGH): 'TOOL DEFERRED' (an Ω1 slot-defer that never
    EXECUTED) used to pass as 'ok' — never-executed defers were banked
    as successful detections into tool_runs, the bandit, trajectory and
    twin ranks. A defer is neither success nor failure: 'deferred'."""
    s = str(out or "")
    if s.startswith("TOOL ERROR"):
        return "error"
    if s.startswith("TOOL DEFERRED"):
        return "deferred"
    if _FAIL_EXIT_RX.search(s) and "[stderr]" in s:
        return "error"
    if _OK_FALSE_RX.search(s[:400]):
        return "error"
    return "ok"


def harvest_targets(out, limit=5):
    """Scrape plausible strike URLs from a tool result (her own recon)."""
    if not out:
        return []
    seen, urls = set(), []
    for u in _URL_RX.findall(str(out)):
        u = u.rstrip(".,;)")
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
        if len(urls) >= limit:
            break
    return urls


def strike_proposal(tool_names, available, targets):
    """Offline-brain strike brief: first cold bench -> first untried curated
    weapon -> args derived from the tested attack-graph ACTIONS against a
    real harvested URL. Returns {"bench","tool","args","target"} or None.
    This is the payload behind the escalation order — the threat is real."""
    if not targets:
        return None
    try:
        from core.attack_graph import ACTIONS
    except Exception:
        return None
    for bench in _WATCHED:
        untried = _untried_from_ladder(tool_names, bench, available)
        if not untried:
            continue
        tool = untried[0]
        spec = ACTIONS.get(tool)
        if not spec:
            continue
        for tgt in targets[:6]:
            try:
                args = spec["args"](tgt)
            except Exception:
                continue
            if not args:
                continue
            return {"bench": bench, "tool": tool, "args": args, "target": tgt}
        return {"bench": bench, "tool": tool, "args": None, "target": None}
    return None


def proposal_text(proposal):
    """Human/LLM line for the escalation order."""
    if not proposal:
        return ""
    tool, args = proposal["tool"], proposal["args"]
    if args:
        return (f"- OFFLINE STRIKE PROPOSAL (execute NOW, then re-audit): "
                f"{tool} with args {json.dumps(args, ensure_ascii=False)} "
                f"(target {proposal['target']})")
    return f"- OFFLINE STRIKE PROPOSAL: fire {tool} on the surface you mapped."


def tag_descriptions(tools):
    """F6: make the benches VISIBLE — prefix each tool desc with its bench.
    Returns new dicts (registry dicts are never mutated)."""
    from tools._phases import phase_for
    out = []
    for t in tools:
        bench = phase_for(t.get("name", ""))
        out.append({**t, "desc": f"[{bench}] {t.get('desc', '')}"})
    return out
