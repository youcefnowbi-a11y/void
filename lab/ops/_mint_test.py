# -*- coding: utf-8 -*-
"""Test: strike reports mint finding cards (mission-79 APP-STATE #8)."""
import sys, os, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mission_workspace import Workspace

tmp = tempfile.mkdtemp()
try:
    ws = Workspace(target="__mintest_tmp")
    # redirect into temp dir
    for attr, sub in (("dir", ""), ("reports", "reports"),
                      ("findings", "findings")):
        setattr(ws, attr, os.path.join(tmp, sub))
    os.makedirs(ws.reports, exist_ok=True)
    os.makedirs(ws.findings, exist_ok=True)

    p = ws.write_report("BOLA deals CONFIRMED - participant scope bypass",
                        "CRITICAL finding: cross-tenant access confirmed. "
                        "exploitable: true, evidence archived.",
                        kind="strike")
    print("report saved:", os.path.basename(p))
    cards = os.listdir(ws.findings)
    print("finding cards minted:", cards)
    assert cards, "MINT FAILED — no card"
    assert "confirmed" in cards[0], f"wrong tag: {cards[0]}"

    # negative: a progress report must NOT mint
    p2 = ws.write_report("recon recap", "mapped the surface, nothing "
                         "confirmed yet", kind="progress")
    cards2 = os.listdir(ws.findings)
    assert len(cards2) == 1, f"progress minted a card: {cards2}"
    print("PASS — strike mint works, progress stays silent")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
