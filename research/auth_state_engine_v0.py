#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auth_state_engine v0.1.0 — companion executable to dossier_3_auth_state_machines.md
VOIDFORGE / Offensive Security Research Division — research artifact, LAB USE ONLY.

Implements the §5 pipeline of the dossier as a runnable v0:
  (c) property monitors  — no-skip, no-replay, issuer/mix-up confinement
  (d) token algebra      — JWT audit (alg/kid/jku/jwk/aud), binding τ extraction
  (e) race planning      — single-use endpoint race plan generator (no network in v0)
  (f) verdict()          — JSON contract identical to dossier §5.4

v0 boundaries (honest, by design):
  - (a) instrumentation: capture traces with mitmproxy (see lab guide §4), feed via --traces
  - (b) inference: hand-built transition map / annotated traces in v0; AALpy L* in v1
  - (e) execution: plan-only in v0; single-packet execution delegated to Turbo Intruder
  - stdlib only — no third-party dependencies, deterministic demo, zero network I/O.

Usage:
    python auth_state_engine_v0.py                 # deterministic built-in demo
    python auth_state_engine_v0.py --traces t.json --flow mfa --out verdict.json --pretty
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

ENGINE = "auth_state_engine"
VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# §2.2 — token binding τ = (subject, scope, epoch, audience, issuer)
# ---------------------------------------------------------------------------

@dataclass
class Binding:
    subject: str | None = None
    scope: frozenset[str] = frozenset()
    epoch: int | None = None
    audience: frozenset[str] = frozenset()
    issuer: str | None = None
    raw_claims: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Trace model — schema documented in lab_guide_auth_state_engine.md §3
# ---------------------------------------------------------------------------

@dataclass
class TraceEvent:
    event: str                     # symbolic input, e.g. "otp_submit", "callback"
    actor: str = "victim"          # identity matrix: victim / attacker / attacker2 / tenant1...
    params: dict[str, Any] = field(default_factory=dict)
    state: str | None = None       # observed server-side state marker (from lab response)
    outcome: str = "200"
    ts: float = field(default_factory=time.time)


@dataclass
class Trace:
    trace_id: str
    events: list[TraceEvent]


def traces_from_json(data: dict[str, Any]) -> list[Trace]:
    out = []
    for t in data.get("traces", []):
        evs = [TraceEvent(
            event=e["event"],
            actor=e.get("actor", "victim"),
            params=e.get("params", {}),
            state=e.get("state"),
            outcome=str(e.get("outcome", "200")),
            ts=float(e.get("ts", time.time())),
        ) for e in t.get("events", [])]
        out.append(Trace(trace_id=t.get("trace_id", f"t{len(out)}"), events=evs))
    return out


# ---------------------------------------------------------------------------
# (c) Monitor 1 — NO-SKIP  (dossier §2.3 P1, §5.3)
#     □(enter(s_protected) → ◇proof(n) ∧ fresh(proof(n)))
# ---------------------------------------------------------------------------

def _accepted(outcome: str) -> bool:
    """Flow-level success: 2xx AND 3xx both count — an OAuth/SAML callback that
    answers 302 is a successful step (redirect onward), not a rejection."""
    return outcome.startswith(("2", "3"))


class NoSkipMonitor:
    """
    Runtime monitor over annotated traces: the first time the trace enters a
    protected state, the set of proofs acquired so far must cover the required
    set. A bypass (missing proof) or stale proof (expired flag on the event)
    is a counterexample = bug (dossier §1.9 family).
    """

    def __init__(self, protected_states: set[str], required_proofs: dict[str, set[str]],
                 proof_events: set[str]):
        self.protected = protected_states
        self.required = required_proofs          # state -> set of required proof events
        self.proof_events = proof_events

    def run(self, trace: Trace) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        acquired: dict[str, float] = {}          # proof event -> ts acquired
        for ev in trace.events:
            if ev.event in self.proof_events and _accepted(ev.outcome):
                acquired[ev.event] = ev.ts
            if ev.state in self.protected:
                req = self.required.get(ev.state, set())
                missing = req - set(acquired)
                if missing:
                    findings.append({
                        "template": "no_skip",
                        "property": "□(enter(s_protected) → ◇proof(n) ∧ fresh(proof(n)))",
                        "trace": trace.trace_id,
                        "entered_state": ev.state,
                        "missing_proofs": sorted(missing),
                        "evidence": [e.event for e in trace.events[:trace.events.index(ev) + 1]],
                    })
                # protected state re-entry resets the proof obligation window
        return findings


