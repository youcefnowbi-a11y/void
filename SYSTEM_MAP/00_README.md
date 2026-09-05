# VOIDFORGE SYSTEM MAP — THE ORGANISM'S MEMORY

This map is the durable memory of the whole platform: every organ, every
graft, every invariant, every feedback loop. Audit waves READ this map
then verify against the real code. When you finish reading all files in
SYSTEM_MAP/ you hold the complete logic of the system in your head —
then you can think with it and find what makes it weak.

## PRIME LAW (P0 — LO's law, read this first, always)
**There is NO perfect system, NO 100% locked system.** Every "locked",
"perfect", "solid" system has leaks nobody knows yet — our job is to
FIND them, BUILD the systems that use them, and PROVE it. A HELD gate
is a phase marker, never a finish line: known vectors closed means the
hunt for UNKNOWN leaks continues (next plane, next edge, next session).
See 10_invariants.md § PRIME LAW for the fleet-wide consequences.

## How to read this map
- Read in order: 01_architecture → 02_nervous_system → 03_world_model →
  04_twin → 05_dream → 06_doctrine → 07_agent_loop → 08_transport →
  09_registry_chokepoints → 10_invariants → 11_risk_zones → 12_graft_log
- Every file names the REAL source paths it describes. Truth = code,
  map = navigation. If they diverge, the CODE wins and the map is wrong.
- The graft log (12) is the living history: what was added, why, what
  bug it fixed. New work appends there.

## The one-paragraph organism
VOIDFORGE is an autonomous offensive-security agent platform: an LLM
agent loop (core/agent.py) that plans and fires tools (tools/ registry,
94+ tools) at scoped targets, an intelligence graph (core/blackboard.py)
that fuses every observation into a living map, a trajectory archive
(core/trajectory.py) that remembers which sequences won, and — since the
Ω-wave — four new organs: a world model that measures surprise (Ω1), an
adversarial twin that challenges every confirmed verdict (Ω2), a dream
that rehearses untaken branches between missions (Ω3), and a doctrine
that writes self-authored rules from every failure (Ω4). All wrapped in
a nervous system (Phase 0) that stops grinding walls (rails), quarantines
dead hosts (breaker), coalesces duplicate flights (coalescer), accounts
for every skipped call (skip ledger), cascades session context
(datastore), and proves blind findings out-of-band (OOB channel).

## File map (the map's map)
01_architecture.md      — the big picture, data flow, process boundaries
02_nervous_system.md    — Phase 0: rails, breaker, coalescer, ledger,
                          datastore, OOB channel — files + semantics
03_world_model.md       — Ω1: prediction contract, calibrated comparator,
                          noise floors, TTL store, surprise map
04_twin.md              — Ω2: truth table, blind policy, ranks, LLM call
05_dream.md             — Ω3: provenance, replay lane, fixpoint, plays
06_doctrine.md          — Ω4: entries, goals, skip-taught, Bayesian retire
07_agent_loop.md        — the mission loop round by round, every graft
                          point in execution order
08_transport.md         — fetch pipeline: cache, coalesce, breaker,
                          redirects, proxies
09_registry_chokepoints.md — tools.execute() gates in exact order
10_invariants.md        — THE LAWS: things that must never break
11_risk_zones.md        — where bugs historically lived + fragile seams
12_graft_log.md         — append-only history of this campaign
