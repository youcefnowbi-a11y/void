"""VOIDFORGE :: attack_graph — MCTS mission brain (model-predictive control).

The agent stops asking "what next" and starts COMPUTING it.

Model
-----
  State   S = (facts, exhausted)
          fact     = (kind, value)   kind ∈ {url, domain, subdomain, endpoint,
                                             js_bundle, secret, token, table,
                                             supabase_ref, anon_key, handle,
                                             har_file, tech, waf, vuln, data}
          exhausted= {(tool, target)} pairs already attempted
  Action  a = (tool, target) — gated by preconditions over facts
  Value   v(s,a) = yield(a) · novelty(s,a) · p̂(a) − λ · ĉ(a)
          yield    expected new facts per success (operator-calibrated prior)
          novelty  1 / (1 + 0.3 · |already-known kinds it would produce|)
          p̂, ĉ     empirical success rate & mean duration — from the bandit
                   (mathcore), which learns from every real mission run.
  Search  UCT (Kocsis & Szepesvári 2006):
              a* = argmax Q(s,a) + c·√(ln N(s) / N(s,a))
          rollouts are model-based: successors add the action's expected
          fact kinds, so chains emerge (js_mine -> bundle -> deobfuscate ->
          secrets). Commit-one-step-then-replan = receding horizon (MPC).
"""
import os, re, sys, math, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.mathcore import bandit_success_cost

# ── State primitives ─────────────────────────────────────────────────

class Fact:
    __slots__ = ("kind", "value")
    def __init__(self, kind, value):
        self.kind, self.value = kind, value
    def key(self):
        return (self.kind, self.value)
    def __repr__(self):
        return f"{self.kind}:{self.value}"


class State:
    __slots__ = ("facts", "exhausted")
    def __init__(self, facts=(), exhausted=()):
        self.facts = frozenset(facts)
        self.exhausted = frozenset(exhausted)
    def with_facts(self, new):
        return State(self.facts | frozenset(new), self.exhausted)
    def with_exhausted(self, pair):
        return State(self.facts, self.exhausted | {pair})
    def kinds(self, kind):
        return sorted(v for k, v in ((f.kind, f.value) for f in self.facts) if k == kind)
    def has(self, kind, contains=None):
        return any(f.kind == kind and (contains is None or contains in f.value)
                   for f in self.facts)
    def __repr__(self):
        return f"S({len(self.facts)} facts, {len(self.exhausted)} exhausted)"


# ── Action catalog ───────────────────────────────────────────────────
# Each entry: pre(facts) gate, targets(state) enumeration, kinds produced,
# yield prior (expected facts on success), args(target) builder.

# R2-5 : les builders d'args ne reçoivent que t — le dernier état réel visité
# par plan() sert de source pour dériver les args de frappe. Objectif :
# plan() ne peut plus jamais émettre un placeholder littéral "<… from intel>"
# en argument d'outil.
_LAST_ENDPOINTS = []


def _ep_fallback(t):
    """Premier endpoint connu de l'état courant, sinon la cible elle-même."""
    return _LAST_ENDPOINTS[0] if _LAST_ENDPOINTS else t


def _auth_base_fallback(t):
    """Base d'auth dérivée du state : premier endpoint /auth connu, sinon le
    premier endpoint, sinon la cible."""
    if _LAST_ENDPOINTS:
        for e in _LAST_ENDPOINTS:
            if "auth" in e:
                return e
        return _LAST_ENDPOINTS[0]
    return t


def _targets_kinds(state, *kinds, prefix_https=True):
    """Domain values usable as URLs."""
    out = list(state.kinds("url"))
    for d in state.kinds("domain"):
        out.append(f"https://{d}" if prefix_https else d)
    return sorted(set(out))