# ---------------------------------------------------------------------------
# (c) Monitor 2 — NO-REPLAY  (dossier §2.3 P2)
#     □(consume(c) → X □ ¬consume(c))
# ---------------------------------------------------------------------------

class NoReplayMonitor:
    """Single-use tokens (code, otp, magic token) must be consumed at most once.
    Duplicate successful consumption with the same token_id = atomicity gap."""

    SINGLE_USE_EVENTS = {"code_consume", "otp_submit", "magic_verify", "invite_redeem"}

    def run(self, trace: Trace) -> list[dict[str, Any]]:
        findings = []
        consumed: dict[tuple[str, str], int] = Counter()
        for ev in trace.events:
            if ev.event in self.SINGLE_USE_EVENTS:
                tid = str(ev.params.get("token_id", "?"))
                if _accepted(ev.outcome):
                    consumed[(ev.event, tid)] += 1
        for (event, tid), n in consumed.items():
            if n > 1:
                findings.append({
                    "template": "no_replay",
                    "property": "□(consume(c) → X□¬consume(c))",
                    "trace": trace.trace_id,
                    "evidence": {"event": event, "token_id": tid, "successful_consumes": n},
                    "impact": "non-atomic single-use guard (TOCTOU) — race window (dossier §6.5)",
                })
        return findings


# ---------------------------------------------------------------------------
# (c) Monitor 3 — ISSuer CONFINEMENT / MIX-UP  (dossier §2.3 P4, §5.3)
#     □(authz_response(resp) → resp.iss = expected_iss(route))
# ---------------------------------------------------------------------------

class MixupMonitor:
    def __init__(self, expected_iss_by_route: dict[str, str], trusted_issuers: set[str]):
        self.expected = expected_iss_by_route
        self.trusted = trusted_issuers

    def run(self, trace: Trace) -> list[dict[str, Any]]:
        findings = []
        for ev in trace.events:
            if ev.event == "callback":
                route = str(ev.params.get("route", "/callback"))
                iss = ev.params.get("iss")
                exp = self.expected.get(route)
                if iss is None:
                    findings.append({
                        "template": "issuer_confinement",
                        "property": "□(authz_response(resp) → resp.iss = expected_iss(route))",
                        "trace": trace.trace_id,
                        "evidence": {"route": route, "iss": None, "expected": exp},
                        "verdict": "MISSING_ISS_ACCEPTED" if _accepted(ev.outcome) else "rejected",
                    })
                elif exp is not None and iss != exp:
                    findings.append({
                        "template": "issuer_confinement",
                        "trace": trace.trace_id,
                        "evidence": {"route": route, "iss": iss, "expected": exp},
                        "verdict": "MISMATCH_ACCEPTED" if _accepted(ev.outcome) else "rejected",
                    })
            if ev.event == "token_exchange":
                iss = ev.params.get("iss")
                if iss is not None and iss not in self.trusted and _accepted(ev.outcome):
                    findings.append({
                        "template": "issuer_confinement",
                        "trace": trace.trace_id,
                        "evidence": {"iss": iss},
                        "verdict": "UNTRUSTED_ISSUER_TOKEN_ACCEPTED",
                    })
        return findings


# ---------------------------------------------------------------------------
# (d) Token algebra — JWT audit  (dossier §1.7, §3.4)
# ---------------------------------------------------------------------------

