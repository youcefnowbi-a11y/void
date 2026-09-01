"""TOOL: jwt_analyst - decode and analyze JWTs without trusting them.

Decodes header/payload, checks expiry, and flags the classic pitfalls:
alg=none acceptance (server-side, can only be proven by replay), missing
exp, iat in the future, kid header injection surface, long-lived tokens.
"""
import base64, json, time
from tools import register


def _b64d(s):
    s = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode()).decode(errors="replace")


def _decode(token):
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("not a JWT shape")
    header = json.loads(_b64d(parts[0]))
    payload = json.loads(_b64d(parts[1]))
    return header, payload, parts[2] if len(parts) > 2 else ""


@register(name="jwt_analyst",
          desc="Decode JWT(s): header/payload, expiry status, algorithm analysis, pitfall flags (alg=none, no exp, kid injection surface). Feed any token from js_mine/spa_crawl output.",
          params={"type": "object", "properties": {
              "token": {"type": "string", "description": "one JWT or several separated by whitespace/commas"}},
              "required": ["token"]})
def jwt_analyst(token):
    tokens = [t for t in token.replace(",", " ").split() if t.count(".") >= 2 and t.startswith("eyJ")]
    if not tokens:
        return json.dumps({"error": "no JWT-looking strings found in input"})
    now = int(time.time())
    out = []
    for t in tokens[:8]:
        try:
            head, payload, sig = _decode(t)
        except Exception as ex:
            out.append({"error": f"decode failed: {str(ex)[:80]}", "token_prefix": t[:30]})
            continue
        flags = []
        alg = head.get("alg", "?")
        if alg.lower() == "none":
            flags.append("ALG=NONE — server may accept unsigned tokens; TEST with forged none-token")
        if not sig:
            flags.append("NO SIGNATURE SEGMENT")
        if "exp" not in payload:
            flags.append("NO exp CLAIM — token never expires (or expiry checked client-side only)")
        elif payload["exp"] < now:
            flags.append(f"EXPIRED {now - payload['exp']}s ago (server may not check!)")
        if payload.get("iat", 0) > now + 300:
            flags.append("iat IN THE FUTURE")
        if head.get("kid") and ("../" in str(head["kid"])) is False and len(str(head.get("kid"))) < 40:
            flags.append(f"kid={head['kid'][:30]} — kid header present (injection/path-traversal surface on some libs)")
        if payload.get("role") in ("anon", "anonymous"):
            flags.append("anon role — check if role claim is client-trusted (try forging role=admin)")
        out.append({"header": head, "payload": payload,
                    "signature_prefix": sig[:12], "flags": flags,
                    "expires_in": (payload["exp"] - now) if "exp" in payload else None})
    return json.dumps({"tokens": len(out), "analysis": out}, ensure_ascii=False, indent=1)[:14000]
