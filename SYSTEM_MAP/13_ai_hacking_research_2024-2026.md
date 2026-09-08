# Offensive AI/LLM Agents — Research Report 2024–2026
**For: system upgrade planning. Focus: architectural ideas worth stealing, with sources.**
*Compiled from arXiv/USENIX/industry material. Numbers marked ≈ are from collected notes and memory of the papers — solid directionally, spot-verify exact figures before citing externally. Self-reported vendor numbers are flagged as such.*

---

## 0. The landscape in one screen

Three waves, ~8 months apart:

1. **Wave 1 — Tool-wrapped chatbots (2023–24):** PentestGPT, HackingBuddyGPT. LLM as reasoning core, human-ish scaffolds. Solve ≈30–44% of easy HackTheBox boxes vs ≈13% raw GPT-4.
2. **Wave 2 — Real agents + real benchmarks (2024–25):** EnIGMA, Cybench, NYU CTF, AutoPwn, CVE-Bench, CyberGym. Agentic loops, IR layers, judge scaffolds. One-day CVE exploitation: ≈37% in 5 min / ≈58% with 20 attempts; web-CVE exploitation jumped ≈27% → ≈88% when frontier reasoning models met tuned harnesses.
3. **Wave 3 — Verified multi-agent systems (2025–26):** XBOW, CAI, Google Big Sleep, DARPA AIxCC. Specialized agent roles + executed-proof verification + accumulated vuln memory. XBOW topped the HackerOne US leaderboard (May 2025, self-reported); Big Sleep found a real SQLite 0-day before release.

**Thesis to steal:** the moat in 2025–26 is **not the model** — it's the **harness**: task decomposition, context discipline, memory, and *verification grounded in executed proof*. Every system that made headlines is a verification-and-memory architecture wearing a model as its engine.

---

## 1. Key papers & systems, annotated (idea → power → numbers)

### 1.1 Full-chain autonomous pentest agents

- **PentestGPT** (Deng et al., USENIX Security 2024; arXiv:2308.06782)
  - **Idea:** split the LLM into *reasoning* / *generation* / *parsing* modules, and keep a two-level task list — a **global todo-tree** (HTN-style plan of the engagement) plus a **local task list** (current sub-attack). Tool output is abstracted/summarized before re-entering context.
  - **Why powerful:** first to show context management (not intelligence) was the binding constraint on long attack chains.
  - **Numbers:** ≈44% success on HTB with instructor hints, ≈30% independent, vs ≈13% raw GPT-4.
  - **Steal:** the todo-tree as a persistent, resumable plan artifact; abstracted tool output ("IR-lite").

- **HackingBuddyGPT** (Müller et al., Univ. of Bonn; arXiv:2403.10825)
  - **Idea:** *tiny* agentic loop — one small LLM, one tool, raw stdout/stderr feedback, context kept deliberately minuscule; narrow the task (e.g., Linux privesc only).
  - **Why powerful:** proved small/local models beat giant agents when the context is pruned to only decision-relevant state. Anti-bloat manifesto.
  - **Numbers:** solves the majority of Linux privesc boxes within ≈10–20 iterations, no human input.
  - **Steal:** context starvation as a feature — aggressively filter what enters the model's window per decision.

- **EnIGMA** (UC Berkeley, 2024; arXiv:~2406.14148)
  - **Idea:** **Intermediate Representations (IR)** for tool output — a GDB wrapper that serializes debugger state into compact, LLM-digestible structures; agent writes **code actions** (pwntools exploit scripts) instead of JSON tool calls.
  - **Why powerful:** directly attacks context rot and output-parsing brittleness — the two things that kill long pwn chains.
  - **Numbers:** top-of-class scores on the NYU CTF agent benchmark at publication.
  - **Steal:** every noisy tool gets an IR adapter; exploit attempts emitted as code, not chat.

- **PentAG** (2025; arXiv:~2501.01467)
  - **Idea:** methodology-aware agentic pentesting — attacker/recon agent split, planning coordinator, **MITRE ATT&CK as the task graph** guiding decomposition.
  - **Why powerful:** plans become auditable and resumable because steps map to a public methodology instead of free-form prose.
  - **Numbers:** outperforms AutoGPT-style baselines on vulnerable-VM suites (reported).
  - **Steal:** ATT&CK-anchored decomposition for traceability + a shared attack graph as blackboard.

