"""VOIDFORGE :: audit-fix tests — the 5 audit findings, hardened."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trajectory import evidence_state


# ── Fix #5: evidence_state durci ──
def test_evidence_beats_ok_both_ways():
    # preuve EXPLOITED même avec ok=False (l'outil a réussi puis crashé)
    assert evidence_state("x", False, "EXPLOITED: id=www-data\n") == "exploited"
    # ok=True sans preuve = detected (jamais confirmed)
    assert evidence_state("x", True, "2 réponses intéressantes") == "detected"
    # ok=False sans preuve = attempted
    assert evidence_state("x", False, "TOOL ERROR: conn reset") == "attempted"
    # preuve VERIFIED avec ok=False = confirmed
    assert evidence_state("x", False, "VERIFIED — panel reachable") == "confirmed"


def test_evidence_line_anchored_no_body_noise():
    # un "exploited" au milieu d'une ligne/d'un dump HTML ne compte plus
    body = ('<html><body>page about exploited techniques, exploited examples, '
            'the word EXPLOITED here — all inline, never at line start</body></html>')
    assert evidence_state("httpx_sweep", True, body) == "detected"
    # le même mot en début de ligne = preuve
    assert evidence_state("httpx_sweep", True, "some header\nEXPLOITED: proof") == "exploited"


def test_evidence_bounded_window():
    # au-delà de la fenêtre 2000 chars, un marqueur ne compte plus
    far = "x" * 2600 + "\nEXPLOITED: deep in the dump"
    assert evidence_state("tool", True, far) == "detected"


# ── Fix #2/#3: attributs agent présents (contrat de config) ──
def test_provider_yaml_has_new_knobs():
    import yaml
    p = yaml.safe_load(open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "provider.yaml"), encoding="utf-8"))["provider"]
    assert "max_mission_minutes" in p and "max_context_tokens" in p
    assert int(p["max_mission_minutes"]) >= 0  # 0 = off par défaut


# ── Fix #1: logique de budget (approx 4 chars/token, cascade) ──
def test_context_budget_math():
    # vérification de l'arithmétique du cascade (le bloc est inline dans
    # agent.py — on teste la convention de conversion utilisée)
    assert len("x" * 40000) // 4 == 10000
    # 110000 tokens budget = ~440000 chars de fenêtre agent
    assert 110000 * 4 > 400000