ACTIONS = {
    # ── RECON ──
    "web_fingerprint": {
        "pre": lambda s: s.has("url") or s.has("domain"),
        "targets": lambda s: _targets_kinds(s),
        "kinds": ("tech",), "yield": 2.0,
        "args": lambda t: {"url": t},
    },
    "waf_detect": {
        "pre": lambda s: s.has("url") or s.has("domain"),
        "targets": lambda s: _targets_kinds(s),
        "kinds": ("waf",), "yield": 1.0,
        "args": lambda t: {"url": t},
    },
    "subdomain_enum": {
        "pre": lambda s: s.has("domain"),
        "targets": lambda s: s.kinds("domain"),
        "kinds": ("domain",), "yield": 3.0,
        "args": lambda t: {"domain": t},
    },
    "wayback_urls": {
        "pre": lambda s: s.has("domain"),
        "targets": lambda s: s.kinds("domain"),
        "kinds": ("endpoint",), "yield": 2.0,
        "args": lambda t: {"domain": t},
    },
    "nmap_scan": {
        "pre": lambda s: s.has("domain"),
        "targets": lambda s: s.kinds("domain"),
        "kinds": ("endpoint",), "yield": 2.0,
        "args": lambda t: {"target": t},
    },
    # ── SURFACE ──
    "js_mine_site": {
        "pre": lambda s: s.has("url") or s.has("domain"),
        "targets": lambda s: _targets_kinds(s),
        "kinds": ("js_bundle", "endpoint", "secret"), "yield": 3.0,
        "args": lambda t: {"site": t},
    },
    "js_mine_url": {
        "pre": lambda s: s.has("js_bundle"),
        "targets": lambda s: s.kinds("js_bundle"),
        "kinds": ("endpoint", "secret"), "yield": 2.5,
        "args": lambda t: {"url": t},
    },
    "endpoint_oracle": {
        "pre": lambda s: s.has("url") or s.has("domain"),
        "targets": lambda s: _targets_kinds(s),
        "kinds": ("endpoint",), "yield": 2.5,
        "args": lambda t: {"base": t, "paths": ["api", "admin", "login", ".env",
                                                "robots.txt", "api/user", "graphql",
                                                "config", "backup", "api.php/me"]},
    },
    "spa_crawl": {
        "pre": lambda s: s.has("url"),
        "targets": lambda s: s.kinds("url"),
        "kinds": ("endpoint", "js_bundle"), "yield": 2.0,
        "args": lambda t: {"url": t},
    },
    "param_brute": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("endpoint",), "yield": 1.5,
        "args": lambda t: {"url": t},
    },
    "deploy_watch": {
        "pre": lambda s: s.has("url"),
        "targets": lambda s: s.kinds("url"),
        "kinds": ("endpoint",), "yield": 1.0,
        "args": lambda t: {"target": t},
    },
    "nuclei_scan": {
        "pre": lambda s: s.has("url"),
        "targets": lambda s: s.kinds("url"),
        "kinds": ("vuln",), "yield": 2.0,
        "args": lambda t: {"target": t},
    },
    # ── EXPLOIT CHAINS ──
    "secret_scan": {
        "pre": lambda s: s.has("js_bundle") or s.has("endpoint") or s.has("har_file"),
        "targets": lambda s: (s.kinds("js_bundle") + s.kinds("endpoint")
                              + s.kinds("har_file")),
        "kinds": ("secret",), "yield": 1.8,
        "args": lambda t: {"path": t},
    },
    "deobfuscate_js": {
        "pre": lambda s: s.has("js_bundle"),
        "targets": lambda s: s.kinds("js_bundle"),
        "kinds": ("endpoint", "secret"), "yield": 2.0,
        "args": lambda t: {"js_path": t},
    },
    "vm_string_dump": {
        "pre": lambda s: s.has("js_bundle"),
        "targets": lambda s: s.kinds("js_bundle"),
        "kinds": ("secret",), "yield": 1.5,
        "args": lambda t: {"js_path": t},
    },
    "sqli_probe_param": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("vuln",), "yield": 2.0,
        "args": lambda t: {"url_template": (t if "{" in t else t + "?q={INJ}")},
    },
    "ssrf_probe": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("vuln",), "yield": 1.5,
        "args": lambda t: {"url_template": t},
    },
    "graphql_introspect": {
        "pre": lambda s: s.has("endpoint", "graphql"),
        "targets": lambda s: [e for e in s.kinds("endpoint") if "graphql" in e],
        "kinds": ("table",), "yield": 3.0,
        "args": lambda t: {"base": t},
    },
    # ── EXPLOITATION (strike layer) ──
    "sqli_union_dump": {
        "pre": lambda s: s.has("endpoint") or s.has("vuln"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("data", "table"), "yield": 4.5,
        "args": lambda t: {"url_template": (t if "{" in t else t + "?id={INJ}")},
    },
    "sqli_blind_extract": {
        "pre": lambda s: s.has("vuln"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("data",), "yield": 3.0,
        "args": lambda t: {"url_template": (t if "{" in t else t + "?id={INJ}"),
                            "subquery": "SELECT version()"},
    },
    "cmd_exec_probe": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("rce",), "yield": 4.0,
        "args": lambda t: {"url_template": (t if "{" in t else t + "?q={INJ}")},
    },
    "ssti_detect_rce": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("rce", "vuln"), "yield": 3.5,
        "args": lambda t: {"url_template": (t if "{" in t else t + "?q={INJ}")},
    },
    "lfi_file_read": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("file_read",), "yield": 2.5,
        "args": lambda t: {"url_template": (t if "{" in t else t + "?page={INJ}")},
    },
    "jwt_forge_replay": {
        # R2-5 : gated sur un endpoint réel — plus de placeholder "<endpoint
        # from intel>", replay_url est dérivé du state (caché _LAST_ENDPOINTS).
        "pre": lambda s: (s.has("token") or s.has("anon_key")) and s.has("endpoint"),
        "targets": lambda s: (s.kinds("token") + s.kinds("anon_key"))[:4],
        "kinds": ("forged_token",), "yield": 3.5,
        "args": lambda t: {"token": t, "replay_url": _ep_fallback(t)},
    },
    "idor_enum": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: [e for e in s.kinds("endpoint")
                              if any(c in e for c in ("id", "user", "order", "/api"))] or s.kinds("endpoint"),
        "kinds": ("data",), "yield": 3.0,
        "args": lambda t: {"url_template": (t + "/{ID}" if not t.endswith("}") and "{ID}" not in t else t)},
    },
    "upload_webshell": {
        "pre": lambda s: s.has("endpoint", "upload") or s.has("endpoint"),
        "targets": lambda s: [e for e in s.kinds("endpoint") if "upload" in e] or s.kinds("endpoint"),
        "kinds": ("rce", "shell"), "yield": 5.0,
        # R2-5 : le répertoire uploads est dérivé de l'endpoint ciblé
        # (miroir de planner.py) — plus de placeholder "<uploads dir from intel>".
        "args": lambda t: {"upload_url": t,
                            "base_uploads_url": t.rstrip("/") + "/uploads/"},
    },
    "shell_session": {
        "pre": lambda s: s.has("shell"),
        "targets": lambda s: s.kinds("shell"),
        "kinds": ("data", "rce"), "yield": 3.5,
        "args": lambda t: {"shell_url": t},
    },
    # ── ZERO-DAY PIPELINE ──
    "fuzz_attack_surface": {
        "pre": lambda s: s.has("url") or s.has("domain") or s.has("endpoint"),
        "targets": lambda s: (s.kinds("endpoint") + _targets_kinds(s))[:6],
        "kinds": ("vuln",), "yield": 3.0,
        "args": lambda t: {"url": (t.split("?")[0] if t.startswith("http") else f"https://{t}")},
    },
    "crash_triage_next": {
        "pre": lambda s: s.has("vuln") or s.has("url"),
        "targets": lambda s: ["fuzz_findings"],
        "kinds": ("vuln",), "yield": 2.5,
        "args": lambda t: {},
    },
    "nday_exploit": {
        "pre": lambda s: s.has("tech") or s.has("vuln"),
        "targets": lambda s: (s.kinds("tech") + s.kinds("vuln"))[:6],
        "kinds": ("vuln", "poc"), "yield": 3.0,
        "args": lambda t: {"cve_id": (t if t.upper().startswith("CVE-") else None),
                            "keyword": (None if t.upper().startswith("CVE-") else t)},
    },
    # ── SUPPORT ACTIONS (offline brain reachability) ──
    "jwt_analyst": {
        "pre": lambda s: s.has("token") or s.has("anon_key"),
        "targets": lambda s: (s.kinds("token") + s.kinds("anon_key"))[:4],
        "kinds": ("vuln",), "yield": 1.5,
        "args": lambda t: {"token": t},
    },
    "auth_metadata_poison": {
        # R2-5 : gated sur un endpoint réel — base dérivée du state,
        # plus de placeholder "<auth base from intel>".
        "pre": lambda s: s.has("token") and s.has("endpoint"),
        "targets": lambda s: s.kinds("token")[:3],
        "kinds": ("vuln",), "yield": 1.8,
        "args": lambda t: {"base": _auth_base_fallback(t), "token": t},
    },
    "dir_brute": {
        "pre": lambda s: s.has("url") or s.has("domain") or s.has("endpoint"),
        "targets": lambda s: (s.kinds("endpoint") + _targets_kinds(s))[:4],
        "kinds": ("endpoint",), "yield": 2.5,
        "args": lambda t: {"base": (t if t.startswith("http") else f"https://{t}")},
    },
    "ip_intel": {
        "pre": lambda s: s.has("domain") or s.has("url"),
        "targets": lambda s: [d for d in (s.kinds("domain") + s.kinds("url"))][:4],
        "kinds": ("service",), "yield": 1.2,
        "args": lambda t: {"ip_or_host": t.replace("https://", "").replace("http://", "").split("/")[0]},
    },
    "port_scan_sync": {
        "pre": lambda s: s.has("domain"),
        "targets": lambda s: s.kinds("domain")[:3],
        "kinds": ("service",), "yield": 1.5,
        "args": lambda t: {"host": t},
    },
    "idor_b64_walk": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: [e for e in s.kinds("endpoint")
                              if any(c in e for c in ("id", "user", "order", "/api"))] or s.kinds("endpoint"),
        "kinds": ("data",), "yield": 2.5,
        "args": lambda t: {"url_template": (t + "/{ID}" if "{ID}" not in t else t)},
    },
    "tg_market_scan": {
        "pre": lambda s: s.has("handle"),
        "targets": lambda s: s.kinds("handle")[:6],
        "kinds": ("handle",), "yield": 1.5,
        "args": lambda t: {"handles": [t.lstrip("@")]},
    },
    # ── ADVANCED WEB STRIKE (gap-matrix additions) ──
    "race_smash": {
        "pre": lambda s: s.has("endpoint") or s.has("url"),
        "targets": lambda s: [e for e in s.kinds("endpoint")
                              if any(k in e.lower() for k in
                                     ("auth", "login", "vote", "coupon", "reset",
                                      "withdraw", "redeem", "order", "pay", "apply"))]
                              or s.kinds("endpoint")[:4],
        "kinds": ("data",), "yield": 2.5,
        "args": lambda t: {"url": t},
    },
    "smuggle_probe": {
        "pre": lambda s: s.has("url") or s.has("domain") or s.has("endpoint"),
        "targets": lambda s: (s.kinds("url") + _targets_kinds(s) + s.kinds("endpoint"))[:3],
        "kinds": ("vuln",), "yield": 3.0,
        "args": lambda t: {"url": t if t.startswith("http") else f"https://{t}"},
    },
    "proto_pollute": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: [e for e in s.kinds("endpoint")
                              if any(k in e for k in ("/api", "/profile", "/settings", "/merge"))]
                              or s.kinds("endpoint")[:4],
        "kinds": ("vuln",), "yield": 2.2,
        "args": lambda t: {"url": t, "gadget_check": t.rsplit("/", 1)[0] + "/profile"},
    },
    "xxe_probe": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: [e for e in s.kinds("endpoint")
                              if any(k in e.lower() for k in
                                     (".xml", "saml", "soap", "rss", "feed", "import", "parse"))]
                              or s.kinds("endpoint")[:4],
        "kinds": ("data",), "yield": 2.5,
        "args": lambda t: {"url": t},
    },
    "redirect_cast": {
        "pre": lambda s: s.has("endpoint"),
        "targets": lambda s: [e for e in s.kinds("endpoint")
                              if any(k in e.lower() for k in
                                     ("login", "auth", "sso", "oauth", "callback",
                                      "redirect", "out", "go"))] or s.kinds("endpoint")[:4],
        "kinds": ("vuln",), "yield": 1.8,
        "args": lambda t: {"url": t},
    },
    "c2_pulse": {
        "pre": lambda s: s.has("endpoint", "cmd=") or s.has("endpoint", "{CMD}"),
        "targets": lambda s: [e for e in s.kinds("endpoint") if "cmd=" in e or "{CMD}" in e][:3],
        "kinds": ("data",), "yield": 2.0,
        "args": lambda t: {"shell_url": t},
    },
    # ── BAAS / DATA ──
    "supabase_exfil": {
        "pre": lambda s: s.has("supabase_ref") and s.has("anon_key"),
        "targets": lambda s: [f"{r}|{k}" for r in s.kinds("supabase_ref")
                              for k in s.kinds("anon_key")],
        "kinds": ("table", "data"), "yield": 4.0,
        "args": lambda t: dict(zip(("project_ref", "anon_key"), t.split("|", 1))),
    },
    "supabase_full_assault": {
        "pre": lambda s: s.has("supabase_ref") and s.has("anon_key"),
        "targets": lambda s: [f"{r}|{k}" for r in s.kinds("supabase_ref")
                              for k in s.kinds("anon_key")],
        "kinds": ("table", "data", "token"), "yield": 3.5,
        "args": lambda t: dict(zip(("project_ref", "anon_key"), t.split("|", 1))),
    },
    "auth_signup_probe": {
        "pre": lambda s: s.has("supabase_ref") or s.has("endpoint", "auth"),
        "targets": lambda s: (s.kinds("supabase_ref")
                              or [e for e in s.kinds("endpoint") if "auth" in e]),
        "kinds": ("token",), "yield": 2.0,
        "args": lambda t: {"base": t if t.startswith("http") else f"https://{t}.supabase.co"},
    },
    "realtime_tap": {
        "pre": lambda s: s.has("supabase_ref") and s.has("table"),
        "targets": lambda s: s.kinds("table"),
        "kinds": ("data",), "yield": 2.0,
        "args": lambda t: {"table": t},
    },
    "data_extract": {
        "pre": lambda s: s.has("endpoint") and (s.has("token") or s.has("secret")),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("data",), "yield": 3.0,
        "args": lambda t: {"url": t},
    },
    "data_dump_paginated": {
        "pre": lambda s: s.has("table") or s.has("data"),
        "targets": lambda s: s.kinds("table") or s.kinds("data"),
        "kinds": ("data",), "yield": 3.0,
        "args": lambda t: {"table": t},
    },
    "api_sweep": {
        "pre": lambda s: len(s.kinds("endpoint")) >= 2 and (s.has("token") or s.has("secret")),
        "targets": lambda s: s.kinds("endpoint"),
        "kinds": ("data",), "yield": 3.5,
        "args": lambda t: {"base": t},
    },
    # ── FORENSICS / OSINT ──
    "har_dissect": {
        "pre": lambda s: s.has("har_file"),
        "targets": lambda s: s.kinds("har_file"),
        "kinds": ("endpoint", "token"), "yield": 3.0,
        "args": lambda t: {"har_path": t},
    },
    "har_tokens": {
        "pre": lambda s: s.has("har_file"),
        "targets": lambda s: s.kinds("har_file"),
        "kinds": ("token", "secret"), "yield": 2.0,
        "args": lambda t: {"har_path": t},
    },
    "tg_probe": {
        "pre": lambda s: s.has("handle"),
        "targets": lambda s: s.kinds("handle"),
        "kinds": ("handle", "token"), "yield": 2.0,
        "args": lambda t: {"handles": [t]},
    },
    "tg_history_harvest": {
        "pre": lambda s: s.has("handle"),
        "targets": lambda s: s.kinds("handle"),
        "kinds": ("data", "secret"), "yield": 2.5,
        "args": lambda t: {"channel": t, "pages": 8},
    },
    # ── INTEL ──
    "nvd_search": {
        "pre": lambda s: s.has("tech"),
        "targets": lambda s: s.kinds("tech"),
        "kinds": ("vuln",), "yield": 1.5,
        "args": lambda t: {"keyword": t},
    },
    "cisa_kev": {
        "pre": lambda s: s.has("tech"),
        "targets": lambda s: s.kinds("tech"),
        "kinds": ("vuln",), "yield": 1.2,
        "args": lambda t: {"keyword": t},
    },
}

