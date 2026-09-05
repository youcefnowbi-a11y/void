import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.advanced_web import race_smash
from tools.graphql_scan import graphql_introspect
from tools.idor_ripper import idor_b64_walk, _is_error_page
from core.proxy import get_opener, get_pool


def test_omega_race_smash_json_handling(monkeypatch):
    sent_requests = []

    def fake_raw_roundtrip(host, port, req_bytes, timeout=8, use_ssl=False):
        sent_requests.append(req_bytes)
        return "HTTP/1.1 200 OK", "applied", 0.01

    monkeypatch.setattr("tools.advanced_web._raw_roundtrip", fake_raw_roundtrip)
    raw_res = race_smash("https://example.com/api/coupon",
                         body={"code": "VIP50"},
                         headers={"Content-Type": "application/json", "Authorization": "Bearer tok"},
                         concurrency=2, rounds=2, success_pattern="applied")

    res = json.loads(raw_res)
    assert res["exploitable"] is True
    assert len(sent_requests) == 4
    req_str = sent_requests[0].decode("utf-8")
    assert '{"code": "VIP50"}' in req_str
    assert req_str.count("Content-Type:") == 1
    assert "Content-Type: application/json" in req_str


def test_omega_race_smash_none_headers(monkeypatch):
    """Verify race_smash handles headers=None without NoneType exception."""
    sent_requests = []

    def fake_raw_roundtrip(host, port, req_bytes, timeout=8, use_ssl=False):
        sent_requests.append(req_bytes)
        return "HTTP/1.1 200 OK", "ok", 0.01

    monkeypatch.setattr("tools.advanced_web._raw_roundtrip", fake_raw_roundtrip)
    raw_res = race_smash("https://example.com/api/action", headers=None, concurrency=2, rounds=1)
    res = json.loads(raw_res)
    assert "races executed" in res.get("summary", "")


def test_omega_graphql_introspect_verdict_contract(monkeypatch):
    mock_schema = {
        "data": {
            "__schema": {
                "types": [
                    {"name": "User", "fields": [{"name": "id"}, {"name": "password"}]},
                    {"name": "Query", "fields": [{"name": "users"}]}
                ]
            }
        }
    }

    def fake_post_graphql(url, query_payload, anon_key=None, timeout=15):
        return 200, json.dumps(mock_schema)

    monkeypatch.setattr("tools.graphql_scan._post_graphql", fake_post_graphql)
    raw_res = graphql_introspect("https://example.com/graphql")

    res = json.loads(raw_res)
    assert res.get("exploitable") is True
    assert "CONFIRMED" in res.get("summary", "")
    assert res.get("endpoint") == "https://example.com/graphql"
    assert any(f["field"] == "password" for f in res.get("sensitive_fields", []))


def test_omega_idor_b64_walk_auth_and_profile(monkeypatch):
    captured_headers = []

    def fake_paced_send(url, headers=None, **kw):
        captured_headers.append(headers or {})
        return 200, '{"id": 1, "login": "admin_user", "email": "admin@example.com"}', 0.05

    monkeypatch.setattr("tools.idor_ripper.paced_send", fake_paced_send)
    # Test with dict header as well
    raw_res = idor_b64_walk("https://example.com/api/users/{ID}", start=1, stop=2,
                            attacker_header={"Authorization": "Bearer dict_jwt"})

    res = json.loads(raw_res)
    assert res.get("exploitable") is True
    assert len(res.get("hits", [])) == 2
    assert captured_headers[0].get("Authorization") == "Bearer dict_jwt"
    assert _is_error_page('{"id": 1, "login": "admin_user"}') is False


def test_omega_proxy_socks_graceful():
    pool = get_pool()
    pool.proxies = ["socks5://127.0.0.1:9050"]
    pool._index = 0
    opener = get_opener()
    assert opener is None or hasattr(opener, "open")
