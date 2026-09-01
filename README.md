# ⚒️ VOIDFORGE

AI-driven offensive-security framework. Consolidates a personal arsenal into one
autonomous agent that plans and executes attacks from natural-language missions.

## ARMING
```yaml
# config/provider.yaml
provider:
  base_url: https://api.deepseek.com/v1   # any OpenAI-compatible
  api_key: YOUR_KEY
  model: deepseek-chat
```

## STRIKE
```powershell
python main.py "Full recon of example.com: fingerprint, JS secrets, API map"
python main.py --tools                    # list arsenal
python main.py --tool har_dissect {"har_path": "C:\\path\\capture.har"}
```

## ARSENAL (62 modules)
recon: web_fingerprint · endpoint_oracle · js_mine_url/site · subdomain_enum
forensics: har_dissect · har_tokens
auth: auth_signup_probe · auth_metadata_poison · otp_brute
injection: sqli_probe_param · sqli_union_dump · sqli_blind_extract
rce: cmd_exec_probe · shell_exec · ssti_detect_rce · upload_webshell · shell_session
advanced: race_smash · smuggle_probe · proto_pollute · xxe_probe · redirect_cast
c2: c2_pulse (beacon discipline: jitter · UA rotation · backoff)
files: lfi_file_read
identity: jwt_analyst · jwt_forge_replay (alg:none · RS→HS · kid · jku/x5u) · idor_enum · idor_b64_walk
zeroday: fuzz_attack_surface (learned seed corpus) · crash_triage_next (emits fuzz_seeds) · nday_exploit (stack-match gate)
telegram: tg_probe · tg_history_harvest
realtime: realtime_tap (supabase phoenix spy)
intel: nvd_search · cisa_kev
reverse: deobfuscate_js · vm_string_dump

## DOCTRINE (knowledge/)
SUPABASE_SIEGE_PLAYBOOK · WAR_PLAN_TELEGRAM · RESEARCH_AI_FRAMEWORKS · MATHCORE_ANALYSIS · OFFENSIVE_STATE_OF_ART

## ROADMAP
v0.2 MCP server exposure · continuous daemon · attack-map reports
v0.3 playwright SPA crawler module · auto-chaining missions
```
