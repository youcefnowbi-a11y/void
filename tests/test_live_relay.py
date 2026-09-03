# -*- coding: utf-8 -*-
"""Guard tests — Tier B live-graph relay."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
from core.agent import Agent


class _FakeBoard:
    def __init__(self, intel, n_assets=3):
        self._intel = intel
        self.assets = {i: {} for i in range(n_assets)}

    def to_prompt(self, limit=40):
        return self._intel


class _EmptyBoard:
    assets = {}

    def to_prompt(self, limit=40):
        return ""


def test_live_update_carries_round_and_top_intel():
    b = _FakeBoard("dom venice.ai conf 0.99 | endpoint /api/x conf 0.9")
    txt = Agent._live_update_text(b, 6)
    assert "round 6" in txt and "venice.ai" in txt
    assert "never re-test ground" in txt


def test_live_update_empty_graph_is_empty():
    assert Agent._live_update_text(_EmptyBoard(), 3) == ""


def test_live_update_capped():
    b = _FakeBoard("x" * 5000)
    txt = Agent._live_update_text(b, 9, cap=500)
    assert len(txt) < 800
