# RIVALS REPORT — Six Systems Dissected, One Throne Empty

*Operation: rival recon. Six of the most dangerous open-source offensive systems
cloned into `_rivals/`, audited file-by-file, judged on whether they REALLY find.
This document is the final compilation: the verdicts, the steals, and the
Ω blueprint v2 — VOIDFORGE's road to ultimate.*

---

## I. THE SIX VERDICTS

| System | What it is | Does it find? | The wound |
|---|---|---|---|
| **sqlmap** | Detection→exploitation king (SQLi) | YES — reliably, via falsifiable probe chains | No deliberation: the loop is brilliant but knows only SQLi; nothing adaptive beyond the oracle |
| **nuclei** | Declarative detection at scale (10k templates) | YES — known signatures + blind-OOB classes | No world model, no cross-target memory, no hypothesis loop; chaining is string-passing |
| **ffuf** | Content fuzzer with calibration brain | Content, not surface — refuses to lie about noise | No concept of "interesting" beyond statistical outliers; human picks wordlists |
| **amass** | Attack-surface fixpoint graph | YES — the only one with a world-model (entities/edges/provenance/TTL) | Nothing downstream triages by confidence; name-centric, passive-heavy |
| **caldera** | Adversary emulation platform | Scripted emulation (~90-95% human-authored YAML) | The perfect memory substrate for a brain it never had; no search, no backtracking |
| **metasploit** | Exploitation framework (2k modules) | YES — fossilized human expertise, semi-autonomous rails | Module selection/option wiring/post-chaining stay operator-driven |
| **sliver** | Implant/C2 (Go) | NO — doesn't hunt; initial access out-of-band | Everything post-foothold is typed RPC: fully automatable after session zero |

**The pattern across all six: memory, execution, filtering, proof — everything
exists. Deliberation — the choosing, weighing, re-planning — exists nowhere.**
Each system's wound is a different missing organ; VOIDFORGE already has the
only organ none of them have: a live LLM decision loop (agent + MCTS + swarm
+ healer + beliefs). We are not competing with these systems. We are the
missing piece that would command all of them.

---

## II. THE STEALS (mapped to source, file-verified)

### From sqlmap (detection/oracle discipline)
1. **Calibration-first ratio oracle** — `lib/request/comparison.py` + `kb.matchRatio`.
   Never diff against the original page: learn the false-signature ratio
   (band [0.02, 0.98], verdict Δratio > 0.05) after deleting dynamically-marked
   spans (`findDynamicContent`/`removeDynamicContent`). ~80% of blind-detection
   robustness in ~300 lines.
2. **The FP truth table** — `checkFalsePositives()` (checks.py:965): three
   fresh randoms; the oracle must answer r1=r1→True, r1=r2→False, r1=r3→False,
   invalid→False. Cheap (~5 requests), kills echo/static-page FP classes.
3. **Grammar separation** — payload (pure predicates + macros) × boundary
   (quote/paren/comment context) × where (append/negate/replace). Auditable
   corpus, deterministic budget pruning.
4. **UNION statistics** — ORDER BY bisection fast-path, then outlier
   detection at average ± 7σ over similarity ratios. Not the naive NULL-walk.
5. **Timing hygiene** — ≥30 baseline samples + MAD outlier stripping before
   trusting any timing oracle (`stripTimeOutliers`).

### From nuclei (proof + traffic discipline)
6. **DSL matchers** — testable predicates over full response maps
   (`status==200 && contains(body,"root:") && size<5000`). Hypotheses become
   expressible as machine-checkable predictions.
7. **OOB lane** — self-hosted interactsh: pre-register the detection predicate
   (`RequestEvent` freezes Event+Operators before the request), re-execute it
   when third-party evidence (DNS/HTTP callback) arrives. Blind SSRF/RCE/XXE
   become PROVEN, not "probably".
8. **Cluster-before-send** — hash single-request detections by canonical
   identity; one round-trip fans out to N matcher sets. 10-50× traffic cut
   on banner checks.
9. **Per-host circuit breaker** — consecutive-failure quarantine with
   permanent-error classification; success removes, not decrements.
10. **Fail-closed variable rendering** — unresolved {{slots}} abort the
    request BEFORE sending. Firing malformed is worse than not firing.
11. **Stop-at-first-match** — execution-wide cancellation token; in-flight
    workers check the flag before each send.

### From ffuf (noise honesty)
12. **Multi-dimensional auto-calibration** — semantically-loaded nonexistent
    probes (`admin<rand16>`, `.htaccess<rand8>`); cascade size→words→lines;
    whichever scalar survives K random inputs becomes the noise filter.
    WAF soft-block pages get baselined because the probes carry the same
    words you'll fuzz with.
13. **Mission stop rails** — >95% of 50+ responses 403 → abort; >20% 429 →
    abort; transport errors > 2× threads → abort. The system knows when a
    door is closed.
14. **Matcher = filter in positive position** — one primitive, composed
    or/and, ~45 lines.

