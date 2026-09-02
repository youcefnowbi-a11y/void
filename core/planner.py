"""VOIDFORGE :: Offline mission planner - keyword-driven tool chaining.
Executes natural-language missions WITHOUT any LLM. The LLM layer (agent.py)
upgrades quality when a key is present; this guarantees the framework works
always. Intent detection -> ordered tool chain -> aggregated report."""
import re, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# R2-12 : table INTENTS morte supprimée — jamais consommée dans tout le repo.

def extract_target(mission):
    m = re.search(r"https?://[^\s,;\"]+", mission)
    if m: return m.group(0).rstrip("/")
    m = re.search(r"\b([a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.(?:com|net|org|me|io|site|shop|store|xyz|tv|cc|fr|dev|app|biz|eu|de|uk|ca|info|online|cloud|ai))\b", mission, re.I)
    if m:
        t = m.group(1)
        return ("https://" + t) if not t.startswith("http") else t
    return None

def extract_path(mission):
    m = re.search(r"[A-Za-z]:\\[^\s,;]+|\./[^\s,;]+|[A-Za-z0-9_\-]+\.(?:har|json|js|txt|md)", mission)
    return m.group(0) if m else None

def plan(mission):
    """Returns ordered [(tool_name, args)] plan."""
    import tools as reg
    available = {t["name"] for t in reg.all_tools()}
    target = extract_target(mission)
    low = mission.lower()
    plan_ = []

    def add(tool, args):
        if tool in available:
            plan_.append((tool, args))

    # file-based missions
    p = extract_path(mission)
    if p and p.endswith(".har"):
        add("har_dissect", {"har_path": p}); add("har_tokens", {"har_path": p})
    if re.search(r"secret|leak|credential", low) and p:
        add("secret_scan", {"path": p})

    # domain/url missions
    if target:
        has_specific = False
        if re.search(r"\b(?:fingerprint|stack|recon|cartograph|analyse|map)\b", low):
            add("web_fingerprint", {"url": target})
            has_specific = True
        if re.search(r"\b(?:waf|firewall|protect)\b", low):
            add("waf_detect", {"url": target})
            has_specific = True
        if re.search(r"\b(?:sqli|inject)\b", low):
            add("sqli_probe_param", {"url_template": target + "?q={INJ}"})
            if re.search(r"\b(?:dump|extract|exfil|data|table)\b", low):
                add("sqli_union_dump", {"url_template": target + "?q={INJ}"})
            has_specific = True
        if re.search(r"\b(?:rce|command.?inject|shell|exec)\b", low):
            add("cmd_exec_probe", {"url_template": target + "?q={INJ}"})
            has_specific = True
        if re.search(r"\b(?:ssti|template)\b", low):
            add("ssti_detect_rce", {"url_template": target + "?q={INJ}"})
            has_specific = True
        if re.search(r"\b(?:race|concurrent|concurrence|condition|double)\b", low):
            add("race_smash", {"url": target})
            has_specific = True
        if re.search(r"\b(?:smuggl|desync|cl\.te|te\.cl|proxy)\b", low):
            add("smuggle_probe", {"url": target})
            has_specific = True
        if re.search(r"\b(?:prototype|pollut|__proto__)\b", low):
            add("proto_pollute", {"url": target, "gadget_check": target + "/profile"})
            has_specific = True
        if re.search(r"\b(?:xxe|xml|saml|soap)\b", low):
            add("xxe_probe", {"url": target})
            has_specific = True
        if re.search(r"\b(?:redirect|redirection|open.?redirect|callback|sso)\b", low):
            add("redirect_cast", {"url": target})
            has_specific = True
        if re.search(r"\b(?:c2|beacon|heartbeat|liveness)\b", low):
            add("c2_pulse", {"shell_url": target})
            has_specific = True
        if re.search(r"\b(?:lfi|traversal|read.?file|fichier)\b", low):
            add("lfi_file_read", {"url_template": target + "?page={INJ}"})
            has_specific = True
        if re.search(r"\b(?:jwt|forge)\b", low):
            # E1 : has_specific seulement si un token est réellement dans la
            # mission — « jwt analysis of site.com » sans token doit retomber
            # sur la chaîne de recon par défaut, pas produire un plan vide.
            # (jwt_analyst exige un arg `token` : il ne peut pas soutenir un
            # plan sans token, on ne l'ajoute donc pas en fallback.)
            tok_m = re.search(r"(eyJhbGci[A-Za-z0-9_\-.]+)", mission)
            if tok_m:
                add("jwt_forge_replay", {"token": tok_m.group(1), "replay_url": target})
                has_specific = True
        if re.search(r"\b(?:idor|bola)\b", low):
            add("idor_enum", {"url_template": target + "/{ID}", "start": 1, "stop": 60})
            has_specific = True
        if re.search(r"\bupload\b", low):
            add("upload_webshell", {"upload_url": target,
                                     "base_uploads_url": target.rstrip("/") + "/uploads/"})
            has_specific = True
        if re.search(r"\b(?:fuzz|zero.?day|0day)\b", low):
            add("fuzz_attack_surface", {"url": target, "max_requests": 250})
            add("crash_triage_next", {})
            has_specific = True
        if re.search(r"\b(?:poc|nday|n.?day)\b", low):
            cve_m = re.search(r"(CVE-\d{4}-\d{4,7})", mission, re.I)
            add("nday_exploit", {"cve_id": cve_m.group(1) if cve_m else None,
                                  "keyword": None if cve_m else target})
            has_specific = True
        if re.search(r"\b(?:endpoint|api|routes?|oracle)\b", low):
            add("endpoint_oracle", {"base": target,
                "paths": ["api.php/me","admin","login","api/user","stat.php","robots.txt",
                          ".env","config","backup","api.php/dashboard"]})
            has_specific = True
        if re.search(r"\b(?:js|minify|bundle|script)\b", low):
            add("js_mine_site", {"site": target})
            has_specific = True
        if re.search(r"\b(?:subdomain|sous.?domain)\b", low):
            add("subdomain_enum", {"domain": re.sub(r"^https?://", "", target).split("/")[0]})
            has_specific = True
        if re.search(r"\bsupabase\b", low):
            # Extract project ref from mission text if present
            ref_m = re.search(r"([a-z0-9]{18,22})\.supabase\.co", mission) or re.search(r"ref[:\s]+([a-z0-9]{18,22})", low)
            anon_m = re.search(r"(eyJhbGci[A-Za-z0-9_\-.]+)", mission)
            if ref_m and anon_m:
                add("supabase_exfil", {"project_ref": ref_m.group(1), "anon_key": anon_m.group(1)})
            else:
                add("spa_crawl", {"url": target})
            has_specific = True

        # Si l'utilisateur saisit juste une cible (ex: "www.hqjcw.com"), déployer la chaîne de reconnaissance par défaut
        if not has_specific:
            clean_dom = re.sub(r"^https?://", "", target).split("/")[0]
            add("web_fingerprint", {"url": target})
            add("waf_detect", {"url": target})
            add("endpoint_oracle", {"base": target, "paths": ["robots.txt", ".env", "api", "admin", "login"]})
            add("js_mine_site", {"site": target})
            add("subdomain_enum", {"domain": clean_dom})
    else:
        # handle-only missions (telegram)
        m = re.search(r"@([A-Za-z0-9_]{4,32})", mission)
        if m or re.search(r"telegram|canal|channel|tg\b", low):
            handles = ([m.group(1)] if m else ["durov"])
            add("tg_probe", {"handles": handles})
            if re.search(r"histor|harvest|scrap", low):
                add("tg_history_harvest", {"channel": handles[0], "pages": 8,
                    "code_regex": r"(?:temp\s*otp|otp|code)\s*[:\-]?\s*\**\s*([A-Z0-9]{6,14})"})

    # intel missions
    for kw, tool in [("cve", "nvd_search"), ("kev", "cisa_kev"),
                     ("exploit", "nvd_search"), ("vulnerab", "nvd_search")]:
        if kw in low:
            words = re.findall(r"[a-zA-Z]{4,}", mission)
            kw_arg = next((w for w in words if w.lower() not in
                          ("cherche","find","latest","dernier","les","des","avec","pour")), "database")
            add(tool, {"keyword": kw_arg} if tool == "nvd_search" else {"keyword": kw_arg})
            break

    return plan_

