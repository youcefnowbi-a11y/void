# -*- coding: utf-8 -*-
"""Guard tests — operator-identity scrubber (deliverables never testify)."""
import socket
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
from core.scrub import scrub, egress_summary


def test_real_hostname_never_survives():
    host = socket.gethostname()
    out = scrub(f"fingerprint of {host} completed, 200 OK")
    assert "[OPERATOR]" in out and host not in out


def test_home_path_never_survives():
    out = scrub("read C:\\Users\\someone-else\\D\\VOIDFORGE\\core\\agent.py")
    assert "C:\\Users\\someone-else" not in out
    assert "[OPERATOR-HOME]" in out


def test_relay_credentials_never_survive():
    out = scrub("egress via socks5://user:secret123@10.0.0.9:1080 then retry")
    assert "secret123" not in out
    assert "[REDACTED]@" in out
    assert "socks5://" in out  # le schéma reste, les creds partent


def test_target_evidence_untouched():
    sample = ("venice.ai 200 clientSecret cs_live_abc; Stripe init amount "
              "18000; PATCH accepted")
    out = scrub(sample)
    assert out == sample  # la preuve cible n'est JAMAIS altérée


def test_idempotent():
    once = scrub("host " + socket.gethostname() + " path C:\\Users\\x\\file")
    twice = scrub(once)
    assert once == twice


def test_egress_summary_shape():
    e = egress_summary()
    assert e["mode"] in ("direct", "relayed")
    assert isinstance(e["exits"], int)