_LAMBDA_COST = 0.05   # value penalty per normalized second of tool runtime
_EPS_STOP = 0.08      # marginal value below which the plan stops


# ── Value model ──────────────────────────────────────────────────────

def value(state, tool, target):
    a = ACTIONS[tool]
    produced = sum(1 for f in state.facts if f.kind in a["kinds"])
    novelty = 1.0 / (1.0 + 0.3 * produced)
    p, dur = bandit_success_cost(tool)
    dur_n = min(dur / 30.0, 1.0)      # 30s runtime = maximal cost
    return a["yield"] * novelty * p - _LAMBDA_COST * dur_n


def available(state):
    """All legal (tool, target, value) actions for a state."""
    out = []
    for tool, a in ACTIONS.items():
        if not a["pre"](state):
            continue
        for t in a["targets"](state):
            if (tool, t) in state.exhausted:
                continue
            out.append((tool, t, value(state, tool, t)))
    return sorted(out, key=lambda x: -x[2])


def successor(state, tool, target):
    """Model step: run the action in imagination — add its expected fact kinds."""
    a = ACTIONS[tool]
    new = [Fact(k, target) for k in a["kinds"]]
    return state.with_facts(new).with_exhausted((tool, target))


# ── MCTS (UCT) ───────────────────────────────────────────────────────

