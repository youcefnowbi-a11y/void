# skill: recon_deep
title: Deep Reconnaissance Methodology (HackTricks × PEASS discipline)
when: recon,cartograph,map,enumerate,discovery,subdomain,footprint,scope

## OPERATING PRINCIPLE
Recon is not a phase you complete — it is a budget you allocate. The operator
who enumerated one more layer wins the engagement. Order matters: passive
before active, wide before deep, cheap before expensive. Every artifact you
collect (subdomain, port, tech, path) feeds the Living Graph, and the graph
suggests the connections you would have missed.

## CHAIN — THE SEVEN LAYERS
1. PASSIVE IDENTITY: subdomain_enum(domain) — certificate transparency
   (crt.sh) + hackertarget, no packets touch the target. Cert SANs reveal
   internal naming conventions (vpn-, dev-, old-, staging-).
2. INFRASTRUCTURE: ip_intel(host) — geo/ASN/reverse-DNS. Shared IP =
   neighbor attack surface; hosting pattern tells cloud vs on-prem.
   port_scan_sync for the wide port picture, nmap_scan for service/version
   detail on the interesting hosts.
3. TECHNOLOGY: web_fingerprint on every live host — server line, framework
   hints, security headers (absent headers = configuration debt = often
   direct attack surface). waf_detect per host: knowing the filter decides
   the payload grammar later (payload_grammar skill).
4. ARCHIVE: wayback_urls(domain) — every URL the target ever exposed:
   dead APIs, removed panels, forgotten params. Old + still-alive = often
   unpatched and forgotten.
5. CONTENT: dir_brute(base) per host + deploy_watch(target, action=snapshot)
   to baseline — deploy_watch diffs catch NEW routes on future runs (the
   silent deployment that ships the vulnerable feature).
6. APPLICATION: spa_crawl(url) — capture the real request grammar a browser
   emits (XHR/fetch), then js_mine_site — every bundle: routes, API URLs,
   JWTs, api keys, supabase refs, source-map recovered code. Secrets feed
   secret_scan; tokens feed jwt_analyst; refs feed cloud_takeover.
7. SYNTHESIS: hand the Living Graph to the strike layer — every asset kind
   has a mapped strike (endpoint→endpoint_oracle, key→data_extract,
   domain→subdomain_enum recursive). batch_execute fans out the independent
   probes concurrently.

## BRUTE DISCIPLINE
- DNS brute before dir brute: new subdomains often expose NEW services the
  main domain never shows.
- Per-host wordlist selection: uvicorn/python stack → /admin,/api,/docs,
  /static; IIS → /aspnet_client, .aspx extensions; nginx+php → .php grammar.
- Rate discipline: the shared pacer protects the target and your stealth;
  slow recon loses nothing, loud recon loses everything.

## CORRELATION GOLD (what the graph connects)
- Same ASN + same TLS SAN across subdomains = one internal naming scheme →
  guess the missing siblings (api-, internal-, jenkins-).
- An old wayback panel + a current JS bundle referencing its API = dead
  frontend, LIVE backend — endpoint_oracle the old paths.
- Two hosts sharing a build ID in JS bundles = same deploy pipeline —
  compromise surface is identical; test the fix on one, retest the other.

## FAILURE MODES
- Wildcard DNS: subdomain_enum returns noise — verify each hit with
  web_fingerprint (identical title/size across "subdomains" = wildcard).
- Cloud-hosted target with WAF+CDN: origin discovery via wayback IP history,
  mail headers (SPF/MX records leak origin), certificate historical data.
- Nothing interesting found: widen the scope sideways (acquired companies,
  forgotten TLDs, dev subdomains from SAN fields) — the perimeter is
  always bigger than the org thinks.
