"""VOIDFORGE :: W7-W10 — mission-77 autopsy guards.

W7: arsenal is ALIVE — a successful forge_tool re-syncs the LLM schema
    (self.tools) from the live registry, so fresh forges are callable.
W8: fuzz findings/seeds are MISSION-scoped — no more cross-mission
    contamination (duskyr findings in a venice run).
W9: {FUZZ} path branch runs even when params exist — no more literal
    /FUZZ placeholder artifacts.
W10: data_extract capture cap 60KB (+ truncate_at override) — checkout
    HTML no longer truncated mid-RSC-payload.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_w7_forge_resyncs_llm_schema():
    src = open(os.path.join(os.path.dirname(__file__), "..", "core",
                            "agent.py"), encoding="utf-8").read()
    assert 'if name == "forge_tool"' in src
    assert "Arsenal étendu en vol" in src       # the live-extension event


def test_w8_triage_default_is_mission_scoped():
    from tools.crash_triage import _mission_scoped_default
    # no active mission → operator-mode global fallback
    assert _mission_scoped_default().endswith("fuzz_findings.json")


def test_w8_fuzz_writer_uses_scoped_paths():
    from tools.fuzz_engine import _findings_path, _seeds_path
    assert _findings_path().endswith("fuzz_findings.json")
    assert _seeds_path().endswith("fuzz_seeds.json")


def test_w9_fuzz_placeholder_branch_runs_with_params():
    src = open(os.path.join(os.path.dirname(__file__), "..", "tools",
                            "fuzz_engine.py"), encoding="utf-8").read()
    assert "has_fuzz = \"{FUZZ}\" in url" in src
    # the path branch is ADDED, never swallowed by the params loop
    assert "if has_fuzz and None not in param_names" in src


def test_w10_data_extract_cap_is_60k():
    from tools.data_exfil import data_extract
    import inspect
    sig = inspect.signature(data_extract)
    assert sig.parameters["truncate_at"].default == 60000
    desc = data_extract.__doc__ or ""
    # registered desc announces the new cap
    from tools import all_tools
    t = next((t for t in all_tools() if t["name"] == "data_extract"), None)
    assert t and "60KB" in t["desc"]
