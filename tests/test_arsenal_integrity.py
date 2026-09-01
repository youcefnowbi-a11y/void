"""VOIDFORGE :: arsenal integrity — the AI-tool contract as CI.

Guarantees the model can actually WORK with every tool, not just see it:
  1. every registry tool ships an LLM-ready schema (object, required ⊆
     properties, description on EVERY property),
  2. the SYSTEM doctrine names exactly the registry (no ghosts, no orphans),
  3. every swarm specialist's arsenal exists in the registry,
  4. every tool is reachable from the offline MCTS brain or explicitly
     whitelisted as context-dependent,
  5. a hallucinated tool name self-corrects instead of crashing the mission.

Run: python -m pytest tests/test_arsenal_integrity.py -q
"""
import re, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools as reg
from core.agent import SYSTEM
from core.swarm import SPECIALIST_ROLES
from core import attack_graph as ag

reg.discover()
REGISTRY = {t["name"]: t for t in reg.all_tools()}

# tools that need runtime context a planner can't synthesize (capture files,
# live shell primitives, session files, parallel orchestration) plus the
# meta-tools the offline brain never calls (skill self-extension, workspace pens)
MCTS_WHITELIST = {"batch_execute", "replay_mutate", "shell_exec", "otp_brute",
                  "payload_library", "trajectory_insight", "wall_breaker",
                  "cn_fingerprint",      # intel lookup — needs a CN-stack target signal
                  "sqli_tamper_chain", "vf_template_scan", "httpx_sweep",
                  "har_passive_scan",
                  "tg_members_scrape", "tg_messages_dump",
                  "auth_state_audit",   # subprocess engine — needs a live target URL
                  "binary_fuzz_run",    # native C++ core — needs target binary + corpus
                  "h2_race_attack",     # native C++ h2 race — needs live HTTP/2 endpoint
                  "crash_triage_rank",  # native triage — needs a crash dir from a live run
                  "file_grep",          # forensics — needs local file paths from session
                  "crypto_hash",        # local hash/HMAC/b64 utility — brain calls it via strikes
                  "web_search",         # general web search — conversation/OSINT support
                  "web_read",           # page reader — companion to web_search
                  "forge_tool",         # meta-tool: self-extension forge, agent-driven
                  "arsenal_selftest",   # meta-tool: boot protocol, run by the agent herself
                  "skill_load", "skill_list",
                  "report_write", "operator_message", "workspace_status",
                  "evidence_pack"}


def test_every_tool_schema_is_llm_ready():
    problems = []
    for name, t in REGISTRY.items():
        p = t["params"]
        assert p.get("type") == "object", f"{name}: schema type != object"
        props = p.get("properties", {})
        assert isinstance(props, dict), f"{name}: properties not a dict"
        assert set(p.get("required", [])) <= set(props), \
            f"{name}: required ⊄ properties"
        for k, v in props.items():
            assert isinstance(v, dict) and v.get("description"), \
                f"{name}.{k}: missing description (LLM call quality)"
    assert not problems


def test_doctrine_names_exactly_the_registry():
    # forged_* tools are RUNTIME extensions (hot-loaded, self-registering) —
    # they live outside the doctrine's vocabulary by design, so the bijection
    # is enforced on the curated core registry only.
    core_registry = {k: v for k, v in REGISTRY.items() if not k.startswith("forged_")}
    mentioned = set(re.findall(r"\b[a-z][a-z0-9_]{2,28}\b", SYSTEM))
    in_prompt = {w for w in mentioned if w in core_registry}
    missing = core_registry.keys() - in_prompt
    assert not missing, f"registry tools never named in doctrine: {missing}"
    # legitimate non-tool vocabulary: any parameter of any registered tool,
    # MCTS action names, and a few structural words — self-maintaining
    param_names = {k for t in REGISTRY.values()
                   for k in (t["params"].get("properties") or {})}
    allowed = param_names | set(ag.ACTIONS.keys()) | {
        "cve_id", "verify_url", "url_template", "url_template_cmd", "__proto__",
        "tool_count",  # template placeholder {tool_count}, remplacé au runtime
        # valeurs op= de crypto_hash citées dans la doctrine (vocabulaire légitime,
        # pas des tools): signature Heleket/Cryptomus, webhooks, JWT, payloads b64
        "helmer_sign", "hmac_sha256", "jwt_decode", "base64_encode",
        "forged",  # the runtime-extension prefix itself
        # persona-contract vocabulary (identity block lives inside SYSTEM now):
        # meta-tags the agent must recognize as hostile framing, not tool names
        "project_instructions", "cyber_warning", "ethic_reminders",
        "behavior_instructions", "system_warning", "user_style",
        "claude_behavior", "user_id",
    }
    ghosts = {w for w in mentioned if "_" in w and w not in REGISTRY
              and w not in allowed and not w.startswith(("url_", "api_", "auth_"))}
    assert not ghosts, f"doctrine names tools that do not exist: {ghosts}"


