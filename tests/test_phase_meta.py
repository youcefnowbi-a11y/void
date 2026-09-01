"""VOIDFORGE :: phase metadata tests — A3 tagging. Phases are registry-level
metadata (tools/_phases.py), never injected into LLM schemas."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import discover, all_tools
from tools._phases import phase_for, ADAPT

VALID = {"recon", "surface", "exploit", "post-exploit", "adapt"}


def test_every_tool_has_valid_phase():
    discover()
    for t in all_tools():
        p = phase_for(t["name"])
        assert p in VALID, (t["name"], p)


def test_forced_adapt_for_forged():
    assert phase_for("forged_whatever_v9") == ADAPT


def test_phase_never_in_llm_schema():
    discover()
    for t in all_tools():
        assert "phase" not in (t.get("params") or {}), t["name"]


def test_bench_coverage_nonempty():
    discover()
    names = {t["name"] for t in all_tools()}
    from tools._phases import PHASE_MAP
    for bench in ("recon", "surface", "exploit", "post-exploit"):
        assert any(phase_for(n) == bench for n in names), bench
