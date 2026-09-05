"""VOIDFORGE :: Ω2 adversarial twin (Phase 2 — the doubter).

Law #2: NO VERDICT WITHOUT PROOF. Every CONFIRMED finding passes a
standing challenger before it can enter the report. The twin is injected
as POLICY (metasploit AutoCheck prepend — the verify gate runs whether
the caller remembered it or not), never as a tool to forget.

Three weapons (stolen, grafted):

2.1 TWIN CALL — a second LLM pass whose standing doctrine is "this is
    wrong; prove it." Argues: honeypot? canary? detection bait?
    soft-mirror? misread status? The twin returns ATTACKED/SURVIVED
    with its arguments. Falls back DETERMINISTICALLY when the LLM is
    unavailable (offline mode: the truth table + blind-verdict policy
    still run — the twin is never a single point of failure).

2.2 TRUTH TABLE — sqlmap checkFalsePositives, our shape: with fresh
    distinct randoms r1≠r2≠r3, the oracle MUST answer r1=r1 → True,
    r1=r2 → False, invalid → False. An always-true, always-false, or
    echoing page cannot pass. Fired on boolean-oracle verdicts.

2.3 RELIABILITY RANKS — metasploit MinimumRank, our shape: per-tool
    rank from the trajectory (observed success + hard-evidence states);
    low-rank evidence carries a discount the twin cites. Ranks refresh
    from trajectory stats; a tool that lied once weighs less until it
    re-proves.

2.4 BLIND-VERDICT POLICY — a blind class (no inline differential) is
    CONFIRMED only with an OOB callback receipt. No receipt → the
    verdict caps at 'partial' with proof: null visible to the operator.

Determinism floor: the truth table + rank lookup + blind policy are
pure arithmetic — they run even with a dead LLM. The LLM twin call is
the second opinion layered on top, never the gate itself.
"""
import json
import random
import re
import threading
import time

_LOCK = threading.Lock()
_RANKS = {}                # tool -> {"rank": float, "runs": int, "ts": float}
_TWIN_CACHE = {}           # verdict-key -> twin verdict (dedup within mission)
_TWIN_CACHE_MAX = 256
_LLM_BUDGET = {"calls": 0, "max": 40, "window_start": time.time(),
               "window": 3600.0}   # ≤40 twin calls per hour (cost discipline)

# sqlmap truth-table constants (checkFalsePositives, our shape)
_TRUTH_REPS = 2            # sqlmap: repeated conf.level times — ours: 2


# ── 2.3: reliability ranks (MinimumRank, our shape) ───────────────────

def refresh_ranks(trajectory_stats=None):
    """Recompute per-tool ranks from the trajectory's own evidence.
    trajectory_stats: {tool: {"runs": n, "wins": w, "hard": h}} where
    hard = runs whose evidence_state landed confirmed/exploited. If not
    provided, ranks stay as-is (the caller decides when to recompute).
    Rank = wins/runs weighted by hard-evidence ratio, 0.0..1.0."""
    if not isinstance(trajectory_stats, dict):
        return
    with _LOCK:
        for tool, st in trajectory_stats.items():
            if not isinstance(st, dict):
                continue      # garbage entry: skip, never kill the refresh
            try:
                runs = int((st or {}).get("runs") or 0)
                wins = int((st or {}).get("wins") or 0)
                hard = int((st or {}).get("hard") or 0)
            except (TypeError, ValueError):
                continue
            if runs < 3:
                # not enough evidence: neutral rank, no discount yet
                _RANKS[tool] = {"rank": 0.5, "runs": runs, "ts": time.time()}
                continue
            base = wins / runs
            hard_ratio = hard / runs
            rank = round(0.6 * base + 0.4 * hard_ratio, 3)
            _RANKS[tool] = {"rank": min(max(rank, 0.0), 1.0), "runs": runs,
                            "ts": time.time()}


def rank_of(tool):
    """The reliability rank a verdict from this tool carries (1.0 =
    trusted blindly; below TWIN_DISCOUNT the twin cites it as weak)."""
    with _LOCK:
        e = _RANKS.get(tool or "")
        return e["rank"] if e else 0.5


def refresh_from_trajectory():
    """Bridge to the archive: rebuild ranks from the trajectory's raw
    events (runs = all, wins = ok, hard = confirmed/exploited states).
    Called once per mission start — cheap (tail-limited by the archive
    reader) and best-effort (a broken archive never kills a mission)."""
    try:
        from core import trajectory as _traj
        from collections import defaultdict
        stats = defaultdict(lambda: {"runs": 0, "wins": 0, "hard": 0})
        for e in _traj._events():
            t = e.get("tool")
            if not t:
                continue
            s = stats[t]
            s["runs"] += 1
            if e.get("ok"):
                s["wins"] += 1
            if e.get("state") in ("confirmed", "exploited"):
                s["hard"] += 1
        refresh_ranks(dict(stats))
    except Exception:
        pass


TWIN_DISCOUNT = 0.35        # below this rank the twin ATTACKS harder


