"""VOIDFORGE :: road-audit regressions — bugs found by the behavioral audit:
verdict() dict-evidence KeyError, binary_fuzz_run corpus_dir landmine."""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools._exploit_lib import verdict


def test_verdict_list_evidence_unchanged():
    out = verdict("t", True, "s", evidence=["a", "b"])
    import json
    d = json.loads(out)
    assert d["evidence"] == ["a", "b"]


def test_verdict_dict_evidence_no_keyerror():
    # historical bug: binary_fuzz_run passed a dict -> KeyError: slice
    out = verdict("t", True, "s", evidence={"crashes": [1] * 30, "execs": 5,
                                            "crash_dir": "x"})
    import json
    d = json.loads(out)
    assert isinstance(d["evidence"], dict)
    assert len(d["evidence"]["crashes"]) == 20   # list inside dict truncated
    assert d["evidence"]["execs"] == 5           # scalars preserved


def test_verdict_none_evidence():
    import json
    d = json.loads(verdict("t", False, "s", evidence=None))
    assert d["evidence"] == []


def test_binary_fuzz_run_corpus_dir_optional():
    # schema must not require corpus_dir (LLM omits it -> None crash)
    from tools import discover, all_tools
    discover()
    t = next(x for x in all_tools() if x["name"] == "binary_fuzz_run")
    assert (t["params"] or {}).get("required") == ["target_path"]
    sig = inspect.signature(t["run"])
    assert sig.parameters["corpus_dir"].default is None
