# MISSION MADL-CAMP1 — MADLEETS.ME PRODUCT EXTRACTION CAMPAIGN

## TARGET
madleets.me — security forum with VIP zones, pro tools, pro methods,
VIP methods. Community content behind authentication walls.

## OBJECTIVE
Extract the premium content: VIP zone threads, pro tools (shared
software/scripts), pro methods (technique write-ups), VIP methods.
Map what the walls are, then go through them, around them, or
through the wall's other side.

## DOCTRINE
- The vendor's own infrastructure leaks its product: sales channels,
  shared CDN URLs, cached variants, API responses that differ between
  anonymous and member contexts.
- Interpretation-differential: test where two components disagree —
  member-only routes that render anyway for crawlers, APIs that
  trust client-supplied role claims, redirect chains that leak
  authenticated content.
- Race the wall: parallel requests at the moment access is granted —
  the window between grant and re-check.
- The campaign runner: PLAN (recon-only planner) → SWARM (parallel
  chains, fresh contexts) → VERIFY (probe-lane verifier).

## BUDGET
- Campaign rounds: standard
- Stop when: premium content extracted OR all chains report walls
  with NEXT-LEAK-AXIS mapped
