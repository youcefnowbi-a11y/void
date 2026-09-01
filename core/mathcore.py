"""VOIDFORGE :: mathcore — the mathematical nervous system.

Five weapons, pure stdlib, no external dependencies:

  §1 INFORMATION THEORY   Shannon entropy, surprisal ranking, Zipf budgeting.
  §2 BANDIT CONTROL       UCB1-Tuned + Thompson sampling over tool history
                          (auto-seeded from missions.db tool_runs).
  §3 STOCHASTIC PACING    Token bucket + full-jitter backoff + EWMA/σ drift
                          detection + AIMD rate adaptation (anti-throttle).
  §4 BAYESIAN FUSION      Log-odds evidence accumulation with correlation
                          discounting -> posterior-ranked findings.
  §5 SIMILARITY / DEDUP   SimHash (Hamming), MinHash (Jaccard), Bloom filter.

Hook map:
  planner.execute_plan  -> bandit_rank() / bandit_record()
  tools._shared._get/_req -> get_pacer(host).wait() / .observe(status, rtt)
  reports / agent       -> fuse_findings_from_db(mission_id)
"""
import json, math, os, random, re, sqlite3, threading, time
from collections import Counter, deque
from hashlib import blake2b

HERE = os.path.dirname(os.path.abspath(__file__))
BANDIT_PATH = os.path.join(HERE, "bandit.json")
DB_PATH = os.path.join(HERE, "missions.db")


# ═══════════════════════════════════════════════════════════════════════
# §1 INFORMATION THEORY — rank candidates by expected bits of surprise
# ═══════════════════════════════════════════════════════════════════════

def entropy(tokens):
    """Shannon entropy H = -Σ p·log2(p), in bits, over a token sequence."""
    n = len(tokens)
    if n == 0:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in Counter(tokens).values())


# Frequency prior over the open web (Zipf-ordered common path/param tokens).
_COMMON = ("api admin login logout user users config settings dashboard home index "
           "static assets js css img images fonts upload uploads download files "
           "search query query2 id uid page pages blog news post posts comment "
           "auth token refresh signin signup register account profile settings2 "
           "v1 v2 v3 graphql rest rpc json xml status health ping debug test "
           "backup bak old new tmp temp private public secret secrets key keys "
           "mail email sms phone notify notification webhook callback oauth "
           "session cookie cart order orders pay payment checkout billing").split()
_PRIOR = {w: 1.0 / (i + 1) ** 1.0 for i, w in enumerate(_COMMON)}
_DEFAULT_P = _PRIOR.get("tmp", 0.0)


def surprisal(token):
    """Surprisal in bits: -log2 P(token). Rare tokens carry more information
    per probe — probing 'j_sesion_backup' teaches you more than 'admin'."""
    p = _PRIOR.get(token.lower(), 0.02)
    return -math.log2(min(max(p, 1e-6), 1.0))


def surprisal_rank(candidates):
    """Rank candidates (paths, subdomains, params) by mean token surprisal,
    descending. High-scoring candidates are the ones worth burning requests on."""
    def score(c):
        parts = re.split(r"[._\-/?=&]+", str(c).lower())
        parts = [p for p in parts if p]
        return sum(surprisal(p) for p in parts) / max(len(parts), 1)
    return sorted(candidates, key=score, reverse=True)


def zipf_top(candidates, budget, s=1.0):
    """Given a request budget B and N candidates with Zipf(s) hit priors,
    return the B candidates maximizing expected discoveries (greedy knapsack
    on per-request expected value — provably optimal for unit costs)."""
    ranked = surprisal_rank(candidates)
    n = len(ranked)
    if budget >= n:
        return ranked
    weights = [(1.0 / (i + 1) ** s) for i in range(n)]
    z = sum(weights) or 1.0
    order = sorted(range(n), key=lambda i: -weights[i] / z)
    return [ranked[i] for i in order[:max(budget, 0)]]


# ═══════════════════════════════════════════════════════════════════════
# §2 BANDIT CONTROL — learn which tools actually deliver
# ═══════════════════════════════════════════════════════════════════════