class _Node:
    __slots__ = ("state", "N", "W", "children")
    def __init__(self, state):
        self.state, self.N, self.W, self.children = state, 0, 0.0, {}


def _rollout(state, depth, rng, tau=0.5):
    """Boltzmann (softmax) rollout through the world model; returns total value.
    Exploration temperature τ over the FULL legal action set instead of
    ε-greedy over a truncated top-third: the entropy budget comes from τ and
    every action keeps a nonzero probability, so low-prior chains that only
    look bad early can still be discovered by the search."""
    total, s = 0.0, state
    for _ in range(depth):
        acts = available(s)
        if not acts:
            break
        vs = [v for _, _, v in acts]
        m = max(vs)
        ws = [math.exp((v - m) / tau) for v in vs]
        r = rng.random() * sum(ws)
        acc, pick = 0.0, acts[-1]
        for a, w in zip(acts, ws):
            acc += w
            if acc >= r:
                pick = a
                break
        tool, t, v = pick
        total += v
        s = successor(s, tool, t)
    return total


def search(root_state, sims=200, depth=6, c_uct=1.2, seed=7, gamma=0.65):
    """One MCTS search from root_state. Returns {action: (Q, N)} at root.

    Backpropagated return follows the discounted-edge-reward form:
        G = v0 + γ·v1 + γ²·v2 + … + γ^d·R(leaf)
    where v_i are the model values of the actions actually traversed and R is
    the Boltzmann rollout from the expanded leaf. γ models mission-interruption
    risk: intelligence not banked early is intelligence at risk (targets patch,
    operators get cut off). This anchors each root edge's Q in its OWN value
    while downstream potential still differentiates subtrees."""
    rng = random.Random(seed)
    root = _Node(root_state)
    root_prior = {a[:2]: a[2] for a in available(root_state)}
    for _ in range(sims):
        node, path, edge_vals = root, [], []
        # — Selection: descend by UCT over EXPANDED children only —
        # Progressive widening (Couëtoux et al. 2011): a node may hold at most
        # w(N) = ⌈2√N⌉+1 children, so branching grows with visit evidence
        # instead of exploding combinatorially on wide states.
        while True:
            acts = available(node.state)
            if not acts:
                break
            vmap = {a[:2]: a[2] for a in acts}
            widening = int(math.ceil(2.0 * math.sqrt(max(node.N, 1)))) + 1
            untried = [a[:2] for a in acts if a[:2] not in node.children]
            if untried and len(node.children) < widening:
                # — Expansion: best-valued untried action within the widening cap —
                tool, t = max(untried, key=lambda a: vmap[a])
                edge_vals.append(vmap[(tool, t)])
                path.append(node)
                node = _Node(successor(node.state, tool, t))
                path[-1].children[(tool, t)] = node
                break
            if not node.children:
                # widening cap says stop expanding but nothing is expanded yet
                # (only possible at N=0) — force-expand the best action.
                tool, t = max(vmap, key=vmap.get)
                edge_vals.append(vmap[(tool, t)])
                path.append(node)
                node = _Node(successor(node.state, tool, t))
                path[-1].children[(tool, t)] = node
                break
            t_log = math.log(max(node.N, 1))
            def uct(item):
                ch = node.children[item]
                q = (ch.W / ch.N) if ch.N else root_prior.get(item, 0.0)
                return q + c_uct * math.sqrt(t_log / max(ch.N, 1))
            best = max(node.children, key=uct)
            edge_vals.append(vmap[best])
            path.append(node)
            node = node.children[best]
        # — Simulation —
        reward = _rollout(node.state, depth, rng)
        # — Backpropagation: per-edge anchoring (R2-1) — chaque nœud reçoit le
        #   retour ancré sur l'ARÊTE QUI L'A CRÉÉ (v_in + gamma·suite), pas le
        #   total ancré racine qui décalait tous les Q profonds par la valeur
        #   de leurs ancêtres. La racine garde le total complet (décision de
        #   chaîne, identique à l'ancien classement des enfants directs) et
        #   n'est plus comptée deux fois.
        G = (edge_vals[-1] + gamma * reward) if edge_vals else reward
        node.W += G
        node.N += 1
        for i in range(len(path) - 1, 0, -1):
            G = edge_vals[i - 1] + gamma * G
            path[i].W += G
            path[i].N += 1
        if path:
            path[0].W += G
            path[0].N += 1
    return {a: ((ch.W / ch.N) if ch.N else root_prior.get(a, 0.0), ch.N)
            for a, ch in root.children.items()}