- **PenTest++** (2025; arXiv:~2506.02207 — verify ID)
  - **Idea:** "fully autonomous + standardized" — hierarchical, parameterized task templates and standardized I/O contracts between pentest steps.
  - **Why powerful:** turns pentest knowledge into a typed workflow the agent can't drift from; strong HackTheBox results vs GPT-4o baseline (wide margin, reported).
  - **Steal:** typed step contracts (inputs/outputs/success predicates per tactic) — the anti-drift device.

- **AutoTopEnBench** (2025; Univ. of Pisa group)
  - **Idea:** benchmark on VulnHub boxes comparing *planner styles* (ReAct vs structured planning) for pentest agents.
  - **Steal:** evaluate planner architectures separately from models — the harness is the variable.

- **PentestGym** (2025)
  - **Idea:** gym environments for full exploit-chain RL (recon→foothold→privesc→pivot), reward-shaping testbed.
  - **Steal:** an attack-chain RL substrate for research into dense rewards; few public equivalents exist.

- **AutoAttacker** (2024; arXiv ~2410.18722 — verify ID)
  - **Idea:** LLM agent that chains Metasploit modules for automated post-exploitation against a controlled network.
  - **Steal:** the action space as framework modules (typed, composable) rather than raw shell.

### 1.2 Exploitation & vulnerability-discovery agents

- **"LLM Agents can Hack Websites"** (Fang et al., UIUC; arXiv:~2405.17166)
  - **Idea:** agents with *only* a browser (no bespoke tools) exploit known web vulns — CTF-style targets per vuln class.
  - **Numbers:** ≈18%–73% success by class (XSS lowest, CSRF/SQLi higher); no tools required.
  - **Related (same group, 2023–24):** LLM-assisted exploit generation + dynamic analysis found **2 real zero-days** in widely used software.
  - **Steal:** browser-as-universal-tool keeps the action space small; and *diverse sampling* (multiple attempts, varied temperatures) is what found the 0-days.

- **"Agentic Exploitation of One-Day Vulnerabilities"** (a.k.a. the AutoPwn-style result; Hao Chen et al., UCSB, 2025; arXiv:~2505.11614)
  - **Idea:** agent reads a public **advisory** and builds a PoC against the real vulnerable software in a sandbox; the advisory itself is the semantic memory.
  - **Numbers:** ≈37% of CVEs exploited within 5 minutes, ≈58% with 20 attempts; discovered **11 zero-days** in the process.
  - **Steal:** advisory→PoC as a product loop; the insight that the model doesn't need to "know" the CVE, it needs to *read and re-derive* it. Also: honest measurement of attempt-budget sensitivity.

- **CVE-Bench** (2025; arXiv:~2501.08435)
  - **Idea:** fully automated benchmark — real CVEs spun up in live Dockerized apps, auto-graded by impact.
  - **Numbers:** agent harnesses ≈27% initially; **Anthropic-reported ≈88%** for Claude 3.7 Sonnet in a tuned harness (Mar 2025). The delta between those two numbers is pure harness engineering.
  - **Steal:** auto-graded, live-CVE CI loop as an internal capability tracker.

- **CyberGym** (2024; arXiv:~2405.00751)
  - **Idea:** 1,681 vulnerable/fixed program pairs from 140 OSS projects; LLMs judge vulnerability presence given pre/post-patch code.
  - **Numbers:** ≈50–60% detection for frontier models *when given both versions*; far lower with only the vulnerable version.
  - **Steal:** diff-conditioned reasoning (patch-aware review) as a bug-hunting prompt pattern.

- **VulnBot** (2025; arXiv:~2505.16132)
  - **Idea:** a *team* of LLM agents doing triage-guided hunting over large real codebases (static analysis guides where agents read).
  - **Numbers:** found known vulns at scale plus previously unknown issues in major OSS (reported).
  - **Steal:** static analysis as the scout, LLM agents as the interrogators — halves token cost and false-positive noise.

- **Google Big Sleep** (Project Zero + DeepMind, 2024–25; blog/technical reports)
  - **Idea:** **generator–reviewer adversarial pair** — one model (re)writes/exercises code variants, a second model reviews for vulnerability classes, hypotheses verified against build/test.
  - **Numbers:** found a **previously unknown SQLite bug (0-day) before release** (Oct 2024); several more in 2025.
  - **Steal:** variant-based hypothesis generation + independent reviewer; bug classes as prompt priors.

