# -*- coding: utf-8 -*-
"""Guard tests — Tier C: burnable operational identity."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
from core.op_identity import identity_for, burn, summary, _IDENTITY
from tools import _transport as T


def _reset():
    _IDENTITY.clear()
    T._HOST_FAILS.clear()


def test_identity_deterministic_and_stable():
    _reset()
    a = identity_for("target.example")
    b = identity_for("target.example")
    assert a == b and a["ua"] and a["lang"]


def test_burn_renews_accent():
    _reset()
    old = identity_for("burn.example")
    info = burn("burn.example", "captcha wall hcaptcha")
    assert info["gen"] == 1
    stale = identity_for("burn.example")            # sans renew → encore grillée
    assert stale["burned"] is True and stale["ua"] == old["ua"]
    fresh = identity_for("burn.example", renew=True)  # le transport renouvelle
    assert fresh["burned"] is False and fresh["gen"] == 1
    assert fresh["ua"] != old["ua"] or fresh["lang"] != old["lang"]


def test_four_strikes_burn_identity():
    _reset()
    for _ in range(3):
        T._mark_host_result("flood.example", 403)
    assert identity_for("flood.example")["burned"] is False
    T._mark_host_result("flood.example", 403)        # 4e refus consécutif
    assert identity_for("flood.example")["burned"] is True


def test_success_resets_strike_counter():
    _reset()
    for _ in range(3):
        T._mark_host_result("ok.example", 403)
    T._mark_host_result("ok.example", 200)           # succès → compteur à zéro
    T._mark_host_result("ok.example", 403)
    T._mark_host_result("ok.example", 403)
    assert identity_for("ok.example")["burned"] is False


def test_summary_shape():
    _reset()
    identity_for("live.example")
    burn("live.example", "test")
    s = summary()
    assert "live.example" in s["burned"] and s["live"] == []
