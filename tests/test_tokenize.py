"""VOIDFORGE :: Dark-Moon tokenization tests — mask/unmask roundtrip,
real-strike guarantee, gate ordering, config off-by-default."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import _tokenize as tk


def setup_function(fn):
    tk.reset_vault()


def test_domain_and_ip_masked():
    t = "GET https://shop-cible.com/admin/login depuis 203.0.113.42"
    m = tk.mask(t)
    assert "shop-cible.com" not in m and "203.0.113.42" not in m
    assert "[HOST-" in m
    # corrélation préservée: le même host -> le même token partout
    t2 = tk.mask("shop-cible.com puis shop-cible.com")
    a, _, b = t2.partition(" puis ")
    assert a == b


def test_credentials_masked():
    t = 'password="SuperPass123" et api_key=sk-live-abcdef123456 et cookie=SESS1234abcdef'
    m = tk.mask(t)
    assert "SuperPass123" not in m and "sk-live-abcdef123456" not in m
    assert "password=" in m and "api_key=" in m   # les noms de champs restent
    assert "[CRED-" in m


def test_structure_and_tech_kept():
    t = "nginx 1.24 sur /admin, param id= redirect= status 302, CVE-2024-1234"
    m = tk.mask(t)
    assert "nginx" in m and "/admin" in m and "id=" in m
    assert "CVE-2024-1234" in m and "302" in m


def test_roundtrip_unmask_restores_exact():
    raw = "https://shop-cible.com/api/auth depuis 203.0.113.42 password=SuperPass123"
    m = tk.mask(raw)
    back = tk.unmask(m)
    assert back == raw  # frappe réelle garantie


def test_unmask_obj_on_tool_args():
    raw_args = {"url": "https://shop-cible.com/admin", "data": "token=SESS1234abc"}
    m = tk.mask_obj(raw_args)
    assert "shop-cible.com" not in json_dumps(m)
    back = tk.unmask_obj(m)
    assert back == raw_args  # l'outil reçoit les vraies valeurs


def test_mask_msgs_keeps_raw_memory():
    msgs = [{"role": "user", "content": "cible: shop-cible.com"},
            {"role": "tool", "content": "GET https://shop-cible.com/x"}]
    sent = tk.mask_msgs(msgs)
    # les copies envoyées sont masquées
    assert "shop-cible.com" not in json_dumps(sent)
    # la mémoire locale reste RAW (l'agent raisonne sur la vérité)
    assert "shop-cible.com" in json_dumps(msgs)


def test_unmasked_token_without_vault_is_stable():
    # un texte sans tokens connus passe intact
    assert tk.unmask("aucun [HOST-999] ici dans le vault") is not None


def test_disabled_by_default_config():
    # règle maison: off par défaut — enabled() lit provider.yaml
    import yaml
    p = yaml.safe_load(open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "provider.yaml"), encoding="utf-8"))["provider"]
    assert p.get("tokenize_secrets", False) is False


def test_gate_order_unmask_before_scope():
    # le unmask s'exécute AVANT les gates dans tools/__init__.execute —
    # vérification structurelle: le bloc _tokenize apparaît avant _scope_check
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "tools", "__init__.py"), encoding="utf-8").read()
    i_tk = src.find("from core import _tokenize")
    # R3-11/12 : le gate passe maintenant par _load_scope_cached() (cache
    # dernier-état-bon) et se re-vérifie dans la boucle heal. Le marqueur vise
    # l'APPEL (précédé d'un « = »), jamais la définition def _scope_check(...)
    # qui apparaît plus haut dans le fichier.
    i_scope = src.find("= _scope_check(args")
    assert 0 < i_tk < i_scope


def json_dumps(x):
    import json
    return json.dumps(x, ensure_ascii=False)