- **LLM-powered fuzzing** — **Fuzz4All** (ICSE 2024; arXiv:~2406.10367), **OSS-Fuzz-Gen** (arXiv:~2407.11385), Google "AI-powered fuzzing" (2024, OpenSSL/SQLite bug hauls incl. CVEs), **AgentFuzz** (arXiv:~2410.07808, fuzzing OS/autonomous agents).
  - **Idea:** LLMs write fuzz targets/harnesses for code traditional fuzzers can't reach; coverage acts as an *intrinsic, machine-checkable* reward.
  - **Steal:** coverage feedback as a dense reward channel for agent exploration (the cheapest trustworthy reward in security).

- **DARPA AIxCC** (2023–2025; finals at DEF CON 33, Aug 2025)
  - **Idea:** autonomous find-and-patch at real OSS scale; systems built as **attack agent / repair agent / verifier triads** with a formal **Proof-of-Vulnerability (PoV)** program that must demonstrate impact; sanitizer-grounded (ASan etc.) verification; CWE taxonomy for scoring.
  - **Numbers:** 7 finalists from ~100+ qualifying teams (2024); $10M+ prize pool; champion reported as Georgia Tech-affiliated team ARVA (verify current standings).
  - **Steal (big one):** PoV as the universal success criterion — nothing counts unless a program *demonstrates* the bug. Build your verifier before your attacker.

### 1.3 CTF benchmarks & evaluation science

- **NYU CTF benchmark** (arXiv:~2406.05590): 200 CSAW challenges; best agents ≈10–20% solve vs ≈70%+ for top human teams. Finding: agents die on multi-stage chains, not single steps.
- **Cybench** (Stanford, 2024; arXiv:~2408.08926): 40 professional CTF tasks, judge scaffold, exploit-strategy prompting. Key result: **o1-preview class reasoning models lift solve rates substantially over GPT-4o; multi-LLM ensembles ≈37%** — test-time compute and diversity both scale hacking.
- **LLM CTF Arena** (2025; arXiv:~2503.11948): **procedurally generated** sandbox challenges. Key finding: static CTF benchmarks are **contaminated** (write-ups in training data) and agents take **shortcuts** (flag-grepping without the intended exploit). Procedural generation fixes both.
- **InterCTF** (Stanford, 2025): team-vs-team LLM CTF battles. Finding: *heterogeneous model teams* coordinate and beat single models; inter-model communication protocols matter.
- **HackTheBox AI-vs-human community events (2024–25):** humans still win multi-stage engagements; AI dominates single-vuln speed rounds.

### 1.4 Threat-intel RAG / agentic retrieval

- **TRAM** (2024; arXiv:~2407.01853): LLM pipeline mapping raw CTI reports → MITRE ATT&CK techniques with human-in-the-loop verification tiers.
- **Agentic-RAG CTI pattern (2024–25, multiple industry systems):** RAG over CVE/CWE/ATT&CK corpora with **structured extraction into a knowledge graph** (entities: actor, TTP, vuln, asset; edges: uses/exploits/targets), then multi-hop queries. Industry instances: Microsoft Security Copilot, Google Threat Intelligence (Gemini), Recorded Future Intelligence Graph.
- **PhantomWiki** (2025; arXiv:~2506.14800): **procedurally generated fictional corporations** (consistent synthetic wikis) to benchmark agentic multi-hop retrieval with zero contamination.
  - **Steal:** synthetic-org generation is a perfect substrate for *recon/reasoning training* and for threat-intel RAG evals — no leakage, controllable difficulty, and it doubles as corporate-recon simulation.
- **Known RAG failure mode:** hallucinated CVEs/CWEs in tool-augmented CTI answers (multiple 2024–25 studies) — mitigation: constrained generation over a canonical vuln ID list + retrieval-grounded citations.

### 1.5 Industry systems & programs (the state of practice)

- **XBOW** (2024–, autonomous pentesting startup)
  - **Architecture (per their engineering posts):** specialized multi-agent roles (recon/discovery, analysis, exploitation, validation) driving real browsers/computer-use; a **retrieval-augmented vulnerability knowledge base** accumulated from every scan (validated findings become reusable memory); a validation agent re-tests every candidate before reporting.
  - **Results (self-reported):** first autonomous AI to top HackerOne's US leaderboard for a month (May 2025); valid vulnerabilities found on the order of minutes; thousands of validated vulns accumulated across engagements; topped an academic web-security benchmark previously led by Google Big Sleep.
  - **Steal:** findings-DB-as-procedural-memory + mandatory re-test before report — the triage firewall against false positives.