### From amass (the emergent map)
15. **Fixpoint event graph** — every discovery is a typed entity/edge with
    provenance + confidence; every discovery RE-ENTERS the handler registry
    and re-triggers discovery (cert → FQDN → NS → cert). Discovery becomes
    emergent, not sequential.
16. **TTL'd source monitoring** — the graph IS the cache; per-source cache
    windows make hourly re-runs nearly free.
17. **Wildcard detection at the resolver** — lying records never reach
    storage.
18. **Zero-confidence guessing** — aggressive Levenshtein/flip generation
    anchored on RESOLVED names, every guess tagged confidence:0, DNS is the
    truth filter. Generate aggressively, triage honestly.
19. **Durable backlog with lease semantics** — SQLite WAL, claim/ack/release,
    watermarks per asset type, fairness shuffling.

### From caldera (the memory substrate)
20. **Fact-slot templates** — capabilities are declarative templates with
    typed memory slots (#{trait}); planning = slot-filling from a shared
    fact store; a step whose fact is missing is DEFERRED, not hallucinated
    (`trim_unset_variables`).
21. **Provenant reinforced memory** — every fact carries origin_type,
    producing links, collecting agent, technique_id; a score that rises when
    the fact is USED and yields results. Credit assignment for free.
22. **Schema-learned parsers** — scan own command templates for co-occurring
    traits (≥2) → auto-extract relationship edges from arbitrary tool output.
    Sentinels flag "output looks like failure" (418).
23. **Objective predicates** — Goals {trait, value, operator, count};
    mission termination = all goals provable from memory. Countable,
    auditable, not prose.
24. **Skip-reason taxonomy** — every skipped step gets a machine-readable
    WHY (platform/executor/privilege/fact-dependency/untrusted). The
    reflection prompt pre-written.

### From metasploit (the planning surface)
25. **Check/Rank/Notes as machine-readable go/no-go** — reliability ladder
    per capability; MinimumRank as a quality floor the planner enforces.
26. **AutoCheck prepend** — verify-before-fire gate injected as policy, not
    requested.
27. **Datastore cascade** — user → global → fallback → default; determinism
    first, model second.

### From sliver (the architecture lesson)
28. **Everything post-foothold = typed RPC** — plan with knowledge, act
    through RPC. Per-binary uniqueness (canaries baked in a second render
    pass) when we ever need implant generation: the forge already has the
    piece.
29. **Durable task queue + beacon/session duality** — async tasking lanes
    for slow targets (fire-and-forget with queue, upgrade to interactive
    on demand).

---

## III. VOIDFORGE vs THE SIX — position audit

**What we have that none of them have:**
- A live deliberation loop: LLM agent + MCTS planner (attack_graph) + swarm
  coordination + healer + beliefs — 94 registered tools under one brain.
- Persistent cross-mission memory: learned_plays (grammar store + nursery),
  capability_vault, beliefs (Bayesian, revised on re-test), trajectory
  (winning-sequence bigrams), target_model.
- The forge: the platform writes its own tools mid-mission.
- Five audit waves deep of hardened infrastructure (V+W+X+Y+Z, 75 findings
  fixed, 274 tests green) — the loop doesn't lie to itself anymore.

**What they have that we lack (the gaps this report closes):**
- sqlmap's calibrated oracle: our param_brute V6 baseline is ONE dimension,
  ONE probe. No learned false-signature, no dynamicity removal.
- nuclei's OOB proof lane: our blind findings are unproven guesses.
- amass's fixpoint: our blackboard fills but nothing re-dispatches.
- caldera's fact-slots: our agent hallucinates values when prerequisites
  are missing instead of deferring the step.
- Nobody's stop rails: our mission grinds against 403 walls the way the
  pacer used to grind (pre-X3.1).

---

## IV. THE Ω BLUEPRINT v2 — four organs, one nervous system

*The original Ω vision (world model → adversarial twin → dream → doctrine)
now carries every stolen organ. Each spec below is implementable against
the existing codebase.*

### Ω1 — WORLD MODEL ENGINE (the predictor) — FIRST
**Core:** before every tool call, the agent writes a prediction
{expected status, expected shape, sentinel}; after the call, the delta is
measured. Surprise — not success — directs the mission.

**Stolen organs grafted in:**
- **sqlmap #1**: per-endpoint learned false-signatures with dynamicity
  spans removed (extends `param_brute`'s V6 baseline into a general
  `core/world_model.py`: predict/observe/surprise over ratio bands).
- **ffuf #12**: signatures are cascades size→words→lines built from
  semantically-loaded probes; WAF soft-block pages enter the baseline.
- **nuclei #10**: a prediction with an unresolved slot NEVER fires — the
  step defers (caldera #20's `trim_unset_variables` semantics).
- **amass #16**: world-model entries age on TTLs; stale predictions
  re-verify before use.
- **nuclei #6**: predictions are DSL predicates — machine-checkable,
  testable by the twin.

**Substrate:** extends `target_model.py` + `beliefs.py`; new
`core/world_model.py`. Every surprise feeds beliefs (Bayesian revision)
and the blackboard (fixpoint re-dispatch, amass #15).

### Ω2 — ADVERSARIAL TWIN (the doubter)
**Core:** every CONFIRMED verdict passes before a second LLM call whose
standing doctrine is: "this is wrong; prove it." Honeypots, canaries,
detection bait, soft-mirrors — argued, cited, forced to re-test.

**Grafted in:**
- **sqlmap #2**: the twin's standard weapon — the truth table. Three fresh
  randoms, the oracle must answer perfectly or the verdict dies.
- **MSF #25**: tools carry reliability ranks; the twin discounts low-rank
  evidence (our `honest_status` + tool reliability from trajectory get
  formalized into a rank registry).
- **nuclei #7**: when inline proof is impossible, the twin demands the OOB
  lane — a verdict is CONFIRMED-blind only with a callback.
- **MSF #26**: the twin is injected as policy (AutoCheck-style prepend on
  the verdict path), not as a tool the agent may forget to call.

### Ω3 — THE DREAM (counterfactual replay)
**Core:** between missions, re-open archived contexts, simulate the
branches not taken, cross against real responses already in the archive.
Dead time becomes training; #79's dead ends finance #80's shortcuts.

**Grafted in:**
- **caldera #21**: provenance makes replay credit-assignable — which step
  would have produced which fact.
- **amass #15/#16**: a simulated branch that "discovers" a new node
  re-triggers handlers in simulation (fixpoint inside the dream); TTLs
  keep replay results fresh.
- **trajectory**: winning-sequence bigrams feed branch selection priors.

**Substrate:** `trajectory.jsonl` + extractions + `offline_brain` (WE4)
extended into a `core/dream.py` replay lane.

### Ω4 — DOCTRINE (self-forged playbooks)
**Core:** mission autopsies write doctrine entries — rules of engagement
written by the system for the system, read at round 0.

**Grafted in:**
- **caldera #23**: doctrine entries TERMINATE on countable fact predicates,
  not prose.
- **caldera #24**: the autopsy explains every skipped step with a
  machine-readable WHY.
- **sqlmap #3**: doctrine entries are predicate × context × where triples —
  auditable, prunable by budget.
- **caldera #20**: doctrine commands carry #{trait} slots filled from the
  fact store at execution time.

**Substrate:** `skills/` + `forge` + `report` extended with
`core/doctrine.py`.

### THE NERVOUS SYSTEM (connective tissue, build-first)
These are small, independent, high-ROI — land them before the organs:
- **OOB lane (nuclei #7)**: self-hosted interactsh (a domain + poll
  endpoint). Blind classes become provable. *Build first — it changes
  what "confirmed" means for every organ.*
- **Cluster-before-send (#8)**: probes sharing a request shape collapse.
- **Per-host circuit breaker (#9)**: quarantine with cause, not martyr
  retries (extends pacer/host marks).
- **Mission stop rails (#13)**: 95%-403 / 20%-429 guards at mission level —
  the mission pivots instead of grinding.
- **Stop-at-first-match (#11)**: abort tokens propagate to in-flight probes.
- **Datastore cascade (#27)**: mission globals → tool param inheritance,
  determinism first.
- **Skip taxonomy (#24)**: the ledger records WHY steps didn't fire.

---

## V. BUILD ORDER

| Phase | What | Why first |
|---|---|---|
| 0 | Nervous system: OOB lane, stop rails, circuit breaker, cluster, skip taxonomy, datastore cascade | Small, independent, immediate mission ROI on #80+ |
| 1 | Ω1 World Model (sqlmap calibration + ffuf cascade + fail-closed slots) | The gravitational center; all other organs consume its predictions |
| 2 | Ω2 Twin (truth table + rank registry + AutoCheck injection) | Verdicts stop lying; honeypots die |
| 3 | Ω3 Dream (provenance replay + fixpoint simulation) | Dead time becomes training |
| 4 | Ω4 Doctrine (predicates + slots + autopsy taxonomy) | The loop closes: the system writes itself |

---

## VI. FINAL WORD

Six systems. Six wounds. One vacancy each — and it is always the same
vacancy: **deliberation**. sqlmap has the oracle without the planner,
nuclei the proof without the prediction, ffuf the filter without the
judgment, amass the map without the triage, caldera the memory without
the search, metasploit the expertise without the autonomy, sliver the
action without the hunt.

VOIDFORGE has had the deliberation since day one. What the six give us —
freely, file by file, line by line — is everything AROUND it: the sensory
discipline, the proof channels, the memory substrate, the honesty
mechanisms. Graft the organs onto the brain, and the platform stops being
a very good executor. It becomes the thing none of them could be:

**The driver they were all built to wait for.**

*Audit sources: `_rivals/{sqlmap,nuclei,ffuf,amass,caldera,metasploit-framework,sliver}`
— every claim in this report is backed by the per-system audit reports
delivered this session, each anchored to files and line numbers in those
checkouts. Full metasploit+sliver teardown: `rival-audit-msf-sliver.md`.*