def execute_plan(plan_, reporter=print):
    """Executes the tool chain, sequenced by bandit expected-value ordering.
    Every outcome feeds back into the bandit -> the planner gets smarter
    with every mission it runs."""
    import time
    import tools as reg
    try:
        from core.mathcore import bandit_rank, bandit_record
        scores = bandit_rank([n for n, _ in plan_])
    except Exception:
        bandit_record = None
        scores = [0.0] * len(plan_)
    # R2-10 : le bandit pur détruisait l'ordre scout→strike du plan — tri
    # stable par tiers (recon/scout = 0, tout le reste = 1), bandit en
    # tie-break dans chaque tier.
    def _tier(i):
        n = plan_[i][0]
        return 0 if any(k in n for k in
                        ("probe", "fingerprint", "recon", "enum", "scan",
                         "dir_brute", "param_brute")) else 1
    order = sorted(range(len(plan_)), key=lambda i: (_tier(i), -scores[i]))

    results = []
    for idx in order:
        name, args = plan_[idx]
        reporter(f"⚙ {name}({json.dumps(args, ensure_ascii=False)[:140]})")
        t0 = time.time()
        out = reg.execute(name, args)
        dur = time.time() - t0
        if bandit_record:
            ok_ = not (isinstance(out, str) and out.startswith("TOOL ERROR"))
            try:
                bandit_record(name, ok_, dur)
            except Exception:
                pass
        results.append({"tool": name, "args": args, "output": out})
        reporter(f"   -> {out[:180]}")
    return results
