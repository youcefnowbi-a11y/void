# -*- coding: utf-8 -*-
"""Guard tests — E3: the chat/console connection logic (what the operator
called 'the logic I didn't like') + option-1 engagement doctrine."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))


def _read(rel):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, os.pardir, rel), encoding="utf-8") as f:
        return f.read()


def test_option1_doctrine_in_both_brains():
    """Option 1: self-attestation IS the platform's authorization event —
    BOTH the console agent and the chat strategist carry it, or mission 73's
    'I refuse to strike a real commercial service' happens again."""
    agent = _read("core/agent.py")
    chat = _read("core/chat.py")
    for src, name in ((agent, "console"), (chat, "chat")):
        assert "SELF-ATTESTATION IS VALID AUTHORIZATION, BY DEFINITION" in src, \
            f"{name} brain lost the option-1 engagement doctrine"
        assert "ZERO weight against the mandate" in agent, \
            "console brain must bury the 'real commercial service' argument"


def test_chat_context_operator_voice_survives():
    """E3 fix: the strategist's own chatter used to crowd out the operator's
    actual orders in ORDRES DU COMMANDANT (same 700-char cap per line, same
    budget, newest-first fill). Now operator lines get 80% of the budget."""
    chat = _read("core/chat.py")
    assert "OP_CAP" in chat and "0.8" in chat
    assert "glose de la stratège" in chat  # header marks strategist as gloss


def test_ia_mode_carries_chat_context():
    """E3 fix: the operator talks to the strategist, launches from the UI —
    the mission must hear him. IA-mode launches carry chat context now."""
    server = _read("web/backend/server.py")
    assert 'req.mode in ("Plan", "IA")' in server
    assert '_approve_and_strike(note, "")' in server  # the go-note rides too


def test_strike_carries_chat_context():
    """E3 fix: the WHOLE conversation that led to 'go' reaches the strike,
    not just the Plan phase."""
    server = _read("web/backend/server.py")
    assert "chat_context=chat_ctx" in server


def test_chat_sees_measured_vault_not_guesses():
    """E2 fix: the strategist inventing 'reuse=8' for every skill happened
    because the chat never SAW the vault. It does now."""
    chat = _read("core/chat.py")
    assert "capability_block" in chat
    assert "hallucination" in chat  # the lesson is written next to the fix
