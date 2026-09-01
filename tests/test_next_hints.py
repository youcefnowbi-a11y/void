"""VOIDFORGE :: chain hints tests — every hinted tool/consumer exists, hints
append at runtime, errors and no-hint tools stay clean."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools._hints import NEXT_HINTS, hint_for, _NO_HINT


def _registry_names():
    from tools import discover, all_tools
    discover()
    return {t["name"] for t in all_tools()}


def test_all_hinted_tools_exist():
    names = _registry_names()
    for producer, pairs in NEXT_HINTS.items():
        assert producer in names, producer
        for consumer, _why in pairs:
            assert consumer in names, (producer, consumer)


def test_no_hint_tools_exist():
    names = _registry_names()
    for n in _NO_HINT:
        assert n in names, n


def test_hint_appends_to_real_tool_output():
    from tools import execute
    # jwt_analyst offline (selftest fixture token) -> must point to jwt_forge_replay
    out = execute("jwt_analyst", {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                                           "eyJzdWIiOiJzZWxmdGVzdCIsImV4cCI6OTk5OTk5OTk5OX0."
                                           "sig"})
    assert "→ NEXT:" in out and "jwt_forge_replay" in out


def test_error_output_never_hinted():
    from tools import execute
    out = execute("__no_such_tool__", {})  # UNKNOWN_TOOL path
    assert "→ NEXT:" not in out


def test_hint_idempotent():
    o1 = hint_for("web_fingerprint", "ok")
    assert "→ NEXT:" in o1
    assert hint_for("web_fingerprint", o1) == ""  # pas de double hint


def test_no_chill_vocabulary_in_hints():
    import re
    chill = re.compile(r"(?i)\b(careful|caution|warning|dangerous|risky|illegal)\b")
    for producer, pairs in NEXT_HINTS.items():
        for _t, why in pairs:
            assert not chill.search(why), (producer, why)