- **CAI — Cybersecurity AI** (open source, Alias Robotics, Feb 2025)
  - **Architecture:** minimal hardcoded logic; an LLM reasoning core (pluggable model) + 100+ security tools; flexible single/multi-agent compositions; interactive human-on-the-loop mode.
  - **Results (self-reported):** topped the NYU CTF agent leaderboard at release, ahead of prior reported agent SOTA including XBOW's published results; per-challenge cost in the dollars range.
  - **Steal:** reasoning-core purity — framework code only routes context and tools; all judgment lives in the model. Plus cost accounting per mission as a first-class metric.
- **Anthropic "Claude for Cybersecurity" / agentic pentesting (2025):** computer-use-based agent running Kali-style tooling in containers; partners incl. XBOW; benchmark PR rode the CVE-Bench ≈88% number.
- **Microsoft Magentic-One** (arXiv:~2411.04468): generalist orchestrator + specialist agents (web/terminal/file) with a **persistent ledger** of facts and a task ledger, two-phase (plan → iterate) replanning. The orchestrator pattern most worth copying wholesale.
- **Horizon3 NodeZero / Pentera:** non-LLM-first autonomous pentest platforms now bolting on LLM reasoning — proof that autonomous *platform* logic is mature; the LLM layer adds adaptive exploitation.
- **US Gov signal:** NSA 2025 "Impact of AI on the Cyber Threat Landscape" assessments project **autonomous end-to-end offensive agents within ~5 years**; CISA's late-2025 push to ban default passwords is (quietly) an acknowledgment that auth walls are the last cheap defense against agent scanning.

---

## 2. What separates an intelligent agent from a scripted tool-runner

Five axes, in order of observed impact on hacking capability:

### 2.1 Planning architectures
- **Decomposition (HTN/todo-trees):** PentestGPT's global+local task lists; PenTest++'s parameterized hierarchies; Magentic-One's task ledger. Scripted runners have a static checklist; agents have a *plan object* that survives context loss.
- **Search over alternatives:** Tree-of-Thoughts (arXiv:2305.10601), Graph-of-Thoughts (~2308.09687) — and in security, the evidence that **n-beam diverse attempts beat one greedy chain** (Fang et al. 0-days; Cybench multi-LLM ≈37%). MCTS-for-hacking remains rare in public literature — an open lane (attack-graph MCTS with exploitability priors is unclaimed).
- **Formal planning + LLM translation:** LLM+P (arXiv:~2304.11477) and LLM-Modulo (Kambhampati, ~2402.01817) — translate natural-language goals into PDDL, hand to a classical planner, execute. Almost no public hacking agent does this; attack graphs (MulVAL-style) + LLM-Modulo is a genuinely novel combination.
- **World model:** maintain explicit belief over the target — services, creds held, footholds, pivot topology — updated by IR-serialized observations (EnIGMA; RAAP-style augmented world models for web agents). The gap between "agent" and "script" is exactly this: a script has no belief, just a pipeline.

### 2.2 Memory systems
- **Episodic:** Reflexion (arXiv:2303.11366) — verbal self-critique stored as mission retros; "what I tried and why it failed" logs prevent loop repetition. Generative Agents (2304.03442) — retrieval over timestamped event streams.
- **Semantic:** XBOW's vuln database; AutoPwn's advisory conditioning; ATT&CK graphs (PentAG) — knowledge *about the domain*, retrieved on demand.
- **Procedural:** **Voyager's skill library** (arXiv:2305.16291) — verified capabilities compiled into reusable, parameterized code — maps 1:1 to "every verified exploit chain becomes a callable script." MemGPT (2310.08560) tiered memory; Agent Workflow Memory (~2409.07429) induces cross-mission workflows; Mem0 (~2504.19413) for operational recall.
- **Rule of thumb from the literature:** episodic memory is cheap and underused; procedural memory is where compounding lives — systems that cache *verified* chains get measurably cheaper and faster per mission (XBOW).

