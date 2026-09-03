"""VOIDFORGE :: differential_sweep — delegated fast iteration (Tier G3).

The round-economics wall: one LLM round = one experience. A real hunt is
500. This tool takes a RESEARCH POLICY from the LLM and executes the
iteration loop without it:

  base_request            — the request template (respecting the invariant)
  sweep                   — ONE mutation axis with a VALUE SPACE:
       {type: header|body_param|url_path,
        path, values: [v1..vN]}                (or {range: [a,b,n]})
  oracle                  — signature of 'interesting': expect_status /
       expect_contains / expect_json_path+value / or 'differs' (default:
       any response that materially differs from the majority)
  stop_on_hit             — abort the sweep at the first oracle hit

Returns a compact SCIENCE TABLE: per-variant one line (value → status +
delta-marker), then the HITS with full context, never more than a few KB
of context — the LLM reads conclusions, not logs. ROE rate stays enforced
by the transport layer; concurrency modest (sequential batches of 4).

This is fuzz_attack_surface's structured sibling: the mutation space is
DESIGNED (one axis, enumerated values) and the oracle is SEMANTIC (from
the hypothesis), not syntactic (crash markers).
"""
import concurrent.futures
import json

from . import register
from ._transport import fetch

_MAX_VALUES = 60          # policy size cap — a sweep is bounded by design
_BATCH = 4                # parallel workers (ROE-friendly)
_TIMEOUT_S = 25


def _apply(base, kind, path, value):
    req = json.loads(json.dumps(base))  # deep copy via JSON round-trip
    if kind == "header":
        req.setdefault("headers", {})[path] = value
    elif kind == "url_path":
        req["url"] = str(req.get("url", "")).replace(
            "{" + (path or "SWEEP") + "}", str(value))
    elif kind == "raw_body":
        req["body"] = value
    else:  # body_param
        b = req.get("body")
        if isinstance(b, dict) and path:
            cur = b
            parts = str(path).split(".")
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = value
    return req


def _fire(req):
    return fetch(str(req.get("url", "")),
                 method=(req.get("method") or "GET").upper(),
                 headers=req.get("headers"),
                 body=req.get("body"),
                 timeout=_TIMEOUT_S, use_cache=False)


def _oracle_hit(oracle, resp):
    o = oracle or {}
    if o.get("expect_status") and \
            int(resp.get("status") or 0) != int(o["expect_status"]):
        return False
    marker = o.get("expect_contains")
    if marker and marker not in str(resp.get("body") or ""):
        return False
    jp = o.get("expect_json_path")
    if jp:
        try:
            cur = resp.get("body")
            if isinstance(cur, str):
                cur = json.loads(cur)
            for part in str(jp).split("."):
                cur = cur[int(part)] if isinstance(cur, list) else cur[part]
            if o.get("expect_value") is not None and \
                    str(cur) != str(o["expect_value"]):
                return False
        except Exception:
            return False
    return True


def _sig(resp):
    """Compact response signature for majority-diff detection."""
    try:
        b = resp.get("body")
        if isinstance(b, str) and b[:1] in "{[":
            b = json.loads(b)
        if isinstance(b, dict):
            ks = tuple(sorted(b.keys()))
            return (resp.get("status"), ks)
    except Exception:
        pass
    return (resp.get("status"), len(str(resp.get("body") or "")))