# Value model:  score = p̂ + exploration_bonus − λ · normalized_duration
#   p̂               empirical success rate of the tool
#   exploration     UCB1-Tuned bonus (variance-aware optimism under uncertainty)
#   λ = 0.05        slow-but-reliable tools only mildly penalized
# No-history tools get a novelty prior + noise so every arsenal module gets
# its chance, but proven workhorses float to the front of the queue.

_LAMBDA = 0.05
_DECAY = 0.985  # per-observation recency factor (half-life ≈ 46 obs)
_NOVEL_PRIOR = {"safe": 0.55, "medium": 0.45, "high": 0.35, "unsafe": 0.25}
_bandit_lock = threading.Lock()
_bandit = None  # {tool: {"n": int, "wins": int, "d1": float, "d2": float}}


def _bandit_load():
    global _bandit
    if _bandit is not None:
        return _bandit
    if os.path.exists(BANDIT_PATH):
        try:
            with open(BANDIT_PATH, encoding="utf-8") as f:
                _bandit = json.load(f)
            return _bandit
        except Exception:
            pass
    _bandit = {}
    _seed_from_db()
    return _bandit


def _bandit_save():
    try:
        # R2-3 : dump atomique tmp + os.replace (miroir de blackboard.py) —
        # un crash mid-écriture ne doit plus corrompre l'état appris.
        tmp = BANDIT_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_bandit or {}, f)
        os.replace(tmp, BANDIT_PATH)
    except Exception:
        pass


def _seed_from_db():
    """Bootstrap bandit priors from historical tool_runs in missions.db."""
    try:
        c = sqlite3.connect(DB_PATH)
        rows = c.execute(
            "SELECT tool_name, status, duration FROM tool_runs "
            "WHERE status IN ('ok','error')").fetchall()
        c.close()
    except Exception:
        return
    for name, status, dur in rows:
        _record(name, status == "ok", float(dur or 0.0), save=False)


def bandit_record(tool, success, duration, save=True):
    """Feed one observed outcome back into the bandit posterior.

    NON-STATIONARY bandit (Garivier & Moulines 2011, sliding-window
    equivalence): every stored statistic decays by γ before the new
    observation lands. Old evidence fades exponentially, so a tool that
    DEGRADES (target hardened, endpoint renamed) loses rank within ~40
    runs, while a consistently good tool keeps its p̂ — and its UCB
    exploration bonus grows again when it goes stale, so it gets retried."""
    global _bandit
    with _bandit_lock:
        s = _bandit_load().setdefault(tool, {"n": 0, "wins": 0, "d1": 0.0, "d2": 0.0})
        if s["n"] > 0:
            for k in ("n", "wins", "d1", "d2"):
                s[k] *= _DECAY
        s["n"] += 1
        s["wins"] += 1 if success else 0
        d = max(float(duration or 0.0), 0.0)
        s["d1"] += d
        s["d2"] += d * d
        if save:
            _bandit_save()


def _stats(tool, danger="safe"):
    s = _bandit_load().get(tool)
    if not s or s["n"] == 0:
        return None
    n = s["n"]
    p = s["wins"] / n
    mean_d = s["d1"] / n
    var_d = max(s["d2"] / n - mean_d * mean_d, 0.0)
    return {"n": n, "p": p, "mean_d": mean_d, "var_d": var_d}


def _ucb1_tuned(p, n, var, t):
    """UCB1-Tuned exploration bonus (Auer et al. 2002, Theorem 4)."""
    if n <= 0:
        return float("inf")
    v = var + math.sqrt(2.0 * math.log(t) / n)
    return math.sqrt((math.log(t) / n) * min(0.25, v))


