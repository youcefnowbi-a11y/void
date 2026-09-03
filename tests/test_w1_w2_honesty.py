"""VOIDFORGE :: W1 + W2 — finding quality + honest ledger (mission-76 lessons).

W1: the engagement report's FINDINGS section claimed 25 HIGH findings that
    were 25 raw JWT blobs — six were her own alg=none forgeries living
    inside jwt_forge_replay output, the rest self-minted session tokens,
    while the agent's own verdict count said ZERO. Guards: provenance
    (our munition is not a discovery), nature (captured JWT without an
    admin marker = evidence MEDIUM, rule 8), identity dedup (re-minted
    same-identity tokens collapse to one finding).
W2: the ledger called failures successes — auth_state_audit's
    'exit=2 [stderr] /health failed' and forged_siwx_signer's
    {'ok': false, 'errors': [No module named 'eth_account']} both
    ledgered [ok]. Guard: honest_status classifies both as error while
    honest negatives (exploitable:false) stay ok.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── W1: provenance / nature / identity-dedup ────────────────────────

def _fake_jwt(iss="https://clerk.venice.ai", sub="user_1", jti="a"):
    import base64
    def b64(d):
        # compact separators + a real-shaped header (kid) — the severity
        # regex demands eyJ+20 chars; short fixtures match nothing (vacuous)
        return base64.urlsafe_b64encode(
            json.dumps(d, separators=(",", ":")).encode()).decode().rstrip("=")
    head = {"alg": "RS256", "kid": "ins_2dubRvCKqi5XrOUxIWgUN4fomDF",
            "typ": "JWT"}
    return f"{b64(head)}.{b64({'iss': iss, 'sub': sub, 'jti': jti})}.sig"


def test_own_munition_is_not_a_finding():
    from core.report import _extract_findings
    forged = _fake_jwt(sub="victim_2")
    t = [("tool", f"jwt_forge_replay: {{'variants': [{{'alg': 'none'}}, "
                  f"{{'alg': 'none'}}], 'jwt': '{forged}'}}")]
    findings, _ = _extract_findings(t)
    assert findings == [], f"own munition leaked into findings: {findings}"


def test_forged_tools_and_crypto_hash_are_artifacts_too():
    from core.report import _SELF_ARTIFACT_TOOLS, _extract_findings
    assert {"jwt_forge_replay", "crypto_hash", "session_keep"} <= _SELF_ARTIFACT_TOOLS
    t = [("tool", f"forged_siwx_idor_v7: {{'token': '{_fake_jwt()}'}}"),
         ("tool", "crypto_hash: jwt_decode output " + _fake_jwt(sub="u9"))]
    findings, _ = _extract_findings(t)
    assert findings == []


def test_target_key_material_in_our_tools_still_counts():
    # if OUR tool output carries the TARGET's live key, the target leaked it
    from core.report import _extract_findings
    t = [("tool", "jwt_forge_replay: replayed against "
                 "postgres://user:pw@db.target.internal:5432/prod")]
    findings, _ = _extract_findings(t)
    assert findings and findings[0]["severity"] == "CRITICAL"


def test_captured_jwt_is_medium_without_admin_marker():
    from core.report import _extract_findings
    t = [("tool", f"data_extract: {{'session': {{'token': '{_fake_jwt()}'}}}}")]
    findings, _ = _extract_findings(t)
    assert len(findings) == 1
    assert findings[0]["severity"] == "MEDIUM", \
        "rule 8: credential in transit without demonstrated end-state is not HIGH"


def test_captured_jwt_is_high_with_admin_marker():
    from core.report import _extract_findings
    # 'internal' sits in the admin marker set WITHOUT tripping the harder
    # service_role CRITICAL rule — this isolates the W1-2 nature gate
    t = [("tool", f"data_extract: {{'note': 'internal', 'token': '{_fake_jwt()}'}}")]
    findings, _ = _extract_findings(t)
    assert findings and findings[0]["severity"] == "HIGH"


def test_service_role_stays_critical():
    from core.report import _extract_findings
    t = [("tool", f"data_extract: {{'service_role': '{_fake_jwt()}'}}")]
    findings, _ = _extract_findings(t)
    assert findings and findings[0]["severity"] == "CRITICAL"


def test_same_identity_remints_collapse_to_one():
    from core.report import _extract_findings
    t = [("tool", f"data_extract: m1 {{'token': '{_fake_jwt(jti='1')}'}}"),
         ("tool", f"data_extract: m2 {{'token': '{_fake_jwt(jti='2')}'}}"),
         ("tool", f"data_extract: m3 {{'token': '{_fake_jwt(jti='3')}'}}")]
    findings, _ = _extract_findings(t)
    assert len(findings) == 1, \
        f"3 re-mints of the same (iss,sub,aud) are ONE finding, got {len(findings)}"


def test_distinct_identities_both_reported():
    from core.report import _extract_findings
    t = [("tool", f"data_extract: {{'token': '{_fake_jwt(sub='user_a')}'}}"),
         ("tool", f"data_extract: {{'token': '{_fake_jwt(sub='user_b')}'}}")]
    findings, _ = _extract_findings(t)
    assert len(findings) == 2


def test_jwt_identity_decode_and_fallback():
    from core.report import _jwt_identity
    a = _jwt_identity(_fake_jwt())
    assert a.startswith("https://clerk")
    # undecodable garbage falls back to a stable blob prefix
    assert _jwt_identity("garbage.notb64atall!!").startswith("garbage.")


# ── W2: honest ledger status ───────────────────────────────────────

def test_honest_status_catches_wrapped_subprocess_death():
    from core.coverage import honest_status
    bad = "[stderr] [!] target /health failed — is the lab running? " \
          "python research/lab_oauth [exit=2]"
    assert honest_status(bad) == "error"


def test_honest_status_catches_ok_false():
    from core.coverage import honest_status
    bad = json.dumps({"ok": False,
                      "errors": ["eth_account: No module named 'eth_account'",
                                 "coincurve: No module named 'coincurve'"]})
    assert honest_status(bad) == "error"


def test_honest_status_keeps_honest_negatives_ok():
    from core.coverage import honest_status
    neg = json.dumps({"exploitable": False,
                      "summary": "0 pattern hits across 2 rounds"})
    assert honest_status(neg) == "ok"
    assert honest_status('{"status": 200, "size": 55637}') == "ok"
    assert honest_status("TOOL ERROR [TypeError]: boom") == "error"


def test_agent_wiring_uses_honest_status():
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "agent.py"),
               encoding="utf-8").read()
    assert src.count("_cov.honest_status(") >= 3  # tap + offline brain + outer loop
