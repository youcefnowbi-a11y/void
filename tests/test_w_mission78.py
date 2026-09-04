"""VOIDFORGE :: W12-W14 — mission-78 autopsy guards.

W12: data_extract carries a persistent per-host cookie jar — login
     chains survive across calls (the #78 root cause of the mid-mission
     "Signed out" 401s, previously worked around with 6 forged tools).
W13: crash_triage_next fails USEFULLY on a directory path instead of a
     raw PermissionError (auto-resolves fuzz_findings.json inside).
W14: nested dict/list values in content_type=form bodies serialize as
     JSON inside the field — no more Clerk 422 form_param_unknown.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── W12: the jar ────────────────────────────────────────────────────

def test_w12_jar_roundtrip():
    from tools.data_exfil import _jar_capture, _jar_merge, _jar_clear, _jar_state
    _jar_clear()
    _jar_capture("https://clerk.example.com", [
        "__session=abc; Path=/; Max-Age=600",
        "__client=xyz; Path=/; Max-Age=600",
    ])
    h = _jar_merge("https://clerk.example.com/api/me", {})
    assert "__session=abc" in h["Cookie"] and "__client=xyz" in h["Cookie"]
    # a different host does NOT see the cookies
    assert "Cookie" not in (_jar_merge("https://api.example.com/x", {}) or {})
    # an explicit Cookie header is never overwritten
    own = _jar_merge("https://clerk.example.com/x",
                     {"Cookie": "custom=1"})
    assert own["Cookie"] == "custom=1"
    st = _jar_state()
    assert "clerk.example.com" in st
    _jar_clear()
    assert _jar_state() == {}


def test_w12_jar_expiry_purges_stale():
    from tools.data_exfil import _jar_capture, _jar_merge, _jar_clear
    _jar_clear()
    _jar_capture("https://x.example.com",
                 ["dead=1; Expires=Thu, 01 Jan 1970 00:00:00 GMT",
                  "alive=2; Max-Age=600"])
    h = _jar_merge("https://x.example.com/", {})
    assert "alive=2" in h["Cookie"] and "dead=1" not in h["Cookie"]
    _jar_clear()


def test_w12_data_extract_schema_has_jar_params():
    from tools import all_tools
    t = next((t for t in all_tools() if t["name"] == "data_extract"), None)
    assert t, "data_extract registered"
    props = t["params"]["properties"]
    assert "use_jar" in props and "jar_clear" in props
    assert "use_jar" in t["desc"]


# ── W13: useful failure on directory paths ─────────────────────────

def test_w13_triage_directory_fails_usefully(tmp_path=None):
    from tools.crash_triage import crash_triage_next
    out = crash_triage_next(path=os.path.dirname(os.path.abspath(__file__)))
    s = str(out)
    assert "DIRECTORY" in s or "fuzz_attack_surface" in s
    # and it never raises


def test_w13_triage_directory_autodiscovery(tmp_path=None):
    import tempfile
    from tools.crash_triage import crash_triage_next
    d = tempfile.mkdtemp(prefix="vf_w13_")
    with open(os.path.join(d, "fuzz_findings.json"), "w",
              encoding="utf-8") as f:
        json.dump([{"url_path": "/x", "param": "q", "payload": "'\"",
                    "severity": 0.8, "signals": ["status_5xx(500)"]}], f)
    out = str(crash_triage_next(path=d))
    assert "triaged finding" in out or "1 triaged" in out
    import shutil
    shutil.rmtree(d, ignore_errors=True)


# ── W14: form-encoding nested values ──────────────────────────────

def test_w14_form_nested_values_json_encoded():
    # Z1.2 migrated _http onto tools._transport.fetch — the W14 encoding
    # now lives in the adapter's pre-cooked wire body. Assert the same
    # contract at the new seam.
    from unittest.mock import patch
    from tools import data_exfil
    sent = {}

    def fake_fetch(url, method="GET", headers=None, body=None,
                   timeout=25, use_cache=False):
        sent["body"] = body
        sent["ct"] = (headers or {}).get("Content-Type")
        return {"status": 200, "body": "{}", "headers": {},
                "size": 2, "final_url": url}

    with patch("tools._transport.fetch", fake_fetch):
        data_exfil._http("https://api.example.com/login", method="POST",
                         body={"identifier": "op@x.io", "strategy": "password",
                               "meta": {"device": "test"}},
                         content_type="form")
    body = (sent["body"] or b"").decode()
    assert "identifier=op%40x.io" in body
    assert "meta=%7B%22device%22%3A" in body, \
        "nested dict must JSON-encode inside the form field"
    assert sent["ct"] == "application/x-www-form-urlencoded"
