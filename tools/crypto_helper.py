"""TOOL: crypto_helper — local cryptographic primitives for offensive ops.

No network calls, no external deps.  Computes hashes, HMACs, base64,
and common signing schemes (md5(base64(body)+key), HMAC-SHA256, etc.)
so the LLM never has to hand-compute base64 or call hashify.net again.
"""
import base64
import hashlib
import hmac as _hmac
import json
import time
from tools import register


@register(
    name="crypto_hash",
    desc="Compute hash/HMAC/base64/signing primitives locally — NO network. "
         "Ops: md5, sha1, sha256, sha512, hmac_sha256, hmac_md5, "
         "base64_encode, base64_decode, base64url_encode, base64url_decode, "
         "helmer_sign (md5(base64(body)+key)), jwt_decode. "
         "Use for forging signatures, verifying webhooks, computing HMAC, "
         "encoding payloads. Returns hex digest for hashes, text for base64.",
    params={"type": "object", "properties": {
        "op": {"type": "string",
               "enum": ["md5", "sha1", "sha256", "sha512",
                        "hmac_sha256", "hmac_md5",
                        "base64_encode", "base64_decode",
                        "base64url_encode", "base64url_decode",
                        "helmer_sign", "jwt_decode"],
               "description": "Operation to perform"},
        "data": {"type": "string",
                 "description": "Input string (plaintext for hash/encode, "
                                "encoded string for decode, body for sign, "
                                "full JWT for jwt_decode)"},
        "key": {"type": "string",
                "description": "Key for HMAC/signing ops (api_key for "
                               "helmer_sign, secret for hmac). "
                               "Ignored for plain hash/encode ops."},
    }, "required": ["op", "data"]},
    danger="safe"
)
def crypto_hash(op, data, key=""):
    result = {"op": op, "input_len": len(data)}

    try:
        if op == "md5":
            h = hashlib.md5(data.encode()).hexdigest()
            result["hex"] = h

        elif op == "sha1":
            h = hashlib.sha1(data.encode()).hexdigest()
            result["hex"] = h

        elif op == "sha256":
            h = hashlib.sha256(data.encode()).hexdigest()
            result["hex"] = h

        elif op == "sha512":
            h = hashlib.sha512(data.encode()).hexdigest()
            result["hex"] = h

        elif op == "hmac_sha256":
            if not key:
                return {"error": "hmac_sha256 requires key param"}
            h = _hmac.new(key.encode(), data.encode(),
                          hashlib.sha256).hexdigest()
            result["hex"] = h
            result["header_value"] = f"sha256={h}"

        elif op == "hmac_md5":
            if not key:
                return {"error": "hmac_md5 requires key param"}
            h = _hmac.new(key.encode(), data.encode(),
                          hashlib.md5).hexdigest()
            result["hex"] = h

        elif op == "base64_encode":
            b = base64.b64encode(data.encode()).decode()
            result["encoded"] = b

        elif op == "base64_decode":
            # auto-pad if needed
            padded = data + "=" * (-len(data) % 4)
            b = base64.b64decode(padded).decode(errors="replace")
            result["decoded"] = b

        elif op == "base64url_encode":
            b = base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")
            result["encoded"] = b

        elif op == "base64url_decode":
            padded = data + "=" * (-len(data) % 4)
            b = base64.urlsafe_b64decode(padded).decode(errors="replace")
            result["decoded"] = b

        elif op == "helmer_sign":
            # Heleket/Cryptomus signing: sign = md5(base64(body) + api_key)
            if not key:
                return {"error": "helmer_sign requires key param (api_key)"}
            b64 = base64.b64encode(data.encode()).decode()
            concat = b64 + key
            h = hashlib.md5(concat.encode()).hexdigest()
            result["base64_body"] = b64
            result["concat_preview"] = (b64[:40] + "..." + key[:12] + "..."
                                        if len(concat) > 60 else concat)
            result["sign"] = h

        elif op == "jwt_decode":
            parts = data.split(".")
            if len(parts) < 2:
                return {"error": "Not a JWT (expected header.payload.sig)"}
            decoded = {}
            for label, part in zip(["header", "payload"], parts[:2]):
                padded = part + "=" * (-len(part) % 4)
                try:
                    raw = base64.urlsafe_b64decode(padded)
                    decoded[label] = json.loads(raw)
                except Exception:
                    decoded[label] = base64.urlsafe_b64decode(
                        padded).decode(errors="replace")
            if len(parts) >= 3:
                decoded["signature_b64"] = parts[2][:48] + (
                    "..." if len(parts[2]) > 48 else "")
            # check expiry
            payload = decoded.get("payload", {})
            if isinstance(payload, dict):
                exp = payload.get("exp")
                if exp:
                    now = int(time.time())
                    decoded["expired"] = now > exp
                    decoded["expires_in_s"] = exp - now
                iat = payload.get("iat")
                if iat:
                    decoded["age_s"] = int(time.time()) - iat
            result["jwt"] = decoded

        else:
            return {"error": f"Unknown op: {op}"}

    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)}"}

    return json.dumps(result, ensure_ascii=False)