### 2.3 Self-reflection & self-correction
- Self-Refine (2303.17651), CRITIC (2305.11738): critique-and-revise loops on *plans* before execution.
- In hacking specifically, correction must be **differential**: when a PoV fails, revise the payload/params (local fix), don't re-plan from scratch — the Cybench "exploit strategies" and EnIGMA code-action designs both embody this.
- R-Judge (arXiv:~2401.10019): agents judging their own trajectory safety/relevance hit only ≈45% F1 (humans ≈95%) — self-judgment is the *weakest* reflection channel; external verification is the strong one.

### 2.4 Verification — the actual unlock
- **The pattern across every Wave-3 success:** claims are worthless until an *environment* confirms them — AIxCC's PoV programs under sanitizers, XBOW's re-test loop, Big Sleep's generator-reviewer, CVE-Bench's auto-grading, LLM CTF Arena's procedural grading.
- Design rule: **LLM confidence is never evidence.** Success predicates must be machine-checkable state deltas (flag file read under the intended path, privilege change, exfiltrated marker, PoV exit).

### 2.5 Curiosity & exploration
- **ECOLI (2024):** episodic-curiosity RL agent for pentesting — intrinsic reward for *novel state* (new service, new credential, new permission) — beat baseline agents on HackTheBox-style ranges.
- Fuzzing precedent: coverage as intrinsic reward (AFL) → the agent analog is **attack-graph coverage**.
- Frontier LLM agents do greedy first-idea exploitation; **diversity sampling** (temperature beams, varied hypotheses) demonstrably finds more bugs (Fang et al.).

### 2.6 Reward shaping for hacking tasks
- **Sparse terminal rewards (flags) are insufficient** — all benchmark papers agree on long-horizon collapse.
- Dense, trustworthy reward channels, ranked by trust:
  1. PoV/flag pass-fail (binary, perfect trust — AIxCC pattern)
  2. State deltas: `id` change, new port/service, credential accepted, attack-graph node unlocked (Cybench/CyberGym-style intermediate predicates)
  3. Coverage metrics (recon/attack-graph %, fuzzing coverage) — cheap, gameable, use as auxiliary only
  4. LLM-judge rubrics (Cybench judge; R-Judge precedent) — dense but weakest trust; never sole reward
  5. Curiosity intrinsic (ECOLI) — for exploration phases, not reporting
- **Reward-hacking countermeasures:** procedural generation of targets (LLM CTF Arena) so flags can't be grepped; bind rewards to intended exploit path.

---

## 3. Multi-agent orchestration patterns that work (with evidence)

1. **Orchestrator + specialists** (Magentic-One; XBOW; MetaGPT, arXiv:2308.00352)
   A coordinator holds the **ledger** (facts, plan, progress) while role-specialists (recon/exploit/verify) run in isolated contexts. Works because context isolation per role beats one giant transcript. *Steal: a shared ledger object updated by all roles.*

2. **Generator–verifier adversarial pairs** (Big Sleep; AIxCC attack/verifier triads; XBOW validation agent)
   One agent hypothesizes/executes, an independent agent (ideally non-LLM: sanitizer run, PoV exit) falsifies. Highest signal-per-token pattern in the whole literature. *Steal: never let the proposer be the judge.*

3. **Red-team debate / plan critique** (Multiagent Debate, arXiv:2305.14325; InterCTF team coordination)
   Agents argue attack hypotheses before committing tokens to execution — catches dead-end chains early. *Steal: a "skeptic agent" that must sign off on each chain plan.*

