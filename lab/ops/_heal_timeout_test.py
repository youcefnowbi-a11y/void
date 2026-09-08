# -*- coding: utf-8 -*-
"""Test: knobless TIMEOUT heal — paced retry once, then honest stop."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import healer as H

# clean slate
try:
    H._save_fixes({})
except Exception:
    pass

# 1st timeout: paced retry (healed args returned)
args, note = H.heal_attempt("forged_test_tool", "TIMEOUT", "timed out",
                            {"url": "https://x/y.js"})
print("attempt1:", args is not None, "-", note)

# 2nd timeout (same tool): honest stop with diagnosis
args2, note2 = H.heal_attempt("forged_test_tool", "TIMEOUT", "timed out",
                              {"url": "https://x/y.js"})
print("attempt2:", args2 is None, "-", note2[:80])

# fresh tool: counter independent
args3, note3 = H.heal_attempt("another_tool", "TIMEOUT", "timed out", {})
print("attempt3 (fresh tool):", args3 is not None, "-", note3)
print("PASS" if (args is not None and args2 is None and args3 is not None) else "FAIL")