def bandit_rank(names, dangers=None):
    """Return exploitation-ready scores for a list of tool names (same order).
    Higher = run earlier. Never raises for unknown tools."""
    with _bandit_lock:
        _bandit_load()
        t = max(2, sum(s["n"] for s in _bandit.values()))
        scores = []
        for i, name in enumerate(names):
            danger = (dangers[i] if dangers and i < len(dangers) else "safe").lower()
            st = _stats(name, danger)
            if st is None:
                # unseen tool: optimism + prior + jitter (deterministic per name+round)
                prior = _NOVEL_PRIOR.get(danger, 0.45)
                rng = random.Random(f"{name}:{t}")
                scores.append(prior + 0.6 + rng.random() * 0.05)
                continue
            # UCB1-Tuned's v term is the VARIANCE OF THE REWARD process.
            # Rewards here are Bernoulli (success/failure), so var ≤ p(1-p) ≤ 0.25
            # by construction — passing duration variance here (pre-existing bug)
            # always saturated min(0.25, v) and silently degraded the bonus to
            # plain UCB1. Duration cost lives in the λ term where it belongs.
            var_r = st["p"] * (1 - st["p"])
            bonus = _ucb1_tuned(st["p"], st["n"], var_r, t)
            if bonus == float("inf"):
                bonus = 0.6
            cost = min(st["mean_d"] / 60.0, 1.0)  # minutes -> [0,1]
            scores.append(st["p"] + bonus - _LAMBDA * cost)
        return scores


def bandit_thompson_sample(names):
    """Thompson sampling: draw from each tool's Beta posterior. Use when you
    want stochastic exploration instead of UCB optimism."""
    with _bandit_lock:
        _bandit_load()
        out = []
        for name in names:
            s = _bandit_load().get(name) or {"n": 0, "wins": 0}
            a = s["wins"] + 1
            b = s["n"] - s["wins"] + 1
            out.append((random.betavariate(a, b), name))
        return sorted(out, key=lambda x: -x[0])


def bandit_success_cost(tool):
    """Public read: (empirical success rate, mean duration in seconds).
    Defaults (0.5, 1.0) for unseen tools — used by the attack-graph planner's
    value model so MCTS exploits real history instead of guessing."""
    with _bandit_lock:
        st = _stats(tool)
    if st is None:
        return 0.5, 1.0
    return st["p"], max(st["mean_d"], 0.1)


def bandit_history():
    """Public read: {tool: {"n", "p", "mean_d"}} for every tool with recorded
    history — lets the LLM agent see which weapons are battle-proven."""
    with _bandit_lock:
        _bandit_load()
        out = {}
        for name, s in (_bandit or {}).items():
            if s.get("n", 0) > 0:
                out[name] = {"n": s["n"], "p": s["wins"] / s["n"],
                             "mean_d": s["d1"] / s["n"]}
        return out


def bandit_reset(seed=False):
    """Wipe learned values (tests / fresh doctrine). seed=True re-pulls DB."""
    global _bandit
    with _bandit_lock:
        _bandit = {}
        if seed:
            _seed_from_db()
        _bandit_save()


# ═══════════════════════════════════════════════════════════════════════
# §3 STOCHASTIC PACING — token bucket + EWMA drift + AIMD adaptation
# ═══════════════════════════════════════════════════════════════════════

# Physics of not getting banned:
#   • Token bucket (rate r, burst b): sustained mean r req/s, bursts up to b.
#   • EWMA(α) tracks server response time; σ from running variance.
#   • 429/403 or rtt > ewma+3σ  ->  r *= 0.5   (multiplicative decrease)
#   • 20 consecutive clean      ->  r += 0.2   (additive increase, capped)
# Same control law as TCP congestion avoidance — it converges to the maximum
# rate the target tolerates, automatically, per host.

