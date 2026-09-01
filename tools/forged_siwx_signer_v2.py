"""VOIDFORGE :: forged tool — siwx_signer_v2
Mint EVM wallet + SIWX headers per Venice docs exact format: valid, invalid-sig control, cross-wallet control
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(**kwargs):
    import json, base64, time, secrets
    from eth_account import Account
    from eth_account.messages import encode_defunct
    acct = Account.create()
    addr = acct.address
    nonce = secrets.token_hex(8)
    issued = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    exp = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(time.time() + 600))
    msg = (f"api.venice.ai wants you to sign in with your Ethereum account:\n{addr}\n\n"
           f"Sign in to Venice API\n\nURI: https://api.venice.ai\nVersion: 1\nChain ID: 8453\n"
           f"Nonce: {nonce}\nIssued At: {issued}\nExpiration Time: {exp}")
    sig = acct.sign_message(encode_defunct(text=msg)).signature.hex()
    if not sig.startswith('0x'):
        sig = '0x' + sig
    payload = {"address": addr, "message": msg, "signature": sig,
               "timestamp": int(time.time() * 1000), "chainId": 8453}
    hdr = base64.b64encode(json.dumps(payload).encode()).decode()
    bad = dict(payload); bad["signature"] = "0x" + "00" * 65
    bad_hdr = base64.b64encode(json.dumps(bad).encode()).decode()
    # cross-wallet control: valid sig from acct, but claims a DIFFERENT address
    other = "0x" + "11" * 20
    xw = dict(payload); xw["address"] = other
    xw_hdr = base64.b64encode(json.dumps(xw).encode()).decode()
    return json.dumps({"ok": True, "address": addr, "nonce": nonce,
                       "header_valid": hdr, "header_invalid_sig": bad_hdr,
                       "header_cross_wallet": xw_hdr,
                       "issuedAt": issued, "expirationTime": exp})


from tools import register as _vf_register
_vf_register('forged_siwx_signer_v2', 'Mint EVM wallet + SIWX headers per Venice docs exact format: valid, invalid-sig control, cross-wallet control', {'properties': {}, 'type': 'object'}, 'safe')(run)
