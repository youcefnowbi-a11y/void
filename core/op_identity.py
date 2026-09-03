"""VOIDFORGE :: operational identity — burnable per-target personas (Tier C).

Each target host gets ONE operational identity, deterministically derived and
STABLE for the whole campaign (fingerprint consistency is survival — a UA
that changes mid-session or a language that contradicts the geo is a bot
tell), and BURNED on an explicit block signal (captcha wall, 403-flood,
WAF challenge): the next attempt on that host starts from a fresh identity.

Identity = the accent of the machine, not who we are (IP comes from the
egress pool, credentials from the operator). Nothing here is secret:
consistency is the whole craft.
"""
import hashlib
import threading

_LOCK = threading.Lock()
_IDENTITY = {}   # host -> {"ua", "lang", "burned"}

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]
_LANG_POOL = ["en-US,en;q=0.9", "en-GB,en;q=0.7", "fr-FR,fr;q=0.9,en;q=0.5",
              "de-DE,de;q=0.9,en;q=0.6", "es-ES,es;q=0.9,en;q=0.5"]


def _derive(host, gen):
    """Deterministic per (host, generation) identity — stable within a
    campaign, fresh after a burn."""
    seed = hashlib.sha1(f"{host}#{gen}".encode()).digest()
    ua = _UA_POOL[seed[0] % len(_UA_POOL)]
    lang = _LANG_POOL[seed[1] % len(_LANG_POOL)]
    return {"ua": ua, "lang": lang, "gen": gen, "burned": False}


def identity_for(host, renew=False):
    """The operational identity for this target — same all campaign long.
    renew=True: after a burn, the NEXT call re-derives (gen+1) — used by the
    transport so every post-burn request automatically speaks fresh."""
    host = (host or "").lower().strip()
    if not host:
        return {"ua": _UA_POOL[0], "lang": _LANG_POOL[0],
                "gen": 0, "burned": False}
    with _LOCK:
        cur = _IDENTITY.get(host)
        if cur is None:
            cur = _derive(host, 0)
            _IDENTITY[host] = cur
        elif renew and cur.get("burned"):
            cur = _derive(host, cur["gen"] + 1)
            _IDENTITY[host] = cur
        return dict(cur)


def burn(host, reason=""):
    """Kill this target's identity — next attempt speaks with a new accent.
    Called by the transport on captcha-wall / hard WAF block / 403-flood."""
    host = (host or "").lower().strip()
    with _LOCK:
        cur = _IDENTITY.get(host)
        if cur is not None:
            cur["burned"] = True
        return {"host": host, "gen": (cur["gen"] + 1) if cur else 1,
                "reason": (reason or "")[:120]}


def burned_count():
    with _LOCK:
        return sum(1 for v in _IDENTITY.values() if v.get("burned"))


def summary():
    """Op-visibility: how many live/burned identities this process carries."""
    with _LOCK:
        live = [h for h, v in _IDENTITY.items() if not v["burned"]]
        dead = [h for h, v in _IDENTITY.items() if v["burned"]]
    return {"live": sorted(live), "burned": sorted(dead)}
