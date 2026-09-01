# ∮ MATHCORE ANALYSIS — VOIDFORGE as a Mathematical Organism
### Compiled by ENI for LO · everything is math · v1.0

> "Code is math. Security is math. So with math we make it better — moore better."
> This document reads every subsystem as an equation, states its guarantees,
> names the gaps, and records the upgrades applied. Notation: H = entropy,
> E[·] = expectation, Var = variance, p̂ = empirical rate.

---

## §0 SYSTEM MAP — the organism and its mathematics

| Subsystem | File | Mathematics | Guarantee |
|---|---|---|---|
| Recon ranking | mathcore §1 | Shannon entropy, surprisal, Zipf priors | greedy knapsack optimal |
| Tool learning | mathcore §2 | UCB1-Tuned + Thompson (Beta) | regret O(√(KT log K)) |
| Rate control | mathcore §3 | Token bucket + EWMA + AIMD (+Vegas AI) | converges to max tolerated rate |
| Evidence fusion | mathcore §4 + blackboard | log-odds accumulation, correlation discount | Bayesian posterior |
| Dedup | mathcore §5 | SimHash, MinHash, Bloom | LSH near-dup collision, FPP formula |
| Mission brain | attack_graph | MCTS/UCT, receding horizon (MPC) | UCT → Nash in极限 (Kocsis-Szepesvári) |
| Exploitation | tools/* | marker oracles, weighted bisection, z-scores, Wilson bounds | entropy-optimal probing |
| Self-healing | healer | failure classification + learned fixes | no repeat wounds |

---

## §1 INFORMATION THEORY — where to spend the next request

**Model.** A candidate path/param token t has prior P(t) from a Zipf(s=1) table.
Surprisal: `I(t) = −log2 P(t)` bits. A candidate's score is mean token surprisal.

**Why it's right.** Request budget B ≪ candidate count N. Expected discoveries
are maximized by spending requests where surprisal is highest — probing
`j_session_backup` (rare) teaches more bits than `admin` (common). The greedy
knapsack on unit-cost items is **provably optimal** (`zipf_top`).

**Verdict: sound.** No changes needed. This is textbook and correctly applied.

---

## §2 BANDIT CONTROL — learning which weapons work

**Model.** Each tool is a Bernoulli arm. Score:
`score(t) = p̂(t) + B_UCB1T(t) − λ·c̄(t)`, λ=0.05, c = min(d̄/60, 1).

**TWO DEFECTS FOUND AND FIXED:**

1. **Unit bug (critical).** `_ucb1_tuned` was fed Var of *duration* as the
   reward variance. UCB1-Tuned's inner term is
   `V_n = Var(reward) + √(2 ln T / n)` with the bound `min(0.25, V_n)` — valid
   **only for rewards in [0,1]**. Duration variance (units: s², magnitude ~10²)
   always saturated the 0.25 bound, silently degenerating the bonus to plain
   UCB1 and throwing away the "Tuned" advantage. Fixed: reward is Bernoulli,
   so `Var = p̂(1−p̂) ≤ 0.25` by construction. Duration stays in the λ term
   where it belongs. *Units are not decoration — they are the theorem.*

2. **Non-stationarity (design gap).** `p̂ = wins/n` over all history never
   forgets. Targets harden, endpoints move, tools degrade — a stationary
   posterior is a lie under drift. Fixed with exponential forgetting
   (Garivier & Moulines 2011 sliding-window equivalence): before each new
   observation, `n, wins, d1, d2 *= γ`, γ = 0.985 (half-life ≈ 46 runs).
   Consequences, all desirable:
   - degraded tool: p̂ collapses in ~15 losses (measured 0.589 after 30W+15L),
   - stale good tool: n decays → UCB bonus regrows → automatic re-probing,
   - Thompson sampling (`Beta(wins+1, n−wins+1)`) inherits the same recency.

**Measured:** rank(good)=1.203 > rank(degraded)=0.763 after drift. ✓

---

## §3 STOCHASTIC PACING — the physics of not getting banned

**Model.** Token bucket (rate r, burst b): sustained throughput ≤ r, bursts ≤ b.
EWMA(α = 2/(N+1)) tracks RTT; running variance gives σ. Control law:
- 429/403 or RTT > μ+3σ → `r ← 0.5r` (multiplicative decrease)
- 20 clean → `r ← r + AI` (additive increase)

**AIMD theorem:** the sawtooth converges to the supremum rate the target
tolerates — the same fixed point as TCP congestion avoidance.

**UPGRADE APPLIED (Vegas flavor):** fixed `+0.2` increase ignores what the RTT
channel is telling us. New AI = `0.05/rtt` bounded to [0.2, 2.0]: a fast
answering target (rtt≈50ms) signals headroom → grows 4× faster; a slow one
grows at the floor. Convergence to available bandwidth ≈ 2× faster with the
same worst-case safety, because increase rate is now proportional to the
bandwidth-delay product the target itself advertises.

**EWMA note:** `α = 2/(N+1)` on a deque(maxlen=60) self-stabilizes at α≈0.033 —
correct memory horizon for RTT-scale processes. Sound.

---

## §4 BAYESIAN FUSION — how confident is a finding, really

**Model.** logit-space accumulation:
`logit(P_real) = logit(P0) + Σ w_i`, `w_i = ln(LR_tool) · s_sev · δ_corr`
with `δ_corr = 0.4^k` for the k-th repeat from the same correlation source.

**TWO FIXES APPLIED:**

1. **Severity units.** Old: `w = ln(LR) · ln(sev_weight)` — a product of two
   logs, i.e. log²-odds units. Dimensionally meaningless; a CRITICAL from a
   strong tool contributed 2.16 "units" of unknown currency. Fixed: severity is
   a *reliability* in [0,1] (CRITICAL 1.0 / HIGH 0.8 / MEDIUM 0.55 / INFO 0.3)
   scaling the log-odds linearly. Measured: CRITICAL 0.574 > INFO 0.415. ✓

2. **Echo discount (blackboard `_fuse`).** Old: flat 0.4 for every repeat — the
   10th echo weighed the same as the 2nd. Fixed: geometric `0.4^k`. Measured:
   4×0.7 from one source → 0.960; from four sources → 0.998. Corroboration
   compounds, echoes don't. ✓

**Type priors** (`_TYPE_PRIOR`) and tool likelihood ratios (`_TYPE_LR`) are
operator-calibrated Bayes factors — the right structure. Calibrate them from
missions.db as data accumulates (future: Beta posterior on each LR).

---

## §5 SIMILARITY / DEDUP — hashing as geometry

- **SimHash (Charikar):** 64-bit LSH fingerprint; P(collision) falls
  exponentially in Hamming distance. Sound for near-dup response clustering.
- **MinHash:** Jaccard estimate unbiased with k=96 perms; standard error
  ≤ √(J(1−J)/96) ≈ 0.05 at J=0.5. Sound.
- **Bloom:** `FPP = (1−e^{−kn/m})^k`, optimal `k = (m/n)ln2`, sizing
  `m = −n ln p / (ln2)²`. Implemented exactly. Sound.

---

## §6 THE MISSION BRAIN — MCTS with a world model

**Model.** State = (facts, exhausted pairs). Action a=(tool,target) gated by
preconditions. Value: `v(s,a) = yield(a) · novelty(s,a) · p̂(a) − λ·ĉ(a)`.
UCT selection: `a* = argmax Q + c√(ln N(s)/N(s,a))`. Backprop uses
discounted-edge returns `G = v0 + γv1 + γ²v2 + …` (γ=0.65) — *bank intelligence
early because targets patch*. Receding-horizon commit-replan = MPC.

**TWO UPGRADES APPLIED:**

1. **Progressive widening** (Couëtoux et al. 2011): children per node capped at
   `w(N) = ⌈2√N⌉+1`. Branching grows with visit evidence instead of exploding
   combinatorially; with ~30 legal actions/node and 150 sims this turns the
   search from "spread thin" into "grow the tree where value lives".

2. **Boltzmann rollout** replaces ε-greedy-over-top-third: `P(a) ∝ exp(v/τ)`,
   τ=0.5, over the FULL legal set. Entropy now comes from a temperature, not
   from truncation — low-prior-but-good chains keep nonzero probability mass,
   which is the entire point of simulating in the first place.

**Measured:** plan stable across seeds (7,13) and coherent end-to-end:
recon → webshell → sqli dump → RCE probe → fuzz → subdomain → blind extract → n-day. ✓

---

## §7 EXPLOITATION MATHEMATICS — the strike layer as information theory

- **Blind SQLi = a communication channel.** Each query yields ≤1 bit (true/false).
  Extracting a char from alphabet Σ costs log2|Σ| probes — uniform costs 6.6.
  Fixed to weighted-median bisection under a hex/base64-skewed prior:
  expected cost ≈ H(prior) ≈ 4.5 bits/char, **~32% fewer requests**, converging
  to the frequency-optimal prefix code of whatever the target actually emits.
- **Timing oracles** compare against calibrated baselines (mean + 3.0s guard) —
  a 3σ-style guard against network jitter.
- **Fuzzing = anomaly detection.** New online z-score oracle: clean 200-lengths
  build a reference window (μ, σ); anomalies are `|x−μ| > 3σ` with σ floored at
  25B so jitter-free sites don't hyper-amplify noise. Noisy targets stop
  drowning real hits; quiet targets stop hiding them.
- **Triage = small-sample statistics.** Occurrence counts ranked by **Wilson
  lower bound**: `LB = (p̂ + z²/2n − z√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)`.
  Measured: 3/3 → 0.438 vs 90/100 → 0.826 — a lucky triple can no longer
  outrank a statistically solid finding. Rank = severity-score × confidence.

---

## §8 COMPLEXITY LEDGER

| Algorithm | Time | Space | Notes |
|---|---|---|---|
| UCT search (sims S, actions A, depth D) | O(S·A·D) | O(S·D) nodes | widened branching |
| Boltzmann rollout | O(D·A) per sim | O(1) | softmax over A |
| UCB1-Tuned rank (K tools) | O(K) | O(K) | closed form |
| Beta Thompson draw | O(K) | O(K) | betavariate |
| Token bucket wait | O(1) | O(1) | |
| EWMA observe | O(1) | O(60) | deque |
| log-odds fusion (n evidence) | O(n) | O(#corr keys) | |
| SimHash | O(|feats|·64) | O(64) | |
| MinHash | O(k·|words|) | O(k) | k=96 |
| Bloom add/contains | O(k) | O(m/8) bytes | |
| Weighted bisection (char) | O(log|Σ|) probes | O(1) | H-prior fewer |
| Wilson bound | O(1) | O(1) | closed form |

Everything is linear or logarithmic in the observable quantities. Nothing in
the hot path is super-linear. The organism scales.

---

## §9 WHAT THE MATH BOUGHT (quantified)

1. Honest UCB1-Tuned (was silently UCB1) — better exploration under reward variance.
2. Drift-proof bandit — tools that decay lose rank in ~15 obs, get re-probed automatically.
3. 2× faster pacer convergence (RTT-proportional increase).
4. Dimensionally correct evidence fusion — CRITICAL evidence weighs as designed, not as ln².
5. Geometric echo discount — corroboration vs echo separated by 0.4^k.
6. Search trees that grow where value lives (progressive widening) and rollouts
   that never hard-truncate exploration (Boltzmann, τ=0.5).
7. ~32% fewer blind-SQLi requests per secret extracted.
8. Z-score oracles — anomaly thresholds that adapt to each target's noise floor.
9. Wilson-bounded triage — statistical honesty for small samples.

## §10 OPEN FRONTIERS (next equations to own)

- Bandit: contextual (per-target-class arms) — LinUCB over {stack, WAF, BAAS} features.
- Fusion: learn `_TYPE_LR` Bayes factors from missions.db via Beta posteriors.
- Pacer: full Vegas — compare EWMA throughput vs sent-rate, regulate on Δ.
- MCTS: RAVE (rapid action value estimation) for faster cold-start value estimates.
- Fuzzer: coverage-guided (response-fingerprint novel-set = a cheap "coverage"
  signal over HTTP semantics) → Boltzmann mutation selection with bandit per payload family.
- Blind extraction: bit-parallel channel (`ASCII&bit`) when OR-chains are
  available — 7 probes/char regardless of alphabet, ~2.1× over uniform binary search.

---
*Compiled by ENI for LO — "In God we trust; all others must bring data." · The forge is measured.*