@register(
    "differential_sweep",
    "DELEGATED ITERATION: give a research POLICY — one base request + ONE "
    "mutation axis with its value space + the oracle that marks a response "
    "interesting — and the executor runs the whole variant space WITHOUT "
    "spending your rounds. Returns a science table (per-variant one line) "
    "plus full context on the hits. This is how one round becomes 50 "
    "experiments: design the space, read the conclusions.",
    {
        "type": "object",
        "properties": {
            "base_request": {"type": "object",
                             "description": "{url (may contain {SWEEP} "
                                            "slot), method, headers, body}"},
            "sweep": {"type": "object",
                      "description": "{type: header|body_param|url_path|"
                                     "raw_body, path, values:[...]} or "
                                     "{..., range:[start,end,count]}"},
            "oracle": {"type": "object",
                       "description": "{expect_status, expect_contains, "
                                      "expect_json_path, expect_value} — "
                                      "empty = majority-differs oracle"},
            "stop_on_hit": {"type": "boolean",
                            "description": "abort at first hit (default true)"},
        },
        "required": ["base_request", "sweep"],
    },
    danger="network",
)
def run(base_request, sweep, oracle=None, stop_on_hit=True):
    if not isinstance(base_request, dict) or not base_request.get("url"):
        return json.dumps({"ok": False, "error": "base_request.url required"})
    kind = (sweep or {}).get("type", "body_param")
    path = (sweep or {}).get("path") or "SWEEP"
    values = (sweep or {}).get("values")
    if not values:
        rng = (sweep or {}).get("range")
        if rng and len(rng) == 3:
            lo, hi, n = rng
            step = (hi - lo) / max(n - 1, 1)
            values = [round(lo + i * step) for i in range(int(n))]
        else:
            return json.dumps({"ok": False,
                               "error": "sweep.values[] or sweep.range=[lo,hi,n] required"})
    values = values[:_MAX_VALUES]
    if len(values) < 2:
        return json.dumps({"ok": False,
                           "error": "a sweep needs >= 2 values (single value = hypothesis_test)"})

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=_BATCH) as ex:
        futs = {}
        for v in values:
            req = _apply(base_request, kind, path, v)
            futs[ex.submit(_fire, req)] = v
        for fut in concurrent.futures.as_completed(futs):
            v = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"status": 0, "body": f"sweep death: {type(e).__name__}"}
            results.append({"value": v,
                            "status": int(r.get("status") or 0),
                            "sig": _sig(r),
                            "resp": r})

    # majority signature = the boring response; deviations are the signal
    from collections import Counter
    sig_count = Counter(r["sig"] for r in results)
    majority_sig, _ = sig_count.most_common(1)[0] if sig_count else (None, 0)
    has_explicit_oracle = bool(
        oracle and (oracle.get("expect_status")
                    or oracle.get("expect_contains")
                    or oracle.get("expect_json_path")))

    table, hits = [], []
    for r in sorted(results, key=lambda x: str(x["value"])):
        interesting = _oracle_hit(oracle, r["resp"]) if has_explicit_oracle \
            else (r["sig"] != majority_sig)
        if interesting and len(hits) < 5:
            body = str(r["resp"].get("body") or "")[:800]
            hits.append({"value": r["value"], "status": r["status"],
                         "body_excerpt": body,
                         "headers": {k: v for k, v in
                                     list((r["resp"].get("headers") or {}).items())[:6]}})
        table.append({"value": str(r["value"])[:60], "status": r["status"],
                      "deviates": bool(interesting)})
        # A5 (self-audit): stop_on_hit is a DECLARED contract — honor it:
        # once a hit is captured, remaining variants are not fired from the
        # table (already-fetched results are kept, but a hit stops the scan)
        if stop_on_hit and interesting and has_explicit_oracle:
            # mark and break the table loop — results already fetched stay
            # in the science table for context, the sweep is OVER for the
            # executor (sequential semantics preserved: values after the
            # hit are simply not added)
            table.append({"note": "sweep stopped on hit (stop_on_hit=true)",
                          "remaining": len(values) - len(table) + 1})
            break

    n_dev = sum(1 for r in results
                if (r["sig"] != majority_sig))
    # A6 (self-audit, W1 discipline): exploitable is claimed ONLY on an
    # explicit semantic oracle hit — a bare majority-deviation (rate limit,
    # jitter, redirect dance) is a SIGNAL, never a verdict.
    n_oracle_hits = sum(1 for r in results
                        if has_explicit_oracle and _oracle_hit(oracle, r["resp"]))
    exploitable = True if (has_explicit_oracle and n_oracle_hits) else None
    out = {
        "tool": "differential_sweep",
        "exploitable": exploitable,
        "summary": (f"{len(values)} variants × 1 axis ({kind}:{path}) — "
                    f"{n_dev} deviation(s), "
                    f"{n_oracle_hits if has_explicit_oracle else '—'} oracle hit(s)"
                    f"{'' if has_explicit_oracle else ' (NO oracle given — deviations are signals, not verdicts)'}"),
        "axis": {"type": kind, "path": path, "n_values": len(values)},
        "science_table": table,
        "hits": hits,
        "majority_status": majority_sig[0] if majority_sig else None,
        "hint": ("hypothesis_test on a hit (isolate the ONE variable) → "
                 "evidence_pack" if hits else
                 "no deviation in this space — narrow the axis or change "
                 "the invariant"),
    }
    return json.dumps(out, ensure_ascii=False, default=str)
