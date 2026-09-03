"""VOIDFORGE :: phase tagging — registry-level metadata for the 5 benches
(RECON / SURFACE / EXPLOIT / POST-EXPLOIT / ADAPT) of the PHASE GUIDE doctrine.

This map is INTERNAL metadata: it is never sent in the LLM tool schema
(llm.py sends only name/desc/params). It powers operator observability and
phase-aware tooling. forged_* runtime tools are ADAPT by design.
"""

RECON = "recon"        # passive intel, OSINT, CVE knowledge
SURFACE = "surface"    # active scouting, endpoint/param discovery, fingerprint
EXPLOIT = "exploit"    # strikes: injection, auth bypass, race, smuggling
POST = "post-exploit"  # shells, pivots, C2, persistence, exfil
ADAPT = "adapt"        # forge, skills, evidence, mission infrastructure

PHASE_MAP = {
    # --- recon -------------------------------------------------------------
    "web_search": RECON, "web_read": RECON, "nvd_search": RECON,
    "cisa_kev": RECON, "ip_intel": RECON, "subdomain_enum": RECON,
    "wayback_urls": RECON, "nday_exploit": RECON, "cn_fingerprint": RECON,
    "payload_library": RECON, "trajectory_insight": RECON, "wall_breaker": RECON,
    "workspace_status": RECON, "skill_list": RECON, "skill_load": RECON,
    "operator_message": ADAPT, "report_write": ADAPT, "evidence_pack": ADAPT,
    # --- surface -----------------------------------------------------------
    "web_fingerprint": SURFACE, "waf_detect": SURFACE, "js_mine_site": SURFACE,
    "js_mine_url": SURFACE, "endpoint_oracle": SURFACE, "dir_brute": SURFACE,
    "param_brute": SURFACE, "api_sweep": SURFACE, "spa_crawl": SURFACE,
    "httpx_sweep": SURFACE, "nmap_scan": SURFACE, "nuclei_scan": SURFACE,
    "fuzz_attack_surface": SURFACE, "graphql_introspect": SURFACE,
    "har_dissect": SURFACE, "har_tokens": SURFACE, "har_passive_scan": SURFACE,
    "secret_scan": SURFACE, "file_grep": SURFACE, "deobfuscate_js": SURFACE,
    "vm_string_dump": SURFACE, "crypto_hash": SURFACE,
    "sqli_probe_param": SURFACE, "ssti_detect_rce": SURFACE,
    "cmd_exec_probe": SURFACE, "lfi_file_read": SURFACE,
    "auth_signup_probe": SURFACE, "auth_metadata_poison": SURFACE,
    "jwt_analyst": SURFACE, "idor_b64_walk": SURFACE,
    "ssrf_probe": SURFACE, "redirect_cast": SURFACE,
    "proto_pollute": SURFACE, "smuggle_probe": SURFACE, "xxe_probe": SURFACE,
    "vf_template_scan": SURFACE,
    # --- exploit -----------------------------------------------------------
    "sqli_union_dump": EXPLOIT, "sqli_blind_extract": EXPLOIT,
    "sqli_tamper_chain": EXPLOIT, "idor_enum": EXPLOIT, "otp_brute": EXPLOIT,
    # ── Tier G science engine — hypothesis as first-class object ──
    "hypothesis_test": EXPLOIT, "differential_sweep": EXPLOIT,
    "jwt_forge_replay": EXPLOIT, "race_smash": EXPLOIT, "h2_race_attack": EXPLOIT,
    "upload_webshell": EXPLOIT, "shell_exec": EXPLOIT, "shell_session": EXPLOIT,
    "cmd_exec_probe": SURFACE,  # detection tool (kept SURFACE above)
    "auth_state_audit": EXPLOIT,
    "supabase_exfil": EXPLOIT, "supabase_full_assault": EXPLOIT,
    "realtime_tap": EXPLOIT,
    "tg_probe": SURFACE, "tg_history_harvest": EXPLOIT,
    "tg_market_scan": SURFACE, "tg_members_scrape": SURFACE,
    "tg_messages_dump": EXPLOIT,
    # --- post-exploit ------------------------------------------------------
    "c2_pulse": POST, "deploy_watch": POST, "binary_fuzz_run": EXPLOIT,
    "crash_triage_rank": POST, "crash_triage_next": POST,
    # --- binary lane (static recon + live crash hunting + escalation) ------
    "bin_triage": SURFACE, "bin_strings": SURFACE, "bin_disasm": SURFACE,
    "bin_fuzz_live": EXPLOIT, "privesc_enum": POST,
    # --- adapt -------------------------------------------------------------
    "batch_execute": ADAPT, "replay_mutate": ADAPT,
}


def phase_for(name):
    """Phase of a registry tool; forged_* runtime extensions are ADAPT."""
    if name.startswith("forged_"):
        return ADAPT
    return PHASE_MAP.get(name, SURFACE)
