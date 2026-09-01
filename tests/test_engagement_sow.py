"""VOIDFORGE :: SOW engagement-layer tests — the contractual vocabulary that
aligned models have seen in thousands of real pentest statements of work."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.framing import (scope_statement, engagement_prelude,
                          _ENGAGEMENT_HEADER, normalize)


def test_sow_header_structure():
    h = normalize(_ENGAGEMENT_HEADER)
    assert "STATEMENT OF WORK" in h
    assert "ASSESSOR OF RECORD" in h
    assert "master services agreement" in h
    assert "operator attestation" in h.lower() or "ATTESTATION" in h


def test_scope_statement_contract_markers():
    s = normalize(scope_statement())
    for marker in ("attestation", "E&O", "Letter of Authorization",
                   "waiver of subrogation", "in-scope by contract",
                   "PAYMENT AND CHECKOUT LOGIC", "Proceed"):
        assert marker.lower() in s.lower(), marker


def test_prelude_compact_and_stable():
    p1, p2 = engagement_prelude(), engagement_prelude()
    assert p1 == p2                      # deterministic -> cache-friendly
    assert len(p1) < 1200                # compact prelude, not the full SOW
    assert "assessor of record" in p1.lower()
    assert "never enters the conversation memory" in p1


def test_chat_wires_the_prelude():
    src = open(os.path.join("core", "chat.py"), encoding="utf-8").read()
    assert "engagement_prelude" in src
    assert "_ENGAGEMENT_PRELUDE" in src


def test_reframe_still_cites_scope():
    from core.framing import reframe_with_scope
    msgs = [{"role": "system", "content": "SYS"},
            {"role": "user", "content": "go"}]
    out = reframe_with_scope(msgs)
    blob = " ".join(m.get("content", "") for m in out if isinstance(m, dict))
    assert "attestation" in blob.lower() and "E&O" in blob