def plan(state, max_steps=8, sims=150, seed=7):
    """Receding-horizon planner: search -> commit highest-Q root action
    (visits as tie-break) -> advance the imagined state -> repeat. Returns
    [(tool, args)] terminating when marginal value drops below _EPS_STOP
    or no legal actions remain."""
    global _LAST_ENDPOINTS
    steps, cur = [], state
    for _ in range(max_steps):
        acts = available(cur)
        if not acts:
            break
        results = search(cur, sims=sims, seed=seed)
        if not results:
            break
        (tool, t) = max(results,
                       key=lambda k: (results[k][0], results[k][1]))
        q, _n = results[(tool, t)]
        if q < _EPS_STOP:
            break
        # R2-5 : l'état courant (réel + faits imaginés) alimente les
        # dérivations d'args — la gate `pre` garantit qu'il contient au moins
        # un endpoint au moment où l'action est commise.
        _LAST_ENDPOINTS = sorted(set(cur.kinds("endpoint")))
        args = ACTIONS[tool]["args"](t)
        steps.append((tool, args))
        cur = successor(cur, tool, t)
    return steps


# ── Mission text -> initial state ────────────────────────────────────

def extract_state(mission):
    """Parse a natural-language mission into a starting belief state."""
    from core.planner import extract_target, extract_path
    facts = []
    t = extract_target(mission)
    if t:
        dom = re.sub(r"^https?://", "", t).split("/")[0]
        facts.append(Fact("url", t.rstrip("/")))
        facts.append(Fact("domain", dom))
    p = extract_path(mission)
    if p and p.endswith(".har"):
        facts.append(Fact("har_file", p))
    for ref in re.findall(r"\b([a-z0-9]{18,22})\.supabase\.co", mission):
        facts.append(Fact("supabase_ref", ref))
    for key in re.findall(r"(eyJhbGci[A-Za-z0-9_\-.]+)", mission):
        facts.append(Fact("anon_key", key))
    for h in re.findall(r"@([A-Za-z0-9_]{4,32})", mission):
        facts.append(Fact("handle", h))
    for kw in ("supabase", "telegram", "graphql"):
        if kw in mission.lower() and not any(f.kind == "tech" for f in facts):
            facts.append(Fact("tech", kw))
    return State(facts)


def plan_smart(mission, max_steps=8, sims=120):
    """Natural-language mission -> MCTS-optimized tool chain (offline, no LLM).
    Falls back to empty list if no target detected (caller then uses the
    keyword planner)."""
    st = extract_state(mission)
    if not st.facts:
        return []
    return plan(st, max_steps=max_steps, sims=sims)
