# VOIDFORGE :: SYSTEM_MAP 15 — THE NEW ERA ARCHITECTURE (2026-09-06)

The premium upgrade session. Three inputs converged: the AI-hacking
research report (SYSTEM_MAP/13 — full annotated 255-line version),
the threat-intel catalog (SYSTEM_MAP/14), the brutal 22-finding
internal audit. What shipped this session:

## SHIPPED (live-verified, battery 382/382)

1. **GRIMOIRE 1.5.0 — the DIFF domain** (141 techniques / 12 domains).
   84 interpretation-differential techniques grafted from the live
   research catalog: TE.0 smuggling, Apache Confusion, WorstFit, cache
   deception/poisoning chains, Next.js _next/data chains, session
   puzzling, race states, DOM clobbering, shadow APIs, prototype
   pollution gadgets, JWT confusion, OAuth non-happy-paths, device-code
   phishing, cookie tossing, secret archaeology (GitHub forks, Docker
   layers, Wayback, sourcemaps), MCP poisoning, agent sandbox escapes,
   memory poisoning, indirect injection exfil, ZombAIs, HTML-to-markdown
   hidden instructions. Every record carries its recon-signal trigger in
   the detection field. THE META-DOCTRINE: "scanners test what a request
   does; the new era tests what two components DISAGREE about."

2. **MCTS planner in LIVE missions (audit #4 CRITICAL fix)**: the
   offline brain planned only when the LLM was dead. Now EVERY mission
   round-0 receives an MCTS TACTICAL PLAN (8-step highest-Q chain from
   extract_state) as its opening book — the agent keeps command, the
   plan is the lookahead it never had. Live missions stop being pure
   round-by-round reaction.

3. **Adversarial twin widened (audit #9 CRITICAL fix)**: the verifier
   fired on exactly one whitespace-sensitive substring. Now every
   CONFIRMED strike structure (OOB callbacks, exploitables, BOLA/leak/
   breach/bypass claims) passes the standing challenger before riding
   into the report. Aligned with the research verdict: "the field
   converged on verification as the unlock — build the verifier before
   the attacker."

4. **Tool deadline watchdog (audit #12 HIGH fix)**: no tool call may
   block >180s — a hung browser/network loop can no longer freeze the
   mission while the operator abort inbox sits dead.

5. **attack_graph dup-key fix (audit #8 HIGH fix)**: TWO data_extract
   nodes — the dict silently kept the weak one (yield 3.0), the
   Bearer-token strike (5.5) was deleted. Merged: token+endpoint =
   authenticated strike (the offline brain regains its best move).

6. **Campaign runner (lab/_calib_campaign.py)**: the 3-phase premium
   flow — PLAN (recon-only agent maps + emits chains JSON) → SWARM
   (PlannedSwarm parallel specialists, each with its own fresh context)
   → VERIFY (adversarial verifier attacks our own work). The dormant
   PlannedSwarm is now reachable from the calib lane. Smoke-tested.

## THE RESEARCH VERDICT (what the field says, 2024-2026)

- Wave 3 (XBOW, Big Sleep, AIxCC) = verification-and-memory
  architectures wearing a model as engine. The moat is the HARNESS.
- MCTS-for-hacking remains rare in public literature — our attack-
  graph MCTS with exploitability priors is an open lane nobody claims.
- Auth walls are the single biggest practical blocker (matches our
  duskyr Telegram wall exactly — CISA's default-password push is the
  quiet acknowledgment).
- Known failure modes we already counter: context rot (workspace
  archive + compaction), noisy recon (hints + elide-to-extractions),
  false positives (twin), long-horizon collapse (MCTS opening book +
  doctrine plays).
- Steal-list alignment: PoV-gated everything (#3 fix), ledger/
  blackboard (mission workspace), IR adapters (elide+archive), skill
  library compounding (doctrine + vault + plays).

## NEXT MOVES (ranked)

1. First live CAMPAIGN on a real target — prove PLAN→SWARM→VERIFY
   end-to-end (the architecture is wired and smoke-tested).
2. Procedural skill library: verified chains → parameterized plays
   (Voyager pattern) — the plays store exists, the harvester is thin
   (24 plays for 10 missions — post-mission minting needs a boost).
3. n-beam diverse attempts (Fang et al.): forge_tool already gives
   diversity; a beam-budget doctrine rule would formalize it.
4. Model routing tiers: glm-5.3-flash triage, premium chain assembly
   (the provider fleet already swaps endpoints — extend to per-phase
   model choice).
5. Auth-wall playbook module (research #8): the duskyr Telegram wall
   experience distilled into a reusable doctrine entry class.

## CAMPAIGN PROOF + AUDIT WAVE 2 (same session, evening)

- CP1 (solo-fallback, 43 rounds, 105 calls): 8 findings confirmed —
  XFF geo-spoof trusted end-to-end on both twins, race_smash 40/40
  double-processing, h5_event plaintext ingestion, tenant access_id
  never-expiring credentials in open catalogs. The DIFF doctrine
  lanes (SQLi/smuggling/proto-pollution) held with proof — wall
  verdicts are intelligence too.
- CP2 (full 3-phase, 72 min): PLAN sealed 11,360 chars / 8 chains →
  PlannedSwarm ran 4 parallel chains with FRESH contexts (the
  long-mission rot cure: 5 windows instead of 1 rotting window) →
  adversarial verifier engaged (2 provider refusals absorbed).
  Chain strikes: most_viewed full grammar → 55KB cross-user PII;
  forged byte-exact AES-CBC telemetry ACCEPTED 200 (90/90 race,
  zero rate-limit); FIPS-197 self-vindication discipline; per-video
  secretKey honestly named as APK-channel-delivered (missing link);
  backend tightening caught live (size max 30, twins in lockstep).
- AUDIT FIXES WAVE 2 (7 findings closed, battery 382/382 each step):
  #20 LLM stale-resp fleet bug, #7 mission-scoped dedup memory,
  #6 planner harvesters (Set-Cookie, sb_secret, host facts, email-as-
  handle regex bug), #1 episodic digest every 10 rounds (the context-
  rot cure — the audit's #1 CRITICAL), plus wave-1's #4 MCTS-live,
  #9 twin widening, #8 dup-key, #12 deadline watchdog.
- Fleet bugs noted for next session: chain workspace binding (evidence_
  pack dead inside chains), verifier target binding (bound a stale
  workspace), sqli_tamper GET-plane on POST-only routes, differential_
  sweep healer TIMEOUT noise.
- The research's own steal-list maps 1:1 onto what shipped: PoV-gating
  (twin), plan-object (MCTS + campaign), memory compounding (episodic
  digest + doctrine + vault), generator-verifier (phase C), IR
  discipline (elide-to-extractions). The MCTS-for-hacking open lane
  from the literature: claimed, wired, and live-proven in CP2.
