"""VOIDFORGE :: V3 depth tests — har_passive_scan (offline HAR) + spa_crawl schema."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools as reg
reg.discover()

HAR = {
    "log": {"entries": [
        {"request": {"url": "https://shop.t/api/v1/orders/42",
                     "headers": [], "queryString": []},
         "response": {"status": 200, "headers": [{"name": "Set-Cookie",
                     "value": "sid=abc123; Path=/"},
                     {"name": "Content-Type", "value": "application/json"}],
                      "content": {"text": '{"price": 10, "balance": 500}'}}},
        {"request": {"url": "https://shop.t/api/me",
                     "headers": [{"name": "Authorization", "value": "Bearer eyJhbGciOiJub25lIn0.eyJyb2xlIjoiYWRtaW4iLCJleHAiOjE5MDAwMDAwMDB9.sig"}],
                     "queryString": []},
         "response": {"status": 200, "headers": [],
                      "content": {"text": "sk_live_abcdefghijklmnop1234"}}},
    ]}
}


def _write_har(tmp_path):
    p = os.path.join(str(tmp_path), "t.har")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(HAR, f)
    return p


def test_registered_and_safe():
    t = reg.get("har_passive_scan")
    assert t["danger"] == "safe"


def test_passive_scan_finds_all_classes(tmp_path):
    out = reg.execute("har_passive_scan", {"har_path": _write_har(tmp_path)})
    assert "IDOR" in out and "orders/42" in out          # idor-shaped
    assert "MONEY" in out and "price" in out             # money fields
    assert "JWT" in out and "none" in out                # alg none + role admin
    assert "SECRETS" in out and "sk_live_" in out        # secret in response
    assert "COOKIES" in out and "sid" in out             # cookie sans flags
    assert "HEADERS" in out                              # security headers absents


def test_passive_scan_bad_inputs():
    assert "NO_HAR" in reg.execute("har_passive_scan", {"har_path": "Z:/nope.har"})
    assert "BAD_HAR" in reg.execute("har_passive_scan", {"har_path": __file__})


def test_spa_crawl_schema_has_forms():
    t = reg.get("spa_crawl")
    # desc mentions the V3 forms surface
    assert "forms" in t["desc"].lower()
