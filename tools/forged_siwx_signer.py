"""VOIDFORGE :: forged tool — siwx_signer
Mint a fresh EVM wallet and build a signed SIWX (Sign-In-With-X) base64 header for api.venice.ai x402 auth — plus an invalid-signature control header
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(**kwargs):
    import json, base64, time, secrets
    result = {"ok": False, "errors": []}
    nonce = secrets.token_hex(10)
    issued = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    exp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(time.time() + 600))
    # --- Attempt 1: eth_account (full SIWE signing) ---
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
        acct = Account.create()
        addr = acct.address
        msg = (f"api.venice.ai wants you to sign in with your Ethereum account:\n{addr}\n\n"
               f"Sign in to Venice AI\n\nURI: https://api.venice.ai\nVersion: 1\nChain ID: 8453\n"
               f"Nonce: {nonce}\nIssued At: {issued}\nExpiration Time: {exp}")
        sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
        if not sig.startswith('0x'):
            sig = '0x' + sig
        payload = {"address": addr, "message": msg, "signature": sig,
                   "timestamp": int(time.time() * 1000), "chainId": "8453"}
        hdr = base64.b64encode(json.dumps(payload).encode()).decode()
        # invalid-signature control variant (same shape, garbage sig)
        bad = dict(payload); bad["signature"] = "0x" + "00" * 65
        bad_hdr = base64.b64encode(json.dumps(bad).encode()).decode()
        return json.dumps({"ok": True, "lib": "eth_account", "address": addr,
                           "header_valid": hdr, "header_invalid_control": bad_hdr,
                           "nonce": nonce, "issuedAt": issued, "expirationTime": exp})
    except Exception as e:
        result["errors"].append(f"eth_account: {e}")
    # --- Attempt 2: coincurve ---
    try:
        import coincurve
        from Crypto.Hash import keccak
        sk = coincurve.PrivateKey(secrets.token_bytes(32))
        pub = sk.public_key.format(compressed=False)[1:]
        k = keccak.new(digest_bits=256); k.update(pub)
        addr = '0x' + k.hexdigest()[-40:]
        msg = (f"api.venice.ai wants you to sign in with your Ethereum account:\n{addr}\n\n"
               f"Sign in to Venice AI\n\nURI: https://api.venice.ai\nVersion: 1\nChain ID: 8453\n"
               f"Nonce: {nonce}\nIssued At: {issued}\nExpiration Time: {exp}")
        k2 = keccak.new(digest_bits=256)
        prefix = f"\x19Ethereum Signed Message:\n{len(msg)}".encode()
        k2.update(prefix + msg.encode())
        sig_rs = sk.sign_recoverable(k2.digest())
        r = sig_rs[:32].hex(); s = sig_rs[32:64].hex(); v = sig_rs[64] + 27
        sig = '0x' + r + s + hex(v)[2:]
        payload = {"address": addr, "message": msg, "signature": sig,
                   "timestamp": int(time.time() * 1000), "chainId": "8453"}
        hdr = base64.b64encode(json.dumps(payload).encode()).decode()
        return json.dumps({"ok": True, "lib": "coincurve", "address": addr,
                           "header_valid": hdr, "nonce": nonce,
                           "issuedAt": issued, "expirationTime": exp})
    except Exception as e:
        result["errors"].append(f"coincurve: {e}")
    # --- Attempt 3: ecdsa + pycryptodome keccak (non-recoverable sig, still tests server verification) ---
    try:
        import ecdsa
        from Crypto.Hash import keccak
        sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        vk = sk.get_verifying_key()
        pub = vk.to_string()
        k = keccak.new(digest_bits=256); k.update(pub)
        addr = '0x' + k.hexdigest()[-40:]
        msg = (f"api.venice.ai wants you to sign in with your Ethereum account:\n{addr}\n\n"
               f"Sign in to Venice AI\n\nURI: https://api.venice.ai\nVersion: 1\nChain ID: 8453\n"
               f"Nonce: {nonce}\nIssued At: {issued}\nExpiration Time: {exp}")
        k2 = keccak.new(digest_bits=256)
        prefix = f"\x19Ethereum Signed Message:\n{len(msg)}".encode()
        k2.update(prefix + msg.encode())
        sig = '0x' + sk.sign_digest(k2.digest()).hex() + '1b'
        payload = {"address": addr, "message": msg, "signature": sig,
                   "timestamp": int(time.time() * 1000), "chainId": "8453"}
        hdr = base64.b64encode(json.dumps(payload).encode()).decode()
        return json.dumps({"ok": True, "lib": "ecdsa", "address": addr,
                           "header_valid": hdr, "nonce": nonce,
                           "issuedAt": issued, "expirationTime": exp})
    except Exception as e:
        result["errors"].append(f"ecdsa: {e}")
    return json.dumps(result)


from tools import register as _vf_register
_vf_register('forged_siwx_signer', 'Mint a fresh EVM wallet and build a signed SIWX (Sign-In-With-X) base64 header for api.venice.ai x402 auth — plus an invalid-signature control header', {'type': 'object', 'properties': {}}, 'safe')(run)
