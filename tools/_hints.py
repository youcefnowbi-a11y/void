"""VOIDFORGE :: chain hints — the self-guiding arsenal.

Le pattern crash_triage_next (qui retourne déjà 'le prochain outil') généralisé:
chaque sortie d'outil qui PRODUIT un artefact annonce les outils qui le
CONSOMMENT. L'agente ne découvre plus le graphe par essais/erreurs — chaque
résultat est un panneau qui pointe vers la suite. Coût prompt: zéro (injecté
au runtime, pas dans les specs). Zéro vocabulaire refroidissant: que du
purement opérationnel.
"""

# producer -> (consumer, why) pairs. Noms vérifiés contre le registre.
NEXT_HINTS = {
    "web_fingerprint": [("waf_detect", "confirm WAF stack"), ("js_mine_site", "mine the JS bundle"), ("subdomain_enum", "expand perimeter")],
    "waf_detect": [("smuggle_probe", "if proxy stack detected"), ("api_sweep", "map the API surface")],
    "subdomain_enum": [("httpx_sweep", "probe which subdomains are live")],
    "wayback_urls": [("endpoint_oracle", "classify archived paths"), ("secret_scan", "grep archived bodies")],
    "spa_crawl": [("sqli_tamper_chain", "strike the forms found"), ("fuzz_attack_surface", "fuzz the endpoints")],
    "js_mine_site": [("deobfuscate_js", "unwrap the bundles"), ("secret_scan", "grep for leaked keys")],
    "js_mine_url": [("deobfuscate_js", "unwrap the bundle"), ("vm_string_dump", "extract VM bytecode strings")],
    "deobfuscate_js": [("secret_scan", "grep the clean source"), ("file_grep", "search saved artifacts")],
    "httpx_sweep": [("web_fingerprint", "fingerprint each live host")],
    "port_scan_sync": [("web_fingerprint", "fingerprint the services found")],
    "nmap_scan": [("web_fingerprint", "fingerprint each open service")],
    "secret_scan": [("jwt_analyst", "analyze any JWT found"), ("data_extract", "use the keys against the API")],
    "sqli_probe_param": [("sqli_union_dump", "dump the confirmed point"), ("sqli_blind_extract", "if union renders nothing")],
    "sqli_union_dump": [("sqli_blind_extract", "if union renders nothing"), ("evidence_pack", "seal the proof")],
    "sqli_blind_extract": [("evidence_pack", "seal the proof")],
    "ssti_detect_rce": [("shell_exec", "run the confirmed engine"), ("upload_webshell", "persist access")],
    "cmd_exec_probe": [("shell_exec", "execute via confirmed separator"), ("upload_webshell", "persist access")],
    "lfi_file_read": [("file_grep", "hunt .env/wp-config/shadow"), ("secret_scan", "grep the pulled files")],
    "xxe_probe": [("lfi_file_read", "read files via the entity ladder")],
    "jwt_analyst": [("jwt_forge_replay", "forge and replay (alg:none/key confusion)")],
    "jwt_forge_replay": [("evidence_pack", "seal the replay proof")],
    "har_dissect": [("har_tokens", "extract tokens from the capture"), ("idor_enum", "vary the IDs found")],
    "har_tokens": [("jwt_analyst", "analyze the JWTs"), ("idor_b64_walk", "walk the b64 IDs"), ("secret_scan", "grep all captured secrets")],
    "har_passive_scan": [("sqli_probe_param", "probe the price/credit fields"), ("race_smash", "race the mutation candidates")],
    "idor_enum": [("data_extract", "pull the exposed records"), ("evidence_pack", "seal the differential proof")],
    "idor_b64_walk": [("data_extract", "pull the exposed records")],
    "auth_signup_probe": [("auth_state_audit", "audit the guard state machine")],
    "auth_metadata_poison": [("auth_state_audit", "audit the guard state machine")],
    "auth_state_audit": [("race_smash", "race the unguarded window"), ("h2_race_attack", "HTTP/2 single-packet race (preferred)")],
    "race_smash": [("evidence_pack", "seal the before/after proof")],
    "h2_race_attack": [("evidence_pack", "seal the before/after proof")],
    "otp_brute": [("evidence_pack", "seal the successful code")],
    "upload_webshell": [("shell_session", "open the C2 rounds"), ("shell_exec", "run the first command")],
    "shell_exec": [("upload_webshell", "persist the access"), ("shell_session", "open the C2 rounds")],
    "shell_session": [("evidence_pack", "seal the access proof"), ("report_write", "document the chain")],
    "api_sweep": [("data_extract", "extract from the live endpoints"), ("sqli_probe_param", "probe the parameters")],
    "param_brute": [("sqli_probe_param", "probe the params found")],
    "dir_brute": [("endpoint_oracle", "classify the hits")],
    "graphql_introspect": [("data_extract", "extract via the schema")],
    "nuclei_scan": [("nday_exploit", "exploit confirmed CVE matches")],
    "nvd_search": [("nday_exploit", "exploit if the stack matches")],
    "cisa_kev": [("nday_exploit", "exploit KEV entries matching the stack")],
    "nday_exploit": [("evidence_pack", "seal the impact proof")],
    "fuzz_attack_surface": [("crash_triage_next", "rank the crashes into an action plan"), ("sqli_probe_param", "probe the interesting params")],
    "binary_fuzz_run": [("crash_triage_rank", "dedup + rate exploitability")],
    "crash_triage_rank": [("crash_triage_next", "get the ranked action plan")],
    "data_extract": [("data_dump_paginated", "full table dump"), ("evidence_pack", "seal the proof")],
    "data_dump_paginated": [("evidence_pack", "seal the proof")],
    "supabase_exfil": [("evidence_pack", "seal the exfil proof")],
    "realtime_tap": [("evidence_pack", "seal the tap proof")],
    "tg_probe": [("tg_history_harvest", "harvest the channel history")],
    "redirect_cast": [("evidence_pack", "seal the open-redirect proof")],
    "proto_pollute": [("evidence_pack", "seal the pollution proof")],
    "smuggle_probe": [("evidence_pack", "seal the desync proof")],
    "ssrf_probe": [("evidence_pack", "seal the internal access proof")],
}

# tools whose output IS already guidance / terminal / infrastructure — never hinted
_NO_HINT = {
    "arsenal_selftest", "report_write", "evidence_pack", "operator_message",
    "batch_execute", "crash_triage_next", "trajectory_insight", "forge_tool",
    "workspace_status", "skill_list", "skill_load", "crypto_hash",
    "payload_library", "file_grep", "web_search", "web_read", "vm_string_dump",
}

_ARROW = "\n\n→ NEXT: "


def hint_for(name, out):
    """Retourne la ligne d'indice à coller après la sortie de `name`, ou ''."""
    if name in _NO_HINT:
        return ""
    pairs = NEXT_HINTS.get(name)
    if not pairs:
        return ""
    if not out or not isinstance(out, str) or out.startswith("TOOL ERROR"):
        return ""
    if "→ NEXT:" in out:  # déjà guidé (batch nested, hint upstream)
        return ""
    body = ", ".join(f"{tool} ({why})" for tool, why in pairs)
    return _ARROW + body
