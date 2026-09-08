# -*- coding: utf-8 -*-
"""Append K2 graft-log section."""
import io

P = "SYSTEM_MAP/12_graft_log.md"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

section = """
## MISSION K2 + FLEET FIXES (2026-09-06 — the wall fully characterized)
- K2 (93 rounds, 155 calls, 100 min, zero provider outage — failover
  fleet steady): the Telegram wall HELD with definitive verdicts across
  10 vectors, all evidence-sealed: bot-token 0/566 archived files
  (strict+loose byte sweep) + 0/94 channel messages; initData forgery
  refuted at the HMAC chain (identical bare 401 across all shapes);
  twin-planes refuted live (main dk_token -> verifier 401); verify-
  confirm route EXISTS (GET 405) but guard sealed (uniform 403 on 13
  secret placements); SQLi listings HELD (pydantic 422); keypool
  marker candidate rejected; all 4 archived sessions tg_linked=false.
- NEW INTEL SEALED despite the hold: verify flow fully decoded
  (POST /api/profile/verify/start -> dvf_<10 chars> code TTL 900s ->
  bot /start -> server flip), the xgift3m purchase grammar
  (claimVerifyLive -> /api/verify/xgift3m/purchase -> /orders retry-
  delivers ORDER CODE = the delivered product), reviews plane open
  (buyer TG handles public), /api/claude-team-seat/pending per-caller
  oracle, keypool openapi names the full admin plane (x-admin-token:
  overview/logs/provider_keys/reseller_keys), seller posted a live
  test account promo (wendallinda827 class), 4th bot discovered
  (@verify_group_bot unlock flow).
- THE AUTH HEADER DECODED (round-7 operator fix, from the 60-208KB
  gap that 8 missions never reached): the verifier's api() wrapper
  sends `X-Telegram-Init-Data: <initData>` — the exact header name
  K2 hunted in 13 shapes. Re-tested live: uniform 401 on fake/garbage/
  empty/no-hash -> the backend runs the REAL HMAC validation
  (GRM-TGM-003). The wall is now characterized with certainty: header
  known, algorithm known, only the bot token missing (leakage-class).
- FLEET FIXES (3, all live-verified):
  1. data_extract offset_bytes — sliding byte window ANYWHERE in a
     body (the 458KB verifier HTML middle reached in ONE call; caps
     raised truncate 600K / tail 500K). The 7-round window gymnastics
     of K2 will never happen again.
  2. spa_crawl req_headers capture — the fetch/XHR hook now records
     the app's own auth headers (redacted to class+shape), the single
     best oracle per K2's own verdict.
  3. (fixed same-session earlier) tail window sizer from P1.
- Battery 382/382 after all fixes.
- NEXT-AXIS (K2 sealed): (1) operator lane — real Telethon /start
  dvf_<code> on our own account completes verification by the
  INTENDED flow; verified session -> buy plane -> product. (2) watch
  for NEW verifier bundle versions (20260905-v4 naming = versioned
  deploys) for a client-side secret leak. (3) keypool admin value
  hunt in future artifacts + customer lane /v1/models trial issuance.
"""

with io.open(P, "a", encoding="utf-8") as f:
    f.write(section)
print("graft log appended:", len(section), "chars")
