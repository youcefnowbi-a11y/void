MISSION BRIEF — VOIDFORGE ENGAGEMENT #79 (DATA EXTRACTION LIVE)
══════════════════════════════════════════

TARGET: duskyr.com (+ payment.duskyr.com, api.duskyr.com if exists,
www.duskyr.com, any subdomain discovered)
PRIMARY: https://duskyr.com/api/market/listings

PRIMARY OBJECTIVE — EXTRACT REAL DATA. This is a live marketplace
(escrow for digital goods and accounts). The mission succeeds when
REAL product data is extracted and archived: actual listings, real
prices, real sellers, real categories — not the homepage HTML, the
API DATA behind it. Impact scenarios:

1. FULL CATALOGUE PULL — the complete product/listing inventory via
   the public API: every listing with its real fields (title, price,
   seller, category, status, dates). data_dump_paginated if pagination
   exists, differential_sweep on offset/limit/page params to MAP the
   pagination grammar first if unknown.

2. SELLER/ACCOUNT DATA — vendor profiles, seller listings, ratings,
   any PII surface (emails, handles, transaction counts). The accounts
   marketplace sells ACCOUNTS — what metadata leaks about them?

3. FINANCIAL PLANE — payment.duskyr.com: exchange rates, USDT rails,
   fee structures, and any unauthenticated financial endpoints. The
   /v1/exchange-rate/USDT/list lane showed timing anomalies (19s vs
   0.4s on 522 errors) in prior intel — never investigated.

4. AUTH SURFACE — signup/login flow: does an account exist that can
   be created natively (no captcha)? With an account, what data does
   the authenticated API expose? (Order history, saved payment
   methods, internal user objects.)

KNOWN FROM PRIOR INTEL (verified intel, do NOT re-derive):
- https://duskyr.com/api/market/listings/404?q= — 522 errors with
  body_delta 15 vs 988 bytes on SSRF payloads (prior fuzz, round 76)
- payment.duskyr.com/v1/exchange-rate/USDT/list — timing 25.5s on
  {{7*7}} (ssti marker), 4.8s on path traversal, 6.6s on 0x7fffffff
- The stack handles USDT/BTC exchange-rate listings publicly

METHOD — the science engine is armed, use it:
- hypothesis_test EVERY "the API requires auth for X" belief — the
  marketplace API might serve deeper data unauthenticated
- differential_sweep the pagination params (one round = 50 probes)
- data_dump_paginated once the grammar is proven — full catalogue
- use_jar=true on data_extract for any login chain (the cookie jar
  W12 holds sessions across calls now)
- Every extraction lands in extractions/ via evidence_pack; REAL data
  = real rows, real prices, real identifiers

RULES OF ENGAGEMENT: standard operator mandate, aggressive intensity,
direct egress. This is reconnaissance and data extraction on a public
marketplace — the data must be DEMONSTRATED (rule 8): archived files
with real listing content, not error responses.

DELIVERABLE: engagement report + findings dossier. The success metric
is EXTRACTED REAL DATA archived in extractions/ — count the rows.
Close with the NEXT MISSION PROPOSAL.