class Pacer:
    def __init__(self, host, rate=8.0, burst=16.0, max_rate=32.0):
        self.host = host
        self.rate = float(rate)
        self.burst = float(burst)
        self.max_rate = float(max_rate)
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._rtts = deque(maxlen=60)
        self._ewma = None
        self._var = 0.0
        self._clean = 0
        self._lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
        self._last = now

    def wait(self):
        """Block until one token is available AND consume it (R2-2). Boucle
        garantie : aucun appelant ne repart sans avoir décrémenté un token —
        un burst de waiters ne peut plus glisser sur un seul refill."""
        slept = 0.0
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return slept
                if self.rate <= 0:
                    return slept  # pacer dégénéré : ne pas boucler à l'infini
                need = (1.0 - self._tokens) / self.rate
            chunk = min(need, 2.0)
            time.sleep(chunk)
            slept += chunk

    def observe(self, status, rtt):
        """Feed one HTTP outcome (status code, round-trip seconds)."""
        with self._lock:
            self._rtts.append(max(float(rtt or 0.0), 0.0))
            alpha = 2.0 / (len(self._rtts) + 1)
            if self._ewma is None:
                self._ewma, self._var = self._rtts[-1], 0.0
            else:
                self._var = (1 - alpha) * (self._var + alpha * (self._rtts[-1] - self._ewma) ** 2)
                self._ewma = alpha * self._rtts[-1] + (1 - alpha) * self._ewma
            if status in (429, 403) or (self._ewma and self._rtts[-1] > self._ewma + 3 * math.sqrt(self._var + 1e-9)):
                self.rate = max(0.5, self.rate * 0.5)
                self._clean = 0
            elif status and status < 400:
                self._clean += 1
                if self._clean >= 20:
                    # RTT-aware additive increase (Vegas flavor): the faster the
                    # target answers, the more headroom it signals. inc = 0.05/rtt
                    # bounded to [0.2, 2.0] req/s keeps the controller monotone
                    # and stable while converging to available bandwidth ~2× faster
                    # than fixed +0.2.
                    rtt = max(self._ewma or 0.25, 0.05)
                    inc = max(0.2, min(2.0, 0.05 / rtt))
                    self.rate = min(self.max_rate, self.rate + inc)
                    self._clean = 0


_pacers = {}
_pacers_lock = threading.Lock()


def get_pacer(host, rate=8.0, burst=16.0):
    with _pacers_lock:
        # R2-9: éviction LRU — le process FastAPI long-vécu ne fuit plus un
        # pacer par host visité depuis le début des temps (pacer_drop n'était
        # appelé que par les tests). Les dormants >1h sortent à 64 entrées.
        if len(_pacers) >= 64 and host not in _pacers:
            _now = time.monotonic()
            for _h in [h for h, p in _pacers.items()
                       if h != host and _now - getattr(p, "_last", _now) > 3600.0]:
                _pacers.pop(_h, None)
        p = _pacers.get(host)
        if p is None:
            p = _pacers[host] = Pacer(host or "default", rate=rate, burst=burst)
        return p


def pacer_drop(host):
    with _pacers_lock:
        _pacers.pop(host, None)


# ═══════════════════════════════════════════════════════════════════════
# §4 BAYESIAN FUSION — posterior probability that a finding is REAL
# ═══════════════════════════════════════════════════════════════════════

# logit(p) = ln(p/(1-p)); each corroborating observation adds ln(LR) to the
# log-odds. Repeated evidence sharing a correlation key is discounted by
# 1/(1+0.35k) so one secret echoed by five tools doesn't read as five secrets.

# Severity acts as the RELIABILITY of an observation, so it scales the
# likelihood ratio in LINEAR space — normalized exponents in [0,1] keep every
# contribution in log-odds units (the old ln(lr)·ln(sev) product lived in
# log²-odds, dimensionally meaningless and wildly overconfident on CRITICAL).
_SEV_W = {"CRITICAL": 1.0, "HIGH": 0.8, "MEDIUM": 0.55, "INFO": 0.3}
_TYPE_PRIOR = {"secret": 0.35, "endpoint": 0.25, "subdomain": 0.20,
               "sqli": 0.30, "token": 0.45, "table": 0.40, "waf": 0.50}
_TYPE_LR = {"supabase_exfil": 4.0, "data_extract": 3.5, "secret_scan": 2.5,
            "endpoint_oracle": 1.8, "har_tokens": 2.0, "js_mine": 1.5,
            "web_fingerprint": 1.2, "subdomain_enum": 1.5}
_DEF_LR = 1.5


def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def fuse_finding(finding_type, evidence, prior=None):
    """evidence: [(tool_name, severity, corr_key)] -> posterior P(real)."""
    p0 = prior if prior is not None else _TYPE_PRIOR.get(str(finding_type).lower(), 0.25)
    logodds = _logit(p0)
    seen_corr = Counter()
    for tool, sev, corr in evidence:
        lr = _TYPE_LR.get(str(tool).lower(), _DEF_LR)
        w = math.log(lr) * _SEV_W.get(str(sev).upper(), _SEV_W["INFO"])
        k = seen_corr.get(corr, 0) if corr else 0
        w /= (1.0 + 0.35 * k)
        logodds += w
        if corr:
            seen_corr[corr] += 1
    return _sigmoid(logodds)


