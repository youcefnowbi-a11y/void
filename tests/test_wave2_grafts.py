"""VOIDFORGE :: wave2 P4/P5 + G13 tests — captcha detection, impersonation
config, scope guard. No network (solvers need keys; none here)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import _transport as t


def test_captcha_challenge_detection():
    # turnstile
    ch = t._captcha_challenge('<div class="cf-turnstile" data-sitekey="0x4AAAAAAADnPIDROrmt1Wwj"></div>')
    assert ch == ("turnstile", "0x4AAAAAAADnPIDROrmt1Wwj")
    # hcaptcha
    ch2 = t._captcha_challenge('sitekey: "10000000-ffff-ffff-ffff-000000000001" hcaptcha')
    assert ch2 and ch2[0] == "hcaptcha"
    # recaptcha v2
    ch3 = t._captcha_challenge('g-recaptcha" data-sitekey="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-')
    assert ch3 and ch3[0] == "recaptcha"
    # pas de challenge
    assert t._captcha_challenge("<html>normal page</html>") is None


def test_captcha_off_by_default():
    t._CAPTCHA_CFG_LOADED[0] = False
    t._CAPTCHA_CFG[0] = None
    cfg = t._captcha_cfg()
    assert (cfg.get("provider") or "none") == "none" or cfg.get("provider") is None
    # solve sans config = None, sans lever d'exception
    assert t._captcha_solve("turnstile", "0xKey", "https://t.local/x") is None


def test_captcha_budget_guard():
    t._CAPTCHA_BUDGET[0] = 0
    t._CAPTCHA_CFG_LOADED[0] = True
    t._CAPTCHA_CFG[0] = {"provider": "capsolver", "api_key": "K"}
    assert t._captcha_solve("turnstile", "k", "u") is None  # budget épuisé
    t._CAPTCHA_BUDGET[0] = 3


def test_impersonate_config_loads():
    prof = t._imp_profile()
    # transport.yaml ships impersonate: "chrome" et curl_cffi est installé
    assert prof in (None, "chrome", "chrome124", "safari")


def test_scope_guard_local_allowed_out_blocked():
    scope = {"in_scope": ["target-example.com"], "out_of_scope": ["mail.target-example.com"]}
    assert t is not None
    from tools import _host_allowed
    assert _host_allowed("target-example.com", scope)
    assert _host_allowed("sub.target-example.com", scope)
    assert not _host_allowed("mail.target-example.com", scope)   # out_of_scope gagne
    assert not _host_allowed("evil.example.net", scope)
    assert _host_allowed("localhost", scope)                     # local toujours ok
    assert _host_allowed("127.0.0.1", scope)
    assert _host_allowed("10.1.2.3", scope)                      # privé ok


def test_scope_check_on_args():
    from tools import _scope_check
    scope = {"in_scope": ["target-example.com"], "out_of_scope": []}
    assert _scope_check({"url": "https://target-example.com/api"}, scope) is None
    err = _scope_check({"url": "https://off-target.net/admin"}, scope)
    assert err and "SCOPE_BLOCKED" in err
    # pas de périmètre défini → pas de garde
    assert _scope_check({"url": "https://anything.t"}, {"in_scope": []}) is None


def test_execute_scope_blocked_end_to_end():
    import tools as reg
    reg.discover()
    # injection du scope par monkeypatch (pas de fichier touché)
    orig = reg._load_scope
    reg._load_scope = lambda: {"in_scope": ["target-example.com"], "out_of_scope": []}
    try:
        out = reg.execute("web_fingerprint", {"url": "https://off-target.net/"})
        assert "SCOPE_BLOCKED" in out
    finally:
        reg._load_scope = orig
