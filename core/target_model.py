"""VOIDFORGE :: target model — the living grammar of ONE target (Tier G2).

She never SEES the target — she reads JSON. A human senses the machine:
which endpoints exist, what the client BELIEVES the server checks, where
the money/tier decisions live. This module derives that sense from the
artifacts she already produces (js_mine/deobfuscate extractions, api
responses) and keeps a per-target MODEL:

  endpoints   — URL templates with parameter slots and methods
  beliefs     — client-side invariants candidates ("client trusts X for
                pricing") — every one is a zero-day candidate
  assets      — keys, ids, sessions seen (references, not values)

The model is derived (best-effort, evidence-linked) and consumed by:
  - the round-0/round-N prompt (model block)
  - hypothesis_test suggestions (candidate invariants to attack)
  - G3 sweeps (the mutation space comes from the grammar)

Storage: data/learned/target_models/<host>.json (gitignored).
"""
import json
import os
import re
import threading
import time

_LOCK = threading.Lock()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "learned", "target_models")

_ENDPOINT_RX = re.compile(
    r"https?://([a-z0-9.\-]+(/[a-z0-9\-._~%{}$]{1,80}){1,12})", re.I)
_PRICE_RX = re.compile(
    r"(?i)(price[_a-z]*|amount|unit_amount|tier|plan|promo|coupon|"
    r"entitlement|subscription|checkout|billing)")
_SECRET_RX = re.compile(
    r"(?i)(pk_live_|sk_live_|api[_-]?key|client[_-]?secret|service[_-]?role)")


def _path_for(target):
    host = re.sub(r"^https?://", "", str(target or "")).split("/")[0].lower()
    return os.path.join(DIR, (re.sub(r"[^a-z0-9.\-]", "_", host) or "x") + ".json")


def _load(target):
    try:
        with open(_path_for(target), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"endpoints": [], "client_beliefs": [], "assets": [],
                "updated": 0, "target": str(target)}


def _save(target, model):
    try:
        os.makedirs(DIR, exist_ok=True)
        tmp = _path_for(target) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(model, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _path_for(target))
    except Exception:
        pass


def _templatize(url):
    """URL → grammar slot template: concrete ids become {id}/{uuid} slots.
    API version segments (v1, v2...) stay literal — they are grammar, not
    instance data."""
    u = re.sub(r"\?.*$", "", str(url))
    u = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
               "{uuid}", u)
    u = re.sub(r"\b(?:sess|cs|sub|cus|ch|pi|sia)_[A-Za-z0-9]{6,}\b",
               "{ref}", u)
    # numeric id segments — but never /v1 /v2 version prefixes
    u = re.sub(r"(?<!v)\b(\d{2,})\b", r"{id}", u)
    u = re.sub(r"/v\{id\}(/|$)", r"/v1\1", u)   # restore versioned paths
    return u[:160]


def ingest(target, name, out):
    """Feed one tool result into the model. Cheap, best-effort, never
    raises — the model is a lens, not a gate."""
    if not target or not out:
        return
    text = str(out)
    try:
        with _LOCK:
            model = _load(target)
            changed = False
            # endpoints from any URL seen in results
            for host, _ in _ENDPOINT_RX.findall(text[:12000]):
                for m in re.finditer(r"https?://[^\s\"'<>\\)}\]]+", text[:12000]):
                    tpl = _templatize(m.group(0))
                    if tpl not in [e["tpl"] for e in model["endpoints"]]:
                        model["endpoints"].append(
                            {"tpl": tpl, "seen_with": name,
                             "ts": time.time(), "hits": 1})
                        changed = True
                    else:
                        for e in model["endpoints"]:
                            if e["tpl"] == tpl:
                                e["hits"] = int(e.get("hits", 1)) + 1
            # client belief candidates: money/tier logic in JS or payloads
            src = name if (name or "").startswith(("js", "deobf", "forged_js")) \
                else None
            if src:
                for line in text[:20000].splitlines():
                    if _PRICE_RX.search(line) and len(line) < 400:
                        claim = line.strip()
                        if claim not in [b["hint"] for b in model["client_beliefs"]]:
                            model["client_beliefs"].append(
                                {"hint": claim[:380], "source": src,
                                 "ts": time.time()})
                            changed = True
                        if len(model["client_beliefs"]) > 60:
                            model["client_beliefs"] = \
                                model["client_beliefs"][-60:]
            # asset references (never values)
            for m in _SECRET_RX.finditer(text[:12000]):
                kind = m.group(1).lower()
                if kind not in model["assets"]:
                    model["assets"].append(kind)
                    changed = True
            if changed:
                model["updated"] = time.time()
                _save(target, model)
    except Exception:
        pass


def grammar_block(target, limit=14, cap=3000):
    """Compact model block for the prompt: the grammar + the attack-worthy
    client beliefs (invariant candidates)."""
    if not target:
        return ""
    with _LOCK:
        model = _load(target)
    eps = sorted(model.get("endpoints", []),
                 key=lambda e: -e.get("hits", 0))[:limit]
    beliefs = model.get("client_beliefs", [])[-limit:]
    if not eps and not beliefs:
        return ""
    L = [f"═══ TARGET MODEL — {target} (living grammar) ═══",
         "Endpoints (templatized, deduped):"]
    for e in eps:
        L.append(f"- {e['tpl']}  (seen {e.get('hits', 1)}×)")
    if beliefs:
        L.append("Client-code invariants — CANDIDATE ZERO-DAY TARGETS "
                 "(what the CLIENT assumes the server enforces):")
        for b in beliefs:
            L.append(f"- {b['hint']}")
    return "\n".join(L)[:cap]


def candidate_invariants(target, limit=8):
    """Invariant candidates ranked for hypothesis_test — the zero-day
    hunting queue derived from the model."""
    with _LOCK:
        model = _load(target)
    beliefs = model.get("client_beliefs", [])
    ranked = sorted(beliefs, key=lambda b: -b.get("ts", 0))[:limit]
    return [b["hint"] for b in ranked]
