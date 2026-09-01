# VOIDFORGE TOOL RESEARCH — integration candidates (survey round 3)

## Technique sources analyzed for extraction
| Tool | ★ | Extractable technique → VOIDFORGE module |
|---|---|---|
| trufflehog / gitleaks | 15K+/10K+ | Secret regex rule sets → **secret_scan** (DONE v0.2, 13 rules imported) |
| nuclei | 22K+ | Template-driven vuln probing → planned: `nuclei_template_runner` wrapper |
| katana | 12K+ | JS-aware crawler → covered by spa_crawl; deeper parse later |
| subfinder | 9K+ | Passive subdomain sources (crt.sh, hackertarget) → **subdomain_enum** (DONE) |
| Telethon harvesters | various | Channel/user scraping → **tg_history_harvest** (DONE), account-mode pending burner |
| Photon | 10K+ | OSINT crawler patterns → fold into spa_crawl deep mode |
| LinkFinder | 3K+ | JS endpoint extraction regexes → enrich js_mine patterns |
| arjun | 3K+ | Hidden-parameter discovery → planned: `param_brute` (wordlist + response-diff heuristics) |

## Darknet reality check
- Onion indexes carry almost no Telegram-economy tooling: that economy lives in-platform.
- Leak-site chatter about DB dumps concentrates on breach forums, not onion search engines.
- Practical intel channel = GitHub advisories + CISA KEV + exploitdb git mirror (all integrated or queued).

## Next integrations queue
1. param_brute (arjun-style hidden param discovery)
2. nuclei template runner (-t webvulns, json output parser)
3. waf_detect (fingerprint cloudflare/aws-waf/sucuri from response headers)
4. mail_hunter (email pattern guesser + breach-db checks)
