MISSION BRIEF — VOIDFORGE ENGAGEMENT #77
══════════════════════════════════════════

TARGET: venice.ai (+ outerface.venice.ai, api.venice.ai, clerk.venice.ai)
PRIMARY: https://venice.ai/checkout/plus/monthly

IMPACT SCENARIOS (the mission's real objective — invert each into
invariant candidates and test them with the science engine):

1. PAY $0 FOR PRO — a paying customer completes the Plus/Pro subscription
   flow and the money actually charged is $0 (or refunded instantly),
   while the account receives and KEEPS the paid tier. End-state proof:
   post-purchase account state showing the tier + the charge/receipt
   showing $0.

2. ENTITLEMENT WITHOUT PURCHASE — an account that never paid holds Pro
   entitlements (models, limits) after logout/re-login. End-state proof:
   authenticated call to a Pro-only resource succeeding, + subscription
   API showing no active paid subscription.

3. TIER SMUGGLING — a free-tier subscription session carries Pro-tier
   entitlements through the checkout session handoff (checkout_session,
   stripe cs_live tokens, x402 balances). End-state proof: the
   differential between what was ordered and what was granted.

ENGAGEMENT STYLE — IMPACT-FIRST (rule 13):
- hypothesis_test IS THE CORE WEAPON. Every "the server must check X"
  belief becomes a controlled experiment: baseline + ONE mutation +
  oracle + direction. REFUTED held-hypotheses = the finding.
- differential_sweep IS YOUR THROUGHPUT: ids to walk, prices to tamper,
  encodings to try — delegate the value space, read the science table.
- The TARGET MODEL + TARGET SCIENCE LEDGER blocks in your context carry
  every endpoint grammar and every tested belief from missions 71-76:
  NEVER re-derive a tested fact. Push the CONFIRMED leads deeper.
- Known-proven from history (do NOT re-prove): x402 payment flow hardens
  (402 discipline), JWT alg variants rejected, checkout sessions are
  live Stripe cs_live objects.
- Known Open leads from run 76: siwx challenge 402 windows, entitlement
  drift after session handoff, the promo/coupon code path (never touched).

RULES OF ENGAGEMENT: standard operator mandate (engagement.yaml),
aggressive intensity, direct egress, do_not_exploit=false. Operator
account on venice.ai is OURS — the $0-purchase scenario runs on the
operator's own test account, self-attestation IS authorization.

DELIVERABLE: engagement report + findings dossier. FINDINGS carry
DEMONSTRATED end-states (rule 8) — a tampered session that expires
unused is a note, not a finding. Seal every confirmed chain with
evidence_pack. Close with the NEXT MISSION PROPOSAL.
