"""VOIDFORGE :: forged tool — web3key_signer
Sign a Venice web3_key challenge token with a freshly minted EVM wallet — returns signer address + signature for the POST body
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(token=None):
    import json
    from eth_account import Account
    from eth_account.messages import encode_defunct
    acct = Account.create()
    addr = acct.address
    token = kwargs.get("token", "")
    sig = acct.sign_message(encode_defunct(text=token)).signature.hex()
    if not sig.startswith('0x'):
        sig = '0x' + sig
    return json.dumps({"ok": True, "signer_address": addr, "signature": sig, "token": token})


from tools import register as _vf_register
_vf_register('forged_web3key_signer', 'Sign a Venice web3_key challenge token with a freshly minted EVM wallet — returns signer address + signature for the POST body', {'properties': {'token': {'type': 'string'}}, 'required': ['token'], 'type': 'object'}, 'safe')(run)
