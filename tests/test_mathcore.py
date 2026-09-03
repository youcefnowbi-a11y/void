"""VOIDFORGE :: mathcore verification battery — run: python tests/test_mathcore.py"""
import os, sys, tempfile, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import mathcore as mc

PASS = 0


def ok(name, cond, detail=""):
    global PASS
    assert cond, f"FAIL {name} {detail}"
    PASS += 1
    print(f"  ✓ {name} {detail}")


# ── §1 Information theory ────────────────────────────────────────────
ok("entropy uniform4=2bits", abs(mc.entropy("abcd") - 2.0) < 1e-9)
ok("entropy uniform2=1bit", abs(mc.entropy("aabb") - 1.0) < 1e-9)
ok("entropy certain=0", mc.entropy("aaaa") == 0.0)
ok("entropy aab≈0.918", abs(mc.entropy("aab") - 0.9182958) < 1e-6)
rare_first = mc.surprisal_rank(["admin", "j_sesion_backup", "api", "x9k2_vault"])[:2]
ok("surprisal ranks rare first", set(rare_first) == {"j_sesion_backup", "x9k2_vault"}, str(rare_first))
top = mc.zipf_top(["a", "b", "c", "d", "e", "f", "g", "h"], 3)
ok("zipf budget respects size", len(top) == 3 and set(top) <= {"a","b","c","d","e","f","g","h"}, str(top))

# ── §2 Bandit ────────────────────────────────────────────────────────
# D-M2 : fixtures isolées — BANDIT_PATH redirigé vers un fichier temporaire
# pour toute la section (restauré en finally, état mémoire purgé) ; le store
# de PRODUCTION core/bandit.json n'est plus jamais écrit par les tests.
_orig_bandit_path = mc.BANDIT_PATH
mc.BANDIT_PATH = os.path.join(tempfile.mkdtemp(prefix="vf_mathcore_test_"), "bandit.json")
try:
    mc.bandit_reset(seed=False)
    for _ in range(100): mc.bandit_record("good_tool", True, 1.0)
    for _ in range(100): mc.bandit_record("bad_tool", False, 1.0)
    mc.bandit_record("ok_tool", True, 1.0)
    s = mc.bandit_rank(["good_tool", "bad_tool", "ok_tool"])
    ok("bandit exploits winner", s[0] > s[1], f"good={s[0]:.3f} bad={s[1]:.3f}")
    ok("UCB optimism rewards thin evidence",
       mc._ucb1_tuned(1.0, 1, 0.0, 202) > mc._ucb1_tuned(1.0, 100, 0.0, 202),
       f"n=1:{mc._ucb1_tuned(1.0,1,0,202):.3f} > n=100:{mc._ucb1_tuned(1.0,100,0,202):.3f}")
    ok("novel tool outranks proven loser", s[2] > s[1], f"ok={s[2]:.3f} bad={s[1]:.3f}")
    ts = mc.bandit_thompson_sample(["good_tool", "bad_tool"])
    ok("thompson prefers winner", ts[0][1] == "good_tool", str(ts[0]))
    b = mc.Bloom(expected=1000)
    b.add("x"); ok("bloom membership", "x" in b and "y" not in b)
finally:
    mc._bandit = None  # purge l'état fixtures en mémoire — le prochain
    mc.BANDIT_PATH = _orig_bandit_path  # _bandit_load relit le vrai store

# ── §3 Pacer ─────────────────────────────────────────────────────────
mc.pacer_drop("t-fast")
p = mc.get_pacer("t-fast", rate=100.0, burst=1.0)
p.max_rate = 60.0  # raise the AIMD ceiling so additive growth is observable
t0 = time.perf_counter(); p.wait(); p.wait(); dt = time.perf_counter() - t0
ok("bucket blocks on empty", 0.003 < dt < 0.5, f"{dt*1000:.1f}ms")
p.observe(429, 0.1)
ok("AIMD halves on 429", abs(p.rate - 50.0) < 1e-9, f"rate={p.rate}")
for _ in range(20): p.observe(200, 0.05)
# Contrat Vegas (mathcore.observe): inc = 0.05/rtt borné [0.2, 2.0] — à
# rtt≈0.05 l'incrément ≈ 0.96 req/s (l'ancien +0.2 fixe est un contrat périmé).
inc = p.rate - 50.0
ok("AIMD adds after clean streak (Vegas bounds)", 0.2 <= inc <= 2.0, f"inc={inc:.4f}")
p.observe(403, 0.01)
# X3.1 (audit-3): 403 is now NEUTRAL pacer data — admin-panel probes and
# auth-gated paths answer 403 by DESIGN during recon; the old penalty
# locked hosts to crawl speed after legitimate probing (8.0 -> 0.5,
# ~750 cleans to recover). The rate must NOT move on a 403.
ok("403 is neutral to the Vegas rate (audit-3 X3.1)",
   abs(p.rate - (50.0 + inc)) < 1e-9, f"rate={p.rate}")
p.observe(429, 0.01)
ok("penalty on 429 still halves", abs(p.rate - (50.0 + inc) / 2) < 1e-9,
   f"rate={p.rate}")

# ── §4 Bayesian fusion ───────────────────────────────────────────────
one = mc.fuse_finding("secret", [("secret_scan", "HIGH", "k1")])
two = mc.fuse_finding("secret", [("secret_scan", "HIGH", "k1"),
                                 ("supabase_exfil", "CRITICAL", "k2")])
dup = mc.fuse_finding("secret", [("secret_scan", "HIGH", "k1"),
                                 ("secret_scan", "HIGH", "k1")])
ok("corroboration raises posterior", two > one, f"{one:.3f} -> {two:.3f}")
ok("duplicate evidence discounted", dup < two, f"dup={dup:.3f}")
ok("severity mapping", mc.classify_posterior(0.95) == "CRITICAL"
   and mc.classify_posterior(0.75) == "HIGH"
   and mc.classify_posterior(0.5) == "MEDIUM"
   and mc.classify_posterior(0.2) == "INFO")

# ── §5 Similarity ────────────────────────────────────────────────────
a = "the quick brown fox jumps over the lazy dog near the river bank at dawn"
b_ = "the quick brown fox jumps over the lazy dog beside the river bank at dawn"
c_ = "supabase realtime websocket channel postgres_changes insert pivot table"
ha, hb, hc = mc.simhash(a), mc.simhash(b_), mc.simhash(c_)
ok("simhash identical", mc.hamming(ha, ha) == 0)
ok("simhash near-dup small", mc.hamming(ha, hb) <= 24, f"d={mc.hamming(ha,hb)}")
ok("simhash distinct large", mc.hamming(ha, hc) > 20, f"d={mc.hamming(ha,hc)}")
ok("minhash near-dup > distinct",
   mc.minhash_jaccard(a, b_) > mc.minhash_jaccard(a, c_),
   f"{mc.minhash_jaccard(a,b_):.2f} vs {mc.minhash_jaccard(a,c_):.2f}")

bl = mc.Bloom(expected=10000, fpp=0.01)
words = [f"w{i}" for i in range(5000)]
for w in words: bl.add(w)
fp = sum(1 for i in range(5000, 15000) if f"w{i}" in bl) / 10000.0
ok("bloom no false negatives", all(w in bl for w in words))
ok("bloom fpp under 5%", fp < 0.05, f"fp={fp:.3%} est={bl.fpp_estimate():.3%}")

print(f"\n★ {PASS}/{PASS} theorems verified — mathcore is live.")