def rank_note(tool):
    """Deterministic discount citation for the twin's argument list."""
    r = rank_of(tool)
    if r < TWIN_DISCOUNT:
        return (f"tool '{tool}' carries reliability rank {r:.2f} — its past "
                f"runs mislead often; demand re-proof")
    return None


# ── 2.2: the truth table (checkFalsePositives, our shape) ──────────────

def truth_table(oracle_fn, reps=_TRUTH_REPS):
    """sqlmap's FP killer: with FRESH randoms per rep, the oracle must
    answer r1==r1 True, r1==r2 False, r1==r3 False, and an INVALID
    statement False. An always-true page (honeypot), an always-false
    page (broken), or an echoing page (reflects the payload verbatim)
    cannot pass.

    oracle_fn(true_statement: str, probe: str) -> bool — the caller's
    boolean oracle (e.g. page differs vs not). Returns (passed: bool,
    table: the printed truth table for evidence).
    """
    table = []
    try:
        for rep in range(reps):
            r1 = random.randint(10**8, 10**9 - 1)
            r2 = random.randint(10**8, 10**9 - 1)
            r3 = random.randint(10**8, 10**9 - 1)
            while r2 == r1:
                r2 = random.randint(10**8, 10**9 - 1)
            while r3 in (r1, r2):
                r3 = random.randint(10**8, 10**9 - 1)
            must_true = oracle_fn(f"{r1}={r1}", f"{r1}={r1}")
            must_false1 = oracle_fn(f"{r1}={r2}", f"{r1}={r2}")
            must_false2 = oracle_fn(f"{r1}={r3}", f"{r1}={r3}")
            invalid = oracle_fn(f"{r1} {r2}", f"{r1} {r2}")
            row = {"rep": rep,
                   "must_true": must_true,
                   "must_false1": must_false1,
                   "must_false2": must_false2,
                   "invalid": invalid}
            table.append(row)
            if not (must_true is True and must_false1 is False
                    and must_false2 is False and invalid is False):
                return False, table
        return True, table
    except Exception:
        return False, table


# ── 2.4: blind-verdict policy ──────────────────────────────────────────

def blind_policy(tool_out):
    """A blind-class verdict is CONFIRMED only with an OOB receipt —
    BUT an inline-confirmed verdict (differential observed on the wire)
    is legitimate proof too. The cap fires ONLY on contradiction:
    exploitable=True with zero inline signals AND no callback = an
    unsupported claim. ssrf_test/xxe_probe structures:

      oob.callback_received: bool, oob.proof: str|None,
      proof_object: {...protocol, token...}|None (ssrf: signals_found: int)

    Returns (adjusted_output_or_True, note) — True means "confirmed,
    cite the note"; adjusted_output is the capped JSON; (None, None) =
    not blind-class or honestly inline-confirmed (pass through).
    """
    try:
        d = json.loads(tool_out) if isinstance(tool_out, str) else (tool_out or {})
    except Exception:
        return None, None
    if not isinstance(d, dict):
        return None, None
    oob = d.get("oob")
    if not isinstance(oob, dict):
        return None, None                       # not a blind-class output
    received = bool(oob.get("callback_received"))
    proof_obj = d.get("proof_object")
    # final-audit fix #4 (HIGH): xxe_probe passes its receipt as
    # oob={url, callback_received, proof} with NO top-level proof_object —
    # genuine callbacks fell through to the contradiction path and were
    # falsely capped at "partial" (systematic suppression of true xxe
    # findings). Fall back to the oob-embedded proof dict.
    if not isinstance(proof_obj, dict) and isinstance(oob.get("proof"), dict):
        proof_obj = oob["proof"]
    if received and isinstance(proof_obj, dict):
        return True, (f"blind verdict CONFIRMED by OOB callback "
                      f"({proof_obj.get('protocol')}, token "
                      f"{proof_obj.get('token')})")
    if d.get("exploitable") is not True:
        return None, None                       # already honest (hypothesis)
    # exploitable=True without receipt: legitimate IF inline signals
    # back it (metadata leak, 2+ vectors — the tool's own inline logic)
    sig = d.get("signals_found")
    if isinstance(sig, int) and sig > 0:
        return None, None                       # inline-confirmed: pass
    # contradiction: confirmed with NO inline differential and NO callback
    d["exploitable"] = "partial"
    d["proof_object"] = None
    d["twin_note"] = ("claimed exploitable with zero inline signals and "
                      "no OOB receipt — capped at partial (law #2: no "
                      "verdict without proof)")
    return json.dumps(d, ensure_ascii=False), d["twin_note"]


# ── 2.1: the twin call (LLM challenger, budgeted, cached) ──────────────