def classify_posterior(p):
    if p >= 0.90: return "CRITICAL"
    if p >= 0.70: return "HIGH"
    if p >= 0.40: return "MEDIUM"
    return "INFO"


def fuse_findings_from_db(mission_id):
    """Fuse all findings recorded for a mission into posterior-ranked intel.
    Returns [{finding_type, posterior, severity, n_evidence, sample}]."""
    try:
        c = sqlite3.connect(DB_PATH)
        rows = c.execute(
            "SELECT tool_name, severity, finding_type, detail FROM findings "
            "WHERE mission_id=? ORDER BY id", (mission_id,)).fetchall()
        c.close()
    except Exception:
        return []
    groups = {}
    for tool, sev, ftype, detail in rows or []:
        g = groups.setdefault(ftype or "unknown",
                              {"evidence": [], "sample": detail or ""})
        g["evidence"].append((tool or "?", sev or "INFO",
                              (detail or "")[:40]))
    out = []
    for ftype, g in groups.items():
        p = fuse_finding(ftype, g["evidence"])
        out.append({"finding_type": ftype, "posterior": round(p, 4),
                    "severity": classify_posterior(p),
                    "n_evidence": len(g["evidence"]), "sample": g["sample"][:160]})
    return sorted(out, key=lambda f: -f["posterior"])


# ═══════════════════════════════════════════════════════════════════════
# §5 SIMILARITY / DEDUP — SimHash, MinHash, Bloom filter
# ═══════════════════════════════════════════════════════════════════════

def _h64(s, seed=0):
    return int.from_bytes(blake2b(s.encode("utf-8", "ignore"),
                                  digest_size=8, key=bytes([seed % 256])).digest(), "big")


def simhash(text):
    """64-bit locality-sensitive fingerprint (Charikar). Near-duplicates
    collide: hamming(simhash(a), simhash(b)) small <=> a≈b."""
    v = [0] * 64
    words = re.findall(r"[a-zA-Z0-9_]{2,}", str(text))
    feats = words + [f"{a}~{b}" for a, b in zip(words, words[1:])]
    if not feats:
        return 0
    for f in feats:
        h = _h64(f)
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    return out


def hamming(a, b):
    return bin(a ^ b).count("1")


def minhash_jaccard(a, b, perms=96):
    """Estimated Jaccard similarity of two texts via k-min hashing."""
    wa = set(re.findall(r"[a-zA-Z0-9_]{2,}", str(a).lower()))
    wb = set(re.findall(r"[a-zA-Z0-9_]{2,}", str(b).lower()))
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    ma = [min(_h64(w, s) for w in wa) for s in range(perms)]
    mb = [min(_h64(w, s) for w in wb) for s in range(perms)]
    return sum(1 for x, y in zip(ma, mb) if x == y) / perms


class Bloom:
    """Space-efficient membership set. FPP ≈ (1-e^{-kn/m})^k; size the bit
    array with m = -n·ln(p)/(ln2)² for target false-positive rate p."""

    def __init__(self, expected=10000, fpp=0.01):
        m = max(64, int(-expected * math.log(fpp) / (math.log(2) ** 2)))
        k = max(1, round((m / max(expected, 1)) * math.log(2)))
        self.m, self.k = m, k
        self.bits = bytearray((m + 7) // 8)
        self.n = 0

    def _idx(self, item):
        h = _h64(str(item))
        h2 = (h >> 32) | 1
        for i in range(self.k):
            yield (h + i * h2) % self.m

    def add(self, item):
        for i in self._idx(item):
            self.bits[i >> 3] |= 1 << (i & 7)
        self.n += 1

    def __contains__(self, item):
        return all(self.bits[i >> 3] >> (i & 7) & 1 for i in self._idx(item))

    def fpp_estimate(self):
        return ((1 - math.exp(-self.k * self.n / self.m)) ** self.k) if self.n else 0.0
