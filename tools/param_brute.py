"""TOOL: param_brute - arjun-style hidden parameter discovery via response diffing."""
import json, hashlib, time
import urllib.parse
from tools import register
from tools._transport import fetch as _fetch

UA = {"User-Agent": "Mozilla/5.0"}
COMMON_PARAMS = ["user","username","id","email","token","key","admin","debug","test",
                 "page","limit","offset","sort","order","q","search","query","file",
                 "path","cmd","exec","action","type","category","lang","locale","redirect",
                 "url","next","return","callback","apikey","api_key","access_token",
                 "refresh_token","role","plan","tier","vip","premium","code","promo"]

@register(name="param_brute",
          desc="Discover hidden HTTP parameters by response-diff heuristics (arjun-style). Sends junk param baseline then tests candidates.",
          params={"type":"object","properties":{
              "url":{"type":"string"},
              "method":{"type":"string","enum":["GET","POST"]},
              "extra_params":{"type":"array","items":{"type":"string"}},
              "delay_ms":{"type":"integer"}},
              "required":["url"]})
def param_brute(url, method="GET", extra_params=None, delay_ms=250):
    cands = COMMON_PARAMS + (extra_params or [])
    def send(params):
        if method == "POST":
            data = urllib.parse.urlencode(params).encode()
            r = _fetch(url, method="POST", body=data,
                       headers={"Content-Type": "application/x-www-form-urlencoded"},
                       timeout=15)
        else:
            sep = "&" if "?" in url else "?"
            qs = urllib.parse.urlencode(params)
            r = _fetch(f"{url}{sep}{qs}", timeout=15)
        body = r.get("body") or ""
        return r.get("status", -1), len(body), hashlib.md5(body.encode()).hexdigest()[:10], body[:200]

    # baseline: reflect nothing
    bs, blen, bhash, bprev = send({"__vf_probe__": str(time.time())})

    discovered = []
    tested = 0
    for p in cands:
        st, ln, hsh, prev = send({p: "__vf_value__"})
        tested += 1
        sig = []
        if hsh != bhash and st == bs:
            sig.append("body-diff")
        if st != bs and st != -1:
            sig.append(f"status-diff({st} vs {bs})")
        if ln != blen and abs(ln - blen) > 20:
            sig.append(f"len-diff({ln} vs {blen})")
        if "__vf_value__" in prev:
            sig.append("REFLECTED!")
        if sig:
            discovered.append({"param": p, "signals": sig, "preview": prev[:150]})
        time.sleep(delay_ms / 1000.0)
    return json.dumps({"baseline": {"status": bs, "len": blen},
                       "tested": tested, "discovered": discovered or "none",
                       "note": "REFLECTED params are XSS-candidates; status-diffs may be auth gates"},
                      ensure_ascii=False, indent=1)