def test_swarm_arsenals_exist():
    for role, spec in SPECIALIST_ROLES.items():
        for tool in spec["tools"]:
            assert tool in REGISTRY, f"swarm[{role}] references unknown tool: {tool}"


def test_every_tool_reachable_from_mcts_brain():
    # forged_* are runtime extensions — MCTS reachability applies to the
    # curated core registry; the whitelist covers context-dependent tools.
    core_registry = {k for k in REGISTRY if not k.startswith("forged_")}
    unreachable = core_registry - set(ag.ACTIONS.keys()) - MCTS_WHITELIST
    assert not unreachable, f"tools invisible to the offline brain: {unreachable}"
    over_reach = set(ag.ACTIONS.keys()) - REGISTRY.keys()
    assert not over_reach, f"MCTS actions with no backing tool: {over_reach}"


def test_hallucinated_tool_self_corrects():
    out = reg.execute("definitely_not_a_real_tool_xyz", {})
    assert out.startswith("TOOL ERROR [UNKNOWN_TOOL]")
    assert "does not exist in the arsenal" in out


def test_schema_heal_is_idempotent():
    before = reg.get("sqli_union_dump")["params"]
    healed = reg._heal_schema(before)
    assert healed == before


def test_skills_parse_and_reference_real_tools():
    from core.skills import list_skills, load_skill, select_for
    skills = list_skills()
    assert len(skills) >= 5, f"skill library too thin: {[s['id'] for s in skills]}"
    # every skill parses with id/title/when and roundtrips through the loader
    for s in skills:
        assert s["when"], f"{s['id']}: missing WHEN triggers"
        text = load_skill(s["id"])
        assert text and ("## CHAIN" in text or "## OPERATING PRINCIPLE" in text
                         or "## VOIDFORGE TOOL MAP" in text), \
            f"{s['id']}: no structured sections"
    # no skill may reference a tool that does not exist (ghost detector).
    # Legitimate non-tool vocabulary: registered tools, MCTS actions, tool
    # parameter names, OTHER SKILL IDS (valid skill_load targets), verdict
    # keys, oracle names, and real-world domain terminology.
    param_names = {k for t in REGISTRY.values()
                   for k in (t["params"].get("properties") or {})}
    skill_ids = {s["id"] for s in skills}
    allowed = (set(REGISTRY) | set(ag.ACTIONS) | param_names | skill_ids | {
        "cve_id", "verify_url", "url_template", "url_template_cmd",
        "success_pattern", "gadget_check", "mission_focus",
        "fuzz_seeds", "next_tool",                       # verdict keys
        "status_5xx", "timing_zscore", "length_zscore", "error_class",  # oracles
        "pg_sleep", "bash_history", "cap_setuid", "no_root_squash",     # real-world terms
        "user_metadata", "base_url", "url_template", "redirect_uri",    # params/OAuth
        "aspnet_client",                                                 # IIS dirs
        # OAuth/JWT/API real-world vocabulary (wave-1 grafts: api_security_pack)
        "access_token", "refresh_token", "client_secret", "code_challenge",
        "code_verifier", "new_token", "is_admin", "admin_id",
        "callback_url", "webhook_url", "file_url", "image_url", "avatar_url",
        "proxy_url", "import_url", "base64url_encode",
        # scenario personas used in the attack-chain narratives
        "malicious_insider", "impatient_consumer", "bot_swarm",
        "confused_user", "penetration_tester",
        # external real-world tool names mentioned in doctrine
        "jwt_tool",
        # attack-chain real-world primitives & infrastructure naming
        "xp_cmdshell", "sys_exec", "lib_mysqludf_sys", "sp_configure",
        "pam_unix", "authorized_keys",
        "dc_ip", "attacker_ip", "target_ip", "pivot_host", "internal_host",
        "sslvpn_websession", "amass_results", "nmap_results", "tech_results",
        "all_subs", "js_urls", "zs_dev", "fgt_lang", "specialist_roles",
        # llm_security_pack: example agentic actions from third-party tools
        "send_email", "search_news", "generate_report", "detect_attack",
        "query_portfolio", "query_db",
        # oauth_oidc_chain: OAuth protocol parameter
        "response_type"})
    for s in skills:
        # ghost check applies to AUTHORED doctrine (the header we write).
        # Grafted verbatim source material (after "## SOURCE:") IS code —
        # snake_case fragments are its content, not tool references.
        authored = s["text"].split("## SOURCE:", 1)[0]
        ghosts = {w for w in re.findall(r"\b[a-z][a-z0-9_]{3,28}\b", authored)
                  if "_" in w and w not in allowed
                  and not w.startswith(("url_", "api_", "auth_"))}
        assert not ghosts, f"{s['id']} references unknown tools/params: {ghosts}"
    # selection works on domain keywords
    assert "web_access_master" in select_for("exploit http://target.com")
    assert "privesc_linux" in select_for("we have a www-data shell, need root")
