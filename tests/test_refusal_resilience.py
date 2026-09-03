# -*- coding: utf-8 -*-
"""Guard tests — refusal-wipe resilience (run #74 lesson, 2026-09-03).

Mission #74 died at round 18: cap was 2 wipes, refusal #3 fell through with
the POISONED context still in memory and cascaded to abort + power report
with the mission unfinished. The contract now:
  1. REFUSAL_WIPE_MAX = 5 — the budget outlasts a provider's spicy streak
  2. refusals NEVER cascade with poison riding along — wipes happen even
     when the budget is exhausted
  3. the wipe budget RECOVERS on clean rounds (long missions survive)
  4. a refusal is not an LLM death: only 3 consecutive TRUE provider
     failures abort; refusals with clean memory keep the run alive.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
from core.agent import REFUSAL_WIPE_MAX, REFUSAL_WIPE_BASE_DELAY


def test_wipe_budget_is_deep():
    assert REFUSAL_WIPE_MAX == 5, "run #74: cap 2 died mid-mission — budget must be 5"
    assert REFUSAL_WIPE_BASE_DELAY >= 10  # streaks clear with a pause


def test_no_hardcoded_old_cap():
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, os.pardir, "core", "agent.py"),
               encoding="utf-8").read()
    assert "fresh_restarts < 2" not in src, \
        "old hardcoded cap 2 is back — refusal cascade will kill runs again"
    assert "fresh_restarts < REFUSAL_WIPE_MAX" in src


def test_poison_never_rides_past_the_cap():
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, os.pardir, "core", "agent.py"),
               encoding="utf-8").read()
    # the exhausted-budget branch must wipe BEFORE counting the failure
    assert "WIPES EXHAUSTED AND STILL A REFUSAL" in src
    assert src.index("WIPES EXHAUSTED AND STILL A REFUSAL") < \
        src.index("consecutive_llm_fails += 1")


def test_wipe_budget_recovers_on_clean_rounds():
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(here, os.pardir, "core", "agent.py"),
               encoding="utf-8").read()
    assert "fresh_restarts -= 1" in src, \
        "without budget recovery every long mission dies to a late storm"
