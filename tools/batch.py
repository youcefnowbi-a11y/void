"""TOOL: batch_execute - run independent tools concurrently.

The agent declares a batch of independent calls; they run in a thread pool
(per-host pacing still applies inside _shared/_transport). Cuts wall-clock
for fan-out recon from N×latency to ~latency.
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import tools as _reg
from tools import register


@register(name="batch_execute",
          desc="Run up to 5 independent tool calls CONCURRENTLY: calls=[{tool, args}, ...]. Use for fan-out recon (same tool on many hosts, or different tools on one host). Results come back keyed by index.",
          params={"type": "object", "properties": {
              "calls": {"type": "array", "items": {"type": "object", "properties": {
                  "tool": {"type": "string"}, "args": {"type": "object"}},
                  "required": ["tool"]}}},
              "required": ["calls"]})
def batch_execute(calls):
    if not isinstance(calls, list):
        return json.dumps({"error": "calls must be a list of {tool, args} objects"})
    calls = calls[:5]
    # Validate each call — LLM sometimes produces truncated JSON
    valid_calls = []
    skipped = []
    for i, c in enumerate(calls):
        if not isinstance(c, dict):
            skipped.append({"index": i, "reason": "not a dict"})
            continue
        tool_name = c.get("tool") or c.get("name") or ""
        if not tool_name or not isinstance(tool_name, str):
            skipped.append({"index": i, "reason": "missing or invalid tool name"})
            continue
        args = c.get("args")
        if args is not None and not isinstance(args, dict):
            # Try to parse if it's a string
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    skipped.append({"index": i, "tool": tool_name,
                                    "reason": "args is not valid JSON"})
                    continue
            else:
                args = {}
        valid_calls.append((i, tool_name, args or {}))

    results = [None] * len(calls)
    for s in skipped:
        idx = s.get("index", 0)
        if idx < len(results):
            results[idx] = {"tool": s.get("tool", "?"), "ok": False,
                            "result": "SKIPPED: " + s.get("reason", "malformed call")}

    # forward the mission's event stream so INNER tools are visible everywhere
    # (R3-24: thread-local du thread d'origine d'abord — le global n'est plus
    # écrit par execute(); le fallback reste pour la compat process mixte)
    inner_event = (getattr(getattr(_reg, "_thread_state", None), "current_event", None)
                   or getattr(_reg, "_CURRENT_EVENT", None))
    # A2 : périmètre de l'agent appelant (plan-mode, rôle swarm) — les appels
    # internes ne peuvent pas frapper hors arsenal. Hérité aussi par les
    # workers pour que le NESTING (batch dans batch) capture le même set.
    _allowed = _reg.current_allowed()

    def run(i, name, args):
        if _allowed is not None and name not in _allowed:
            return i, {"tool": name, "ok": False,
                       "result": "SKIPPED: '" + name + "' hors arsenal autorisé de "
                                 "l'agent appelant (plan-mode / rôle swarm)."}
        _prev = _reg.current_allowed()
        _reg.allowed.names = _allowed
        try:
            # through reg.execute: healer + UNKNOWN_TOOL self-correction included
            res = _reg.execute(name, args or {}, on_event=inner_event)
        finally:
            _reg.allowed.names = _prev
        return i, {"tool": name, "ok": not str(res).startswith("TOOL ERROR"),
                   "result": str(res)[:4000]}

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(run, i, name, args)
                   for i, name, args in valid_calls]
        for f in as_completed(futures):
            try:
                i, r = f.result()
                results[i] = r
            except Exception as exc:
                for idx in range(len(results)):
                    if results[idx] is None:
                        results[idx] = {"tool": "?", "ok": False,
                                       "result": "EXCEPTION: {}: {}".format(
                                           type(exc).__name__, str(exc)[:200])}
                        break

    # Fill any remaining None slots
    for idx in range(len(results)):
        if results[idx] is None:
            results[idx] = {"tool": "?", "ok": False, "result": "SKIPPED: no result"}

    out = {"executed": len(valid_calls), "results": results}
    if skipped:
        out["skipped"] = skipped
    s = json.dumps(out, ensure_ascii=False, indent=1)
    if len(s) > 22000:
        # WC4 (audit-2 C4): flat 6000c per sub-result × 5 calls overflowed
        # the 22000 final cap — the LAST results were amputated mid-JSON
        # and silently lost. Re-serialize with an EVEN per-result budget
        # that provably fits: floor((22000 - overhead) / n_results).
        n = max(1, len(results))
        per = max(1200, (20000 - 400) // n)
        for r in results:
            if isinstance(r, dict) and len(str(r.get("result") or "")) > per:
                r["result"] = str(r.get("result"))[:per] + \
                    "…[elided — full result archived in extractions/]"
        out["results"] = results
        s = json.dumps(out, ensure_ascii=False, indent=1)
    return s[:22000]