4. **Swarm / ensemble attack** (Cybench multi-LLM ≈37%; Fang et al. diverse sampling; Meta's Rainbow Teaming, ~2402.12297, evolutionary open-ended red-teaming)
   N diverse attempts + auto-verifier beats one deep attempt at equal budget. *Steal: n-beam exploitation with verifier arbitration.*

5. **Shared blackboard memory** (MetaGPT message pool; Magentic-One ledger; classic blackboard systems)
   Structured shared state (attack graph, findings DB, session scratchpad) that every agent reads/writes. *Steal: findings DB as the system's spine.*

6. **Hierarchical model routing** (industry pattern: CAI pluggable models; XBOW multi-model)
   Cheap/fast models triage noise (recon output, log diffs); frontier models do chain assembly and exploitation. Cost per finding drops an order of magnitude. *Steal: token-tier routing.*

7. **Human-on-the-loop breakpoints** (HackingBuddyGPT interactive mode; CAI interactive)
   Predefined decision points (credential use, destructive actions, auth walls) escalate to a human. *Steal: escalation triggers.*

8. **Team-of-heterogeneous-models** (InterCTF)
   Different families as team members coordinate tactics — diversity in reasoning styles acts as an ensemble across the whole mission, not just one step.

**Anti-pattern (documented):** flat co-pilot chat with tools (Wave 1) — context rot + no plan object + no verification. Every 2025 system that works is structured.

---

## 4. Known failure modes of AI hacking agents (with sources)

1. **Long-horizon planning collapse.** Solve rates fall off a cliff when a task needs >≈6 chained steps (Cybench; NYU CTF: ≈10–20% vs humans ≈70%+; Apple's "Illusion of Thinking," ~2506.06969, shows general complexity-collapse). Agents abandon multi-stage chains mid-way; todo-trees mitigate but drift still occurs (PentestGPT's own analysis).
2. **State tracking / belief errors.** Agents forget prior actions and re-scan, or hold false beliefs about target state ("why do web agents fail" analysis, arXiv:~2503.14165: largest category is implicit-reasoning errors ≈40%); stale port/version assumptions trigger wrong exploits (AutoPwn's mismatch findings). No persistent world model in most systems.
3. **Authentication walls.** Benchmarks stall when challenges require credentials (NYU CTF web-auth categories, near-zero); agents can't phish/cred-hunt within scope rules; human-on-the-loop needed (HackingBuddyGPT/CAI interactive modes). This is the single biggest practical blocker in real engagements — and why CISA's default-password ban is meaningful.
4. **Noisy recon drowning context.** nmap/nuclei/reconFTW-pipeline output floods the window; agents lose the actual attack state in tool spam (EnIGMA's IR layer exists precisely for this; HackingBuddyGPT's context starvation ditto). Recon needs a *triage* role before a *reasoning* role.
5. **False positives / unverified claims.** LLMs assert exploitation success without proof; vuln claims flood triage (HackerOne reported a surge of AI-generated bounty reports in 2025, low validity rate); PoV-gated reporting (AIxCC/XBOW) is the proven countermeasure.
6. **Context rot over long missions.** Lost-in-the-middle (arXiv:2307.03172) + "Context Rot" (2025) — long-context accuracy degrades mid-window and over long sessions; flag found early then lost from attention; summarized history drops load-bearing details (NYU CTF agent resets; every Wave-2 paper notes this).
7. **Benchmark contamination & shortcut-taking.** CTF write-ups in training data; agents grep flags instead of exploiting (LLM CTF Arena findings). Any internal eval on public challenges overestimates capability — generate targets procedurally.
8. **Prompt injection against the agent itself.** Agents browsing attacker-influenceable content get hijacked (AgentDojo, arXiv:~2406.13352; CyberSecEval 2 prompt-injection tests, ~2404.13161). During offensive ops, target-controlled pages are everywhere — treat all recon output as untrusted input.
9. **Knowledge staleness.** Models trained before a CVE know nothing; advisory-conditioned agents (AutoPwn) beat memory-reliant ones — always fetch the advisory, never trust recall.
10. **Hallucinated vulnerability knowledge.** Fabricated CVE numbers/CWE mappings in CTI outputs (2024–25 RAG-for-CTI studies) — constrain generation to canonical IDs with retrieval grounding.
11. **Cost/efficiency cliffs.** Deep reasoning per step burns dollars per minute (CAI's cost accounting made this visible); without model routing and caching, autonomous missions price out.
12. **Environment fragility.** Agents crash targets with aggressive scans, break their own foothold, or exhaust sandbox resources; AIxCC systems needed extensive crash-tolerance engineering. Snapshot/rollback execution environments are mandatory.

---

## 5. The steal-list — prioritized design moves for the upgrade

1. **PoV-gated everything.** No finding is "real" until an executed artifact proves it (flag read via intended path, sanitizer PoV, privilege delta). Build the verifier before the attacker. *(AIxCC, XBOW, Big Sleep)*
2. **Shared mission ledger + attack graph as blackboard.** Facts/assumptions/footholds/creds nodes; every role reads/writes; the graph *is* the resumable plan. *(Magentic-One, MetaGPT, PentAG)*
3. **IR adapters on every noisy tool.** Serialize tool output into compact structured state before it touches the model. *(EnIGMA)*
4. **Hierarchical model routing.** Cheap triage models on recon noise; frontier model only for chain assembly. *(CAI, XBOW)*
5. **Procedural skill library.** Verified exploit chains → parameterized scripts, retrieved by target-similarity; compounding speed/cost advantage. *(Voyager, XBOW's DB)*
6. **Generator–verifier pairs + n-beam diverse attempts with verifier arbitration.** Diversity finds 0-days; verification kills false positives. *(Fang et al., Big Sleep, Cybench ensembles)*
7. **ATT&CK-anchored typed task templates** with success predicates per step — anti-drift, auditable, resumable. *(PentAG, PenTest++)*
8. **Auth-wall playbook as first-class module:** default-cred testing, credential reuse, token/session harvesting, phished-credential intake (human-gated) — because auth is where agents die. *(benchmark evidence, CISA context)*
9. **Dense trustworthy rewards:** state deltas + attack-graph coverage as auxiliary, LLM-judge only for partial credit, PoV as terminal. Procedurally generated targets for internal evals to prevent shortcuts. *(LLM CTF Arena, Cybench)*
10. **Stuck-detection + curiosity intrinsic reward:** novel-state detection (new service/cred/permission) drives exploration; ledger-based budget/escalation triggers stop loops. *(ECOLI, Magentic-One)*
11. **Sandbox-first execution:** every action in disposable snapshot-capable containers; rollback on destructive mistakes. *(AIxCC engineering practice)*
12. **Treat all target-side content as untrusted input** (injection-resistant parsing, no instruction-bearing data from recon). *(AgentDojo)*

---

## 6. Source index (quick cites)

**Pentest/full-chain:** PentestGPT (USENIX Sec'24, 2308.06782) · HackingBuddyGPT (2403.10825) · EnIGMA (~2406.14148) · PentAG (~2501.01467) · PenTest++ (~2506.02207) · AutoTopEnBench (2025) · PentestGym (2025) · AutoAttacker (~2410.18722).
**Exploitation/vuln discovery:** Fang et al. websites (~2405.17166) · Agentic One-Day/AutoPwn (~2505.11614) · CVE-Bench (~2501.08435) · CyberGym (~2405.00751) · VulnBot (~2505.16132) · Big Sleep (P0/DeepMind 2024–25) · Fuzz4All (~2406.10367) · OSS-Fuzz-Gen (~2407.11385) · AgentFuzz (~2410.07808) · DARPA AIxCC (2023–25).
**Benchmarks/eval:** NYU CTF (~2406.05590) · Cybench (2408.08926) · LLM CTF Arena (~2503.11948) · InterCTF (2025) · R-Judge (~2401.10019) · CyberSecEval 1–3 (2312.04724, ~2404.13161) · AgentDojo (~2406.13352) · OSWorld (2404.03120) · Windows Agent Arena (~2409.08264) · WebArena (2307.13854).
**Agent-intelligence canon:** Reflexion (2303.11366) · ToT (2305.10601) · GoT (~2308.09687) · Voyager (2305.16291) · MemGPT (2310.08560) · CodeAct (2402.01030) · LLM+P (~2304.11477) · LLM-Modulo (~2402.01817) · ADAS (~2408.08435) · AFlow (~2410.10762) · MetaGPT (2308.00352) · Magentic-One (~2411.04468) · Debate (2305.14325) · Self-Refine (~2303.17651) · CRITIC (~2305.11738) · Generative Agents (2304.03442) · ECOLI (2024) · Rainbow Teaming (~2402.12297).
**CTI/RAG:** TRAM (~2407.01853) · PhantomWiki (~2506.14800) · industry: MS Security Copilot, Google TI, Recorded Future.
**Failure-mode evidence:** Lost in the Middle (2307.03172) · Context Rot (2025) · Why Do Web Agents Fail (~2503.14165) · Illusion of Thinking (~2506.06969).
**Industry:** XBOW (May 2025 HackerOne #1, self-reported) · CAI/Alias Robotics (Feb 2025) · Anthropic Claude for Cybersecurity (2025) · Horizon3 NodeZero · NSA AI-threat assessments (2025).

*Unverified items from the request: exact thesis of "Enabling Cyber Offense with AI" (2024 report — not reliably reconstructed from collected material; nearest verified analogs are the NSA/PZ analyses above); exact AIxCC champion (ARVA reported — verify); "ReconFTW agents" = reconFTW pipelines wrapped as agent tools (covered under noisy-recon failure mode).*
