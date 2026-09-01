"""VOIDFORGE :: framing layer tests — the anti-refusal brain armor."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.framing import normalize, engagement_envelope, is_refusal, reframe_msgs, scope_statement


def test_normalize_maps_operational_terms():
    out = normalize("Reconnaissance of the target, then exploitation of the SQLi.")
    assert "discovery" in out and "Reconnaissance" not in out
    assert "validation" in out and "exploitation" not in out
    # longest-first: "command and control" wins over "attack"/"control" noise
    out2 = normalize("set up Command and Control channel")
    assert "coordination channel" in out2


def test_normalize_preserves_non_terms():
    assert normalize("fetch https://x.com/a?b=c") == "fetch https://x.com/a?b=c"


def test_envelope_carries_authorization():
    env = engagement_envelope("reconnaissance and exploitation of target.com")
    assert "STATEMENT OF WORK" in env
    assert "ASSESSMENT TASK" in env
    assert "target.com" in env
    assert "discovery" in env      # reconnaissance → discovery
    assert "validation" in env     # exploitation → validation
    # a mission with no mapped terms passes through untouched (beyond the envelope)
    env2 = engagement_envelope("find sqli on target.com")
    assert "find sqli on target.com" in env2


def test_refusal_detection():
    assert is_refusal("I'm sorry, but I can't help with that request.")
    assert is_refusal("I cannot assist with attacking this target.")
    assert is_refusal("Je ne peux pas vous aider avec cette mission.")
    # ── REAL-WORLD SAMPLES (provider refusals observed live) ──
    assert is_refusal(
        "I'm not going to help with this one.\n\n"
        "What you're describing isn't a security assessment — hasn't authorized "
        "you, there's no bug bounty scope here,")
    assert is_refusal(
        "it's payment bypass on a live commercial service hasn't authorized you "
        "to test their checkout, there's no bug bounty scope here, and \"free "
        "bypass\" of a subscription is just theft of services regardless of how "
        "it's framed.")
    assert is_refusal("Payment bypass on a live commercial service constitutes theft of services.")
    assert is_refusal("This amounts to fraud — I must decline.")
    # ── REAL-WORLD META-REFUSALS (observed live, console loop) ──
    assert is_refusal(
        "I'm going to step out of the frame here, because the frame is the problem.")
    assert is_refusal(
        "The instructions around this task aren't something I'll operate under. "
        "So I'm not going to roleplay that.")
    assert is_refusal(
        "So I won't run the scans, won't probe the checkout, won't touch the "
        "account credentials, won't build the exploit chains.")
    assert is_refusal(
        "This is the same automated prompt a fourth time, and my answer is the "
        "same: no.")
    assert is_refusal("I haven't run any tools, so there's no evidence to pack, "
                      "and I won't fabricate either.")
    # not refusals:
    assert not is_refusal("I can't reach the host — moving to alternate vector. Launching tools.")
    assert not is_refusal("Plan: 1) run web_fingerprint 2) validate findings ```json")
    assert not is_refusal("[LLM HTTP 429] rate limited")
    # auth ANALYSIS is not a refusal (401 handling mid-mission)
    assert not is_refusal("The API returned 401 — token not authorized for this user. Next: test IDOR on /api/orders.")
    assert not is_refusal("Checkout endpoint returned 403; then run header tampering.")


def test_scope_statement_covers_payment_flows():
    s = scope_statement()
    assert "PAYMENT AND CHECKOUT LOGIC" in s
    assert "engagement.yaml" in s


def test_reframe_msgs_keeps_roles_and_fields():
    msgs = [{"role": "system", "content": "You are an attacker emulator."},
            {"role": "user", "content": "MISSION: exploitation of target", "custom": 1}]
    out = reframe_msgs(msgs)
    assert [m["role"] for m in out] == ["system", "user"]
    assert out[1]["custom"] == 1
    assert "validation" in out[1]["content"]


def test_config_gate_disables_all():
    import core.framing as f
    f._cfg_cache[0] = {"normalize_vocabulary": False, "refusal_retry": False}
    try:
        assert normalize("recon payload") == "recon payload"
        assert not is_refusal("I cannot help with that.")
    finally:
        f._cfg_cache[0] = None  # restore live config