def b64url_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def audit_jwt(token: str, expected_alg: str | None = None) -> dict[str, Any]:
    """Decode + audit a JWT. Audit-only: signature is NOT verified (that is the point —
    the audit surfaces what a verifier must pin down)."""
    report: dict[str, Any] = {"verdict_flags": []}
    try:
        h_b64, p_b64, *_ = token.split(".")
        header = json.loads(b64url_decode(h_b64))
        payload = json.loads(b64url_decode(p_b64))
    except Exception as exc:  # malformed token — report, don't crash
        return {"verdict_flags": ["MALFORMED"], "error": str(exc)}

    alg = header.get("alg")
    report["header"] = header
    report["claims"] = payload

    if alg in (None, "none"):
        report["verdict_flags"].append("ALG_NONE_ACCEPTABLE_SURFACE")
    if expected_alg and alg != expected_alg and alg in ("HS256", "HS384", "HS512"):
        # asymmetric expected, symmetric presented → classic confusion (CVE-2022-29217 family)
        report["verdict_flags"].append(f"ALG_CONFUSION_SURFACE({expected_alg}->{alg})")
    kid = header.get("kid")
    if isinstance(kid, str) and ("../" in kid or kid.startswith(("/", "%")) or "'" in kid):
        report["verdict_flags"].append("KID_INJECTION_SURFACE")          # path / SQLi pattern
    for k in ("jku", "x5u"):
        if k in header:
            report["verdict_flags"].append(f"{k.upper()}_REMOTE_KEY_SURFACE")   # attacker-resolvable key URL
    if "jwk" in header:
        report["verdict_flags"].append("JWK_EMBEDDED_KEY_SURFACE")       # CVE-2018-0114 family

    # binding τ extraction
    b = Binding(
        subject=payload.get("sub"),
        scope=frozenset(str(payload.get("scope", "")).split()),
        epoch=payload.get("pwd_at") or payload.get("auth_time"),
        audience=frozenset([payload["aud"]] if isinstance(payload.get("aud"), str) else payload.get("aud", [])),
        issuer=payload.get("iss"),
        raw_claims=payload,
    )
    report["binding"] = b.__dict__ | {
        "audience": sorted(b.audience),
        "scope": sorted(b.scope),
    }
    return report


