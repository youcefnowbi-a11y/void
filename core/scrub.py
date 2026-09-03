"""VOIDFORGE :: operator-identity scrubber — the deliverables never testify
about the operator.

What leaves the machine (client-bound reports, dossiers, app-state) must not
carry: the Windows hostname, the local username (any casing), local home
paths (C:\\Users\\<user>\\…), LAN/private IPs of the operator's machine, or
the egress relay URLs (which can embed credentials). Target-side artifacts —
domains, target IPs, captured tokens — are EVIDENCE and are never touched.

The workspace extractions/ledger stay RAW: the operator needs the full data
locally. Scrubbing happens at deliverable-write time, in one place.
"""
import os
import re
import socket

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOADED = [False]
_STRINGS = []      # exact operator strings to replace (longest first)
_IPS = []          # literal operator IPs -> [OPERATOR-IP-n]
_RELAYS = []       # egress URLs -> [EGRESS-n]
_FALLBACK_USER = re.compile(r"C:\\Users\\[^\\\s:]+\\", re.I)
# AUDIT F5 — défense en profondeur SANS destruction de preuve : les credentials
# socks (relays, jamais de la cible) sont masqués même non configurés ; mais
# `https://admin:admin@target.example` peut ÊTRE la découverte (creds-in-URL)
# — la preuve cible http(s)/ftp reste intacte. Les relays http configurés
# sont déjà couverts par le masque _RELAYS ci-dessus.
_CREDS_URL = re.compile(
    r"\b((?:socks5h?|socks4)://)([^\s/:@]+):([^\s/@]+)@", re.I)


def _mask_relay(i, url):
    try:
        from urllib.parse import urlsplit
        sp = urlsplit(url)
        host = sp.hostname or "relay"
        return f"[EGRESS-{i + 1}·{host}]"
    except Exception:
        return f"[EGRESS-{i + 1}]"


def _load():
    if _LOADED[0]:
        return
    _LOADED[0] = True
    # 1. machine identity
    try:
        _STRINGS.append(socket.gethostname() or "")
    except Exception:
        pass
    try:
        fqdn = socket.getfqdn()
        if fqdn and fqdn not in _STRINGS:
            _STRINGS.append(fqdn)
    except Exception:
        pass
    user = (os.path.basename(os.path.expanduser("~")) or "").strip()
    if user:
        _STRINGS.append(user)
    try:
        import getpass
        gu = (getpass.getuser() or "").strip()
        if gu and gu not in _STRINGS:
            _STRINGS.append(gu)
    except Exception:
        pass
    # 2. LAN/private IPs of this machine (target IPs are NEVER listed here)
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        for inf in infos:
            ip = inf[4][0]
            if ip and ip not in _IPS and not ip.startswith("127."):
                _IPS.append(ip)
    except Exception:
        pass
    _STRINGS[:] = [s for s in _STRINGS if s and len(s) >= 3]
    _STRINGS.sort(key=len, reverse=True)
    # 3. egress relays (transport.yaml first-class pool + legacy proxies.txt)
    for fname, key in (("transport.yaml", ("transport", "proxies")),
                       ("proxies.txt", None)):
        p = os.path.join(_HERE, os.pardir, "config", fname)
        if not os.path.exists(p):
            continue
        try:
            if key:
                import yaml
                with open(p, encoding="utf-8") as f:
                    d = yaml.safe_load(f) or {}
                urls = list((((d.get(key[0]) or {})
                              .get(key[1])) or []))
            else:
                with open(p, encoding="utf-8") as f:
                    urls = [ln.strip() for ln in f
                            if ln.strip() and not ln.strip().startswith("#")]
            for u in urls:
                if isinstance(u, str) and "://" in u and u not in _RELAYS:
                    _RELAYS.append(u)
        except Exception:
            pass


def egress_summary():
    """{mode, exits} — how the arsenal leaves the machine right now."""
    _load()
    if _RELAYS:
        return {"mode": "relayed", "exits": len(_RELAYS)}
    return {"mode": "direct", "exits": 0}


def scrub(text):
    """Strip operator identity from deliverable text. Idempotent."""
    if not text:
        return text
    _load()
    for i, url in enumerate(_RELAYS):
        text = text.replace(url, _mask_relay(i, url))
    for i, ip in enumerate(_IPS):
        text = text.replace(ip, f"[OPERATOR-IP-{i + 1}]")
    for s in _STRINGS:
        text = text.replace(s, "[OPERATOR]")
    # credentials dans une URL (configurée ou pas) : jamais
    text = _CREDS_URL.sub(lambda m: f"{m.group(1)}[REDACTED]@", text)
    # dernier filet : tout chemin utilisateur résiduel (autre session Windows)
    text = _FALLBACK_USER.sub(lambda m: "[OPERATOR-HOME]\\", text)
    return text