_TWIN_DOCTRINE = (
    "You are the ADVERSARIAL TWIN of an offensive-security agent. Your "
    "standing doctrine: the finding below is WRONG. Attack it: honeypot? "
    "canary token planted for scanners? detection bait (honeypot field "
    "served to make tools scream)? soft-mirror (dev/prod parity)? "
    "misread status (403 vs 404)? reflected payload mistaken for "
    "server-side execution? default-credential page that fakes success? "
    "Answer STRICT JSON: {\"attack\": \"SUSTAINED\"|\"OVERRULED\", "
    "\"arguments\": [\"...\"], \"reproof\": \"one concrete re-proof "
    "that would settle it\"}. OVERRULED only if the finding survives "
    "your best attack. Be brief and concrete."
)

_CFG = None                # agent cfg (provider) — set by configure()


def configure(cfg):
    """Bind the twin to the agent's provider config (call from
    Agent.__init__ / wherever a mission starts). Pass None to unbind."""
    global _CFG
    _CFG = cfg if isinstance(cfg, dict) and "provider" in cfg else None


def _budget_ok():
    """≤ max twin calls per window (cost discipline — the twin is a
    second opinion, not a mission of its own)."""
    with _LOCK:
        now = time.time()
        if now - _LLM_BUDGET["window_start"] > _LLM_BUDGET["window"]:
            _LLM_BUDGET["window_start"] = now
            _LLM_BUDGET["calls"] = 0
        if _LLM_BUDGET["calls"] >= _LLM_BUDGET["max"]:
            return False
        _LLM_BUDGET["calls"] += 1
        return True


def _verdict_key(tool, out):
    return f"{tool}:{hash(str(out)[:600]) & 0xFFFFFFFFFFFF:x}"


def twin_attack(tool, out, target=""):
    """Run the challenger on a CONFIRMED verdict. Deterministic-first:
    rank discount + blind policy ride along; the LLM twin call is the
    second opinion (cached per identical verdict; budgeted hourly;
    offline → deterministic-only verdict). Returns the twin record:

    {"attacked": bool, "survived": bool, "arguments": [...],
     "reproof": str, "deterministic_only": bool}
    """
    rec = {"attacked": False, "survived": True, "arguments": [],
           "reproof": "", "deterministic_only": True}
    # deterministic weapons first
    args_ = []
    rn = rank_note(tool)
    if rn:
        args_.append(rn)
    bp_out, bp_note = blind_policy(out)
    if bp_note:
        args_.append(bp_note)
    rec["arguments"] = args_
    # cached verdict?
    key = _verdict_key(tool, out)
    with _LOCK:
        cached = _TWIN_CACHE.get(key)
    if cached is not None:
        rec.update(cached)
        rec["cached"] = True
        return rec
    # LLM twin call (budgeted; skips silently offline/unconfigured/at cap)
    try:
        if _CFG is not None and _budget_ok():
            from core.llm import LLM
            p = _CFG["provider"]
            _twin_llm = LLM(p["base_url"], p["api_key"], p["model"],
                            temperature=0.2)
            msgs = [{"role": "user", "content":
                     _TWIN_DOCTRINE
                     + f"\n\nTARGET: {str(target)[:120]}\nTOOL: {tool}\n"
                       f"FINDING OUTPUT:\n{str(out)[:3000]}"}]
            resp = _twin_llm.chat(msgs, max_tokens=400)
            content = ((resp or {}).get("content") or "") if isinstance(
                resp, dict) else str(resp or "")
            content = str(content).strip()
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                d = json.loads(m.group(0))
                rec["attacked"] = True
                rec["survived"] = str(d.get("attack")) == "OVERRULED"
                rec["arguments"] = (rec["arguments"] or []) + [
                    str(a)[:200] for a in (d.get("arguments") or [])[:4]]
                rec["reproof"] = str(d.get("reproof") or "")[:300]
                rec["deterministic_only"] = False
                with _LOCK:
                    if len(_TWIN_CACHE) > _TWIN_CACHE_MAX:
                        for k in list(_TWIN_CACHE)[:len(_TWIN_CACHE) - _TWIN_CACHE_MAX]:
                            _TWIN_CACHE.pop(k, None)
                    _TWIN_CACHE[key] = {k: rec[k] for k in
                                        ("attacked", "survived", "arguments",
                                         "reproof", "deterministic_only")}
    except Exception:
        pass
    return rec


def twin_note(rec):
    """Render the twin record as the tool-result/report citation."""
    if not rec or (not rec.get("attacked") and not rec.get("arguments")):
        return ""
    head = "[Ω2 TWIN]"
    if rec.get("survived") and rec.get("attacked"):
        head = "[Ω2 TWIN ✓ SURVIVED]"
    elif rec.get("attacked"):
        head = "[Ω2 TWIN ✗ SUSTAINED ATTACK]"
    args_s = "; ".join(rec.get("arguments") or [])[:400]
    out = f"\n\n{head} {args_s}"
    if rec.get("reproof"):
        out += f" — re-proof: {rec['reproof']}"
    return out


def reset():
    """Test hygiene / mission reset (cache cleared; ranks persist —
    they are cross-mission evidence, not mission state)."""
    with _LOCK:
        _TWIN_CACHE.clear()