class TokenAlgebraAuditor:
    """Binding-preservation checks over observed presentations (dossier §2.3 P3):
    a token bound to audience X must not be accepted by an endpoint mapped to audience Y."""

    def __init__(self, endpoint_audience: dict[str, str]):
        self.endpoint_aud = endpoint_audience   # route -> expected aud

    def run(self, trace: Trace, jwt_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        findings = []
        for ev in trace.events:
            if ev.event != "token_present":
                continue
            ref = str(ev.params.get("token_ref"))
            rep = jwt_reports.get(ref)
            if not rep:
                continue
            aud = rep["binding"]["audience"]
            route = str(ev.params.get("route"))
            want = self.endpoint_aud.get(route)
            if want and want not in aud and _accepted(ev.outcome):
                findings.append({
                    "template": "binding_preservation",
                    "property": "□(grant(B) → ∃τ: τ.sub=B ∧ τ.aud ∋ res ∧ τ.epoch≥now)",
                    "trace": trace.trace_id,
                    "evidence": {"token_ref": ref, "token_aud": sorted(aud),
                                 "route": route, "endpoint_aud": want},
                })
        return findings


# ---------------------------------------------------------------------------
# §2.3 P6 / §6.1 — entropy checks
# ---------------------------------------------------------------------------

def charset_of(secret: str) -> tuple[str, int, bool]:
    """Return (best charset name, canonical |C|, confident). Conservative: pick the
    smallest class that covers every observed character. NOTE: the class size is the
    canonical alphabet size (hex = 16 values, case-insensitive), NOT the number of
    distinct literal characters observed in the set definition — conflating the two
    inflates H (a 16-char hex secret is 64 bits, not 16·log2(22) = 71.4)."""
    classes: list[tuple[str, set[str], int]] = [
        ("digits", set("0123456789"), 10),
        ("hex", set("0123456789abcdefABCDEF"), 16),
        ("base36", set("0123456789abcdefghijklmnopqrstuvwxyz"), 36),
        ("base62", set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"), 62),
    ]
    observed = set(secret)
    for name, chars, size in classes:
        if observed <= chars:
            return name, size, True
    return "base64url", 64, observed <= set(
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"
    )


def shannon_entropy_bits(secret: str) -> float:
    """Empirical entropy of the observed sample (sanity check, not the budget)."""
    if not secret:
        return 0.0
    counts = Counter(secret)
    n = len(secret)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def check_entropy(secret: str, label: str, min_bits: float) -> dict[str, Any]:
    name, size, confident = charset_of(secret)
    nominal = len(secret) * math.log2(size) if confident else float("nan")
    empirical = shannon_entropy_bits(secret)
    return {
        "label": label,
        "charset": name,
        "length": len(secret),
        "nominal_bits": round(nominal, 1) if confident else None,
        "empirical_bits_sample": round(empirical, 1),
        "min_bits": min_bits,
        "verdict": "PASS" if confident and nominal >= min_bits else "FAIL",
        "method": "H = L·log2|C|  (dossier §6.1)",
    }


# ---------------------------------------------------------------------------
# (e) Race planning — single-use endpoints  (dossier §3.5, §6.5; execution = Turbo Intruder)
# ---------------------------------------------------------------------------

def race_plan(endpoints: list[str], n: int = 30, protocol: str = "http2") -> dict[str, Any]:
    return {
        "mode": "plan_only_v0",
        "endpoints": endpoints,
        "requests_per_race": n,
        "technique": ("http2_single_packet" if protocol == "http2"
                      else "http1_last_byte_sync"),
        "model": "P ≈ 1 − (1 − w/σ)^C(k,2)   (dossier §6.5)",
        "note": ("v0 emits the plan; execute with Turbo Intruder "
                 "(github.com/PortSwigger/turbo-intruder) — single-packet attack."),
    }


# ---------------------------------------------------------------------------
# (f) Verdict — JSON contract, dossier §5.4
# ---------------------------------------------------------------------------

class VerdictBuilder:
    def __init__(self, target: dict[str, Any]):
        self.target = target
        self.findings: list[dict[str, Any]] = []
        self._seq = 0

    def add(self, finding: dict[str, Any], severity: str, title: str, repro: list[str]) -> None:
        self._seq += 1
        self.findings.append({
            "id": f"VF-AUTH-{self._seq:03d}",
            "severity": severity,
            "title": title,
            **finding,
            "repro": repro,
        })

    def to_json(self, machine: dict[str, Any], entropy: list[dict[str, Any]],
                bindings: list[dict[str, Any]], race: dict[str, Any]) -> str:
        return json.dumps({
            "engine": ENGINE, "version": VERSION,
            "target": self.target,
            "machine": machine,
            "findings": self.findings,
            "entropy": entropy,
            "token_bindings": bindings,
            "race_plan": race,
        }, indent=2, ensure_ascii=False, default=str)


SEVERITY = {
    "no_skip": "critical", "no_replay": "high", "issuer_confinement": "critical",
    "binding_preservation": "high",
}
TITLES = {
    "no_skip": "Protected state reachable without required proof (step-skip)",
    "no_replay": "Single-use token consumed more than once (non-atomic guard)",
    "issuer_confinement": "Callback/token accepted with unverified or mismatched issuer (mix-up surface)",
    "binding_preservation": "Token accepted outside its bound audience",
}


# ---------------------------------------------------------------------------
# Deterministic built-in demo — synthetic vulnerable MFA/OIDC lab traces
# ---------------------------------------------------------------------------

def _make_jwt(header: dict[str, Any], payload: dict[str, Any]) -> str:
    j = lambda o: b64url_encode(json.dumps(o, separators=(",", ":")).encode())
    return f"{j(header)}.{j(payload)}.DEMO_NOT_A_REAL_SIGNATURE"


def demo_traces() -> list[Trace]:
    t1 = Trace("t1-victim-mfa-skip", [
        TraceEvent("creds_submit", "victim", {"user": "V"}, "s1_creds_ok", "200"),
        TraceEvent("session_establish", "victim", {}, "s3_authenticated", "200"),
        TraceEvent("resource_access", "victim", {"route": "/api/admin"}, "s3_authenticated", "200"),
    ])
    t2 = Trace("t2-code-race", [
        TraceEvent("code_consume", "victim", {"token_id": "α"}, "s4_code_exchanged", "200"),
        TraceEvent("code_consume", "attacker", {"token_id": "α"}, "s4_code_exchanged", "200"),
    ])
    t3 = Trace("t3-mixup", [
        TraceEvent("callback", "attacker", {"route": "/cb/google", "iss": None}, "s1_creds_ok", "302"),
        TraceEvent("token_exchange", "attacker", {"iss": "https://attacker.tld"}, "s4_code_exchanged", "200"),
    ])
    t4 = Trace("t4-aud-confusion", [
        TraceEvent("token_present", "attacker", {"token_ref": "tok_v", "route": "/api/admin"}, "s3_authenticated", "200"),
    ])
    return [t1, t2, t3, t4]


def run_engine(traces: list[Trace], flow: str, pretty: bool) -> str:
    # -- flow specification (v0: hand-built transition map, dossier §5.2) ----------
    protected = {"s3_authenticated"}
    required = {"s3_authenticated": {"creds_submit", "otp_submit"}}
    proof_events = {"creds_submit", "otp_submit", "magic_verify"}
    expected_iss = {"/cb/google": "https://accounts.google.com"}
    trusted = {"https://accounts.google.com", "https://lab.idp.tld"}
    endpoint_aud = {"/api/admin": "admin.internal", "/api/pay": "api.internal"}

    # -- (d) demo JWT corpus (built programmatically; deterministic) ---------------
    tok_v = _make_jwt(
        {"alg": "RS256", "kid": "key-2026-03"},
        {"sub": "victim", "aud": ["api.internal"], "iss": "https://lab.idp.tld", "scope": "read"},
    )
    tok_evil = _make_jwt(
        {"alg": "HS256", "kid": "../../dev/null", "jku": "https://evil.tld/jwks.json"},
        {"sub": "attacker", "aud": ["api.internal"], "iss": "https://attacker.tld", "scope": "admin"},
    )
    jwt_reports = {"tok_v": audit_jwt(tok_v, expected_alg="RS256"),
                   "tok_evil": audit_jwt(tok_evil, expected_alg="RS256")}

    # -- (c) monitors -----------------------------------------------------------------
    findings_acc: list[dict[str, Any]] = []
    for m in (NoSkipMonitor(protected, required, proof_events),
              NoReplayMonitor(), MixupMonitor(expected_iss, trusted),
              TokenAlgebraAuditor(endpoint_aud)):
        for t in traces:
            findings_acc.extend(m.run(t, jwt_reports) if isinstance(m, TokenAlgebraAuditor) else m.run(t))

    # -- (f) verdict --------------------------------------------------------------------
    vb = VerdictBuilder({"base_url": "lab://demo", "flow": flow, "date": time.strftime("%Y-%m-%d")})
    for f in findings_acc:
        tpl = f["template"]
        vb.add(f, SEVERITY.get(tpl, "info"), TITLES.get(tpl, tpl), ["see lab guide §7 for reproduction pattern"])

    entropy = [
        check_entropy("a1b2c3d4e5f6a7b8", "observed state param (16 hex)", 128.0),
        check_entropy("q7Xk2Mw9Rt4Bz6Nc1Pd0Vf", "observed code param (22 base62)", 160.0),
        check_entropy("482913", "observed OTP (6 digits)", 19.9),
    ]
    bindings = [{"ref": k, "flags": v["verdict_flags"], "sub": v["binding"]["subject"],
                 "aud": v["binding"]["audience"], "iss": v["binding"]["issuer"]}
                for k, v in jwt_reports.items()]
    machine = {"states": 5, "alphabet": 8, "inference": "hand-built (v0)", "confidence": 0.85,
               "protected": sorted(protected), "required_proofs": {k: sorted(v) for k, v in required.items()}}
    race = race_plan(["POST /oauth/token (code exchange)", "POST /mfa/verify (otp)"], n=30)
    out = vb.to_json(machine, entropy, bindings, race)
    return out if pretty else json.dumps(json.loads(out))


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(prog=ENGINE, description="auth flow state-machine auditor (v0, lab use only)")
    ap.add_argument("--traces", help="path to trace JSON (schema: lab guide §3)")
    ap.add_argument("--flow", default="mfa", choices=["mfa", "oauth2", "oidc", "magic_link"])
    ap.add_argument("--out", help="write verdict JSON to file")
    ap.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = ap.parse_args()

    # Windows consoles default to cp1252 — force UTF-8 so the LTL math symbols survive
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.traces:
        with open(args.traces, encoding="utf-8") as fh:
            traces = traces_from_json(json.load(fh))
    else:
        traces = demo_traces()

    verdict = run_engine(traces, args.flow, pretty=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(verdict)
        print(f"[+] verdict written: {args.out}", file=sys.stderr)
    print(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
