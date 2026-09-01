"""TOOL: tg_osint - Telegram channel/bot probing + history harvesting + code extraction."""
import asyncio, json, os, re, sys, urllib.request, time
from tools import register

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36"}

def _get(url, timeout=25):
    rq = urllib.request.Request(url, headers=UA)
    try:
        return urllib.request.urlopen(rq, timeout=timeout).read().decode(errors="replace")
    except Exception as ex:
        return f"__ERR__ {type(ex).__name__}: {str(ex)[:60]}"

@register(name="tg_probe",
          desc="Probe Telegram handles: live/dead, title, description, member count.",
          params={"type":"object","properties":{
              "handles":{"type":"array","items":{"type":"string"}}},
              "required":["handles"]})
def tg_probe(handles):
    out = []
    for h in handles:
        h = h.lstrip("@")
        body = _get(f"https://t.me/{h}")
        title = re.search(r'og:title" content="([^"]*)"', body)
        desc = re.search(r'og:description" content="([^"]*)"', body)
        members = re.search(r'([\d\s.,K]+)\s*(?:subscribers|members)', body)
        title_v = (title.group(1) if title else "").strip()
        live = bool(title_v) and "Telegram: Contact" not in title_v and len(body) > 6000
        out.append({"handle": h, "live": live, "title": title_v[:70],
                    "desc": (desc.group(1) if desc else "")[:120],
                    "members": members.group(1).strip() if members else ""})
        time.sleep(0.3)
    return json.dumps(out, ensure_ascii=False, indent=1)

@register(name="tg_history_harvest",
          desc="Scrape full public channel history via t.me/s/. Extract messages + optional code patterns (OTP/token regexes).",
          params={"type":"object","properties":{
              "channel":{"type":"string"},
              "pages":{"type":"integer"},
              "code_regex":{"type":"string"}},
              "required":["channel"]})
def tg_history_harvest(channel, pages=10, code_regex=None):
    channel = channel.lstrip("@").split("/s/")[-1]
    # slug : le channel finit dans l'URL t.me ET le nom de fichier rapport
    channel = re.sub(r"[^A-Za-z0-9._-]", "_", channel)
    msgs, ids_, before, dates = [], None, "", []
    for _ in range(int(pages)):
        u = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        h = _get(u)
        if h.startswith("__ERR__"): break
        ids = re.findall(rf'data-post="{channel}/(\d+)"', h)
        if not ids: break
        before = min(int(i) for i in ids) - 1
        times = re.findall(r'<time datetime="([^"]+)"', h)
        dates += times[:len(ids)]
        for m_ in re.findall(r'class="tgme_widget_message_text js-message_text"[^>]*>(.*?)</div>', h, re.S):
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m_)).strip()
            msgs.append(txt)
        time.sleep(0.7)
    result = {"channel": channel, "messages": len(msgs), "msgs_sample": msgs[:25]}
    if code_regex:
        found = set()
        for m in msgs:
            for mm in re.finditer(code_regex, m):
                found.add(mm.group(0))
        result["codes_found"] = sorted(found)[:50]
    _out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(_out_dir, exist_ok=True)
    with open(os.path.join(_out_dir, f"{channel}_history.json"), "w", encoding="utf-8") as f:
        json.dump({"dates": dates, "messages": msgs}, f, indent=1, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False, indent=1)
