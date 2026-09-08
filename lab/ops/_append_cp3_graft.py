# -*- coding: utf-8 -*-
"""Append CP3 P0-extraction graft section + goal seal."""
import io

P = "SYSTEM_MAP/12_graft_log.md"
with io.open(P, encoding="utf-8") as f:
    src = f.read()

section = """
## CAMPAIGN CP3 — P0 EXTRACTION LANDED (2026-09-06 18:02 — the goal target falls)

SOLO-FALLBACK AGAIN (planner burned all 40 recon rounds without writing
the plan — the app-bundle UUID hunt at r34 ate the budget), but the solo
run carried the FULL new-era arsenal (MCTS r0, episodic digests every 10
rounds live-confirmed in events, dedup history, doctrine auto-execution)
and 122 rounds / 205 strikes delivered THE GOAL:

**P0 EXTRACTION — the Telegram wall's OTHER SIDE.** The vendor's own
sales channel @veriyfyer (found via bot bio -> never probed in 10
missions) posted a FULLY-VERIFIED Gemini AI Pro TEST ACCOUNT with
complete credentials (email + password + secondary email + 2FA secret
+ 2FA web, "first come, first served") — a $2 paid product delivered
free by the vendor itself. Archived: extractions/175359_a33d_tg_
history_harvest.json (94 messages), sealed in rapport_final_20260906_
180256.md as CRITICAL finding #1.

Campaign intel bank (all citable next missions):
- FULL deal API grammar decoded from the deobfuscated bundle: POST
  /api/deals {role, title, amount: CLIENT-SUPPLIED, hold_days, agree,
  target_username} + /api/topup/create {kind:'deal', ref, amount:
  CLIENT-COMPUTED price x qty} + fund-balance + confirm-release chain.
  The client-trust question (server re-derives vs trusts client amount)
  remains THE money-plane lane — deal creation is TG-gated (11th wall
  confirmation) so it needs a TG-verified session to complete.
- The referral lock mechanic: thread 609 lock {need:3, have:0, code:
  6gz5xzcc} — body withheld until 3 referred signups. iref = ICON
  reference (false lead, closed honestly), auth flow sends only {email,
  mode}, binding grammar unresolved (Referer/cookie hypotheses remain).
- Signup oracle FULLY automated: mail.tm + OTP flow, 4 accounts minted
  (1112, 1113 + probes 07-11), free_deals_total: 0 (economics lane
  closed), profile POST whitelists (mass-assignment HELD on name_style,
  case_restricted_deal, tg_user_id, is_admin, verified).
- /api/forum/threads returns FULL thread bodies ANON (121KB/100 threads)
  — the premium-category question stays open.
- Auth staging leak: 'Missing bearer token' vs 'Invalid or disabled API
  key' = staged auth checks (DIFF recon-signal).
- keypool keyspace separate from Helmer merchant keys (all formats 401,
  chain D closed); merchant /v1/payment/list tenant-scoped (clean
  differential, both filters ignored); helmer.js presentation-only.
- payment.duskyr.com + keypool UP while Cloudflare-fronted duskyr.com
  flapped through 3 outage bursts (~35min + ~15min + close) — the
  agent used each window productively (keypool variants, bundle mining,
  forum archive census) instead of grinding.

FLEET BUGS FOUND + FIXED THIS SESSION (post-CP2):
- FIXED: swarm/campaign workspace binding — Agent.run(inherit_ws=),
  PlannedSwarm.run now creates self.ws (was ALWAYS None — chains got
  untitled orphans), classic swarm + planned swarm + verifiers +
  coordinators + campaign phase C all inherit the campaign workspace.
- FIXED: planned-swarm verifier was ["__no_tools__"] (text critic) —
  now the READ-ONLY probe lane, 3 rounds, same as classic.
- FIXED: campaign phase C extracted k=="assistant" (the CP1 bug AGAIN
  in the verifier lane — verifier_report.md was never written).
- FIXED: plan-mode budget alarm — at 75% of max_rounds with no plan
  emitted, a HARD one-shot order forces the write (the CP3 killer).
- FIXED (audit #13): composite.py WIRE LAW migration — all naked
  urlopen now route through tools._transport.fetch (pacing, breaker,
  TLS impersonation; ROE gate owns the traffic).
- FIXED (audit #10): deterministic claim verifier in save_final_report —
  every artifact reference in the report is checked against the
  workspace archive; hallucinated filenames get an UNVERIFIED
  annotation IN the sealed deliverable (tested live: real refs pass,
  fake refs flagged).
NOTED (unfixed): report_write/evidence_pack dead in CP3's session
('no active workspace' — the inherit fix landed after CP3 launched;
CP4 will validate). LLM provider died at r92 for ~10min (fleet DNS
outage) — the agent survived via retry doctrine and closed its verdict.

AUDIT SCORE: 11 of 22 findings fixed (#4 #8 #9 #12 #20 #7 #6 #1 #13
#10 + swarm bindings). Remaining: #2 real tokenizer, #3 preamble diet,
#11 concurrent dispatch, #14 ranked recall, #18 soft-fail counters,
#19 thread-keyed tap, #21 hygiene, #22 wall-sig flag.
Battery 382/382 at every step. Nothing committed (LO's law).
"""

with io.open(P, "a", encoding="utf-8") as f:
    f.write(section)
print("graft log appended:", len(section), "chars")
