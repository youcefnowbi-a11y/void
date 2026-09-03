"""VOIDFORGE :: hypothesis_test — the falsifiable experiment engine (Tier G1).

The mission-76 lesson, generalized: an LLM pentester READS results and
forms impressions; a researcher DESIGNES experiments. Every real bug hunt
is: state an invariant the target should hold → break exactly one variable
→ measure the differential → conclude CONFIRMED / REFUTED / INCONCLUSIVE.

This tool makes the hypothesis a first-class object:
  hypothesis (natural language, ends in the report either way)
  baseline   (the request that respects the invariant)
  mutation   (ONE variable changed — header, body param, URL segment)
  oracle     (what a violated invariant looks like: status, body marker,
              json path value, or 'differs' — plus the direction: the
              hypothesis can claim the guard EXISTS (held) or is MISSING
              (violated))

Verdict contract (verdict-backed, feeds findings + belief memory G4):
  CONFIRMED   — the oracle fired: the invariant is what the hypothesis says
                (a VIOLATED direction + confirmed = the finding; a HELD
                direction + confirmed = a proven defense, dossier §1)
  REFUTED     — the oracle did not fire on a valid differential
  INCONCLUSIVE — no differential could be established (both failed,
                identical failures, network death)

One HTTP pair per call, everything through the transport layer (ROE,
posture, identity, cache, proxy) — same laws as data_extract.
"""
import copy
import json

from . import register
from ._transport import fetch

_MAX = 260          # cap any echoed request material in the verdict card
_DEPTH = 6          # max JSON depth walked by the differential


def _dig(obj, path):
    """Dot path walker (a.b.0.c) — None when absent."""
    cur = obj
    for part in (path or "").split(".") if path else []:
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _norm_headers(h):
    return {k.lower(): str(v) for k, v in (h or {}).items()
            if k.lower() not in ("content-length", "host")}


def _json_body(resp):
    b = resp.get("body")
    if isinstance(b, (dict, list)):
        return b
    try:
        return json.loads(b)
    except Exception:
        return None


def _diff(a, b, depth=0, path=""):
    """Structural differential of two JSON trees — list of (path, a, b)."""
    out = []
    if depth > _DEPTH:
        return out
    if type(a) is not type(b):
        out.append((path or "root", a, b))
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append((f"{path}.{k}" if path else k,
                            a.get(k), b.get(k)))
            else:
                out += _diff(a[k], b[k], depth + 1,
                             f"{path}.{k}" if path else k)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((f"{path}[]" if path else "[]",
                        f"len={len(a)}", f"len={len(b)}"))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += _diff(x, y, depth + 1,
                             f"{path}[{i}]" if path else f"[{i}]")
    elif a != b:
        out.append((path or "root", a, b))
    return out


def _apply_mutation(spec, req):
    """ONE variable changed on a DEEP COPY — never touch the baseline."""
    out = copy.deepcopy(req)
    kind = (spec or {}).get("type", "body_param")
    if kind == "header":
        out.setdefault("headers", {})
        key = spec.get("path") or spec.get("name") or ""
        if spec.get("value") is None:
            out["headers"].pop(key, None)
        else:
            out["headers"][key] = spec.get("value")
    elif kind == "url":
        seg = spec.get("path") or ""
        base_url = str(req.get("url", ""))
        if "{" + seg + "}" in base_url:
            out["url"] = base_url.replace("{" + seg + "}", str(spec.get("value")))
        else:
            # A3 (self-audit): no template slot — replacing the WHOLE url is
            # not a one-variable mutation, it is a different experiment.
            # Honest refusal, not a silent overwrite.
            out["_mutation_refused"] = (
                f"url mutation needs a {{{seg}}} slot in baseline.url "
                f"— use body_param/header or re-issue with a templated url")
    elif kind == "raw_body":
        out["body"] = spec.get("value")
    else:  # body_param / json_path — one leaf of the JSON body
        path = spec.get("path") or spec.get("name") or ""
        b = out.get("body")
        if isinstance(b, dict) and path:
            cur = b
            parts = path.split(".")
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            if spec.get("value") is None:
                cur.pop(parts[-1], None)
            else:
                cur[parts[-1]] = spec.get("value")
        elif path and isinstance(b, str) and spec.get("value") is not None:
            out["body"] = spec.get("value")
    return out


def _check_oracle(oracle, mutated_resp):
    """Does the MUTATED response satisfy the violation signature?"""
    o = oracle or {}
    want_status = o.get("expect_status")
    if want_status and int(want_status) != int(mutated_resp.get("status") or 0):
        return False, f"status {mutated_resp.get('status')} != {want_status}"
    marker = o.get("expect_contains")
    body = str(mutated_resp.get("body") or "")
    if marker and marker not in body:
        return False, f"marker {marker[:40]!r} absent"
    jp = o.get("expect_json_path")
    if jp:
        want = o.get("expect_value")
        got = _dig(_json_body(mutated_resp) or {}, jp)
        if want is not None and str(got) != str(want):
            return False, f"json {jp} = {got!r} != {want!r}"
        if want is None and got is None:
            return False, f"json path {jp} absent"
    if not (want_status or marker or jp):
        # bare oracle = 'the response differs materially from baseline'
        return None, "no explicit signature — see differential"
    return True, "oracle satisfied"


def _one_request(req, timeout=30):
    return fetch(str(req.get("url", "")),
                 method=(req.get("method") or "GET").upper(),
                 headers=req.get("headers"),
                 body=req.get("body"),
                 timeout=timeout,
                 use_cache=False)  # experiments are never cached


@register(
    "hypothesis_test",
    "THE SCIENCE ENGINE: state an invariant hypothesis in natural language, "
    "give the baseline request + ONE mutation (a single changed variable) + "
    "the oracle that recognizes the violation, and this tool runs the "
    "controlled differential experiment and returns a falsifiable verdict "
    "(CONFIRMED / REFUTED / INCONCLUSIVE) with the full response "
    "differential. direction='violated' tests that a guard is MISSING "
    "(oracle fired on mutant = finding); direction='held' tests that a "
    "defense HOLDS (oracle silent on mutant = proven defense for the "
    "dossier). Impact-first hunting starts HERE — not at scanners.",
    {
        "type": "object",
        "properties": {
            "hypothesis": {"type": "string",
                           "description": "the invariant claim, natural "
                                          "language, ends in the report "
                                          "either way"},
            "baseline": {"type": "object",
                         "description": "{url, method, headers, body} — the "
                                        "request that RESPECTS the invariant"},
            "mutation": {"type": "object",
                         "description": "ONE changed variable: "
                                        "{type: header|body_param|url|raw_body,"
                                        " path, value}"},
            "oracle": {"type": "object",
                       "description": "violation signature on the MUTATED "
                                      "response: {expect_status, "
                                      "expect_contains, expect_json_path, "
                                      "expect_value}"},
            "direction": {"type": "string",
                          "description": "'violated' (guard missing — oracle "
                                         "firing CONFIRMS the hypothesis) or "
                                         "'held' (defense holds — oracle "
                                         "silent CONFIRMS)"},
        },
        "required": ["hypothesis", "baseline", "mutation"],
    },
    danger="network",
)
def run(hypothesis, baseline, mutation, oracle=None, direction="violated"):
    if not hypothesis or not isinstance(baseline, dict) or not baseline.get("url"):
        return {"ok": False,
                "error": "hypothesis + baseline.url are mandatory"}
    direction = "held" if str(direction).lower() == "held" else "violated"

    try:
        base_resp = _one_request(baseline)
    except Exception as ex:
        return {"ok": False, "error": f"baseline request died: {type(ex).__name__}: "
                                       f"{str(ex)[:120]}"}
    b_status = int(base_resp.get("status") or 0)
    if b_status == 0:
        return {"ok": False,
                "error": f"baseline unreachable ({str(base_resp.get('body'))[:120]})",
                "stage": "baseline"}

    mutant = _apply_mutation(mutation, baseline)
    if mutant.get("_mutation_refused"):
        return {"ok": False,
                "error": mutant["_mutation_refused"],
                "hint": "a mutation changes ONE variable — template the "
                        "baseline url with slots ({id}, {plan}...) first"}
    try:
        mut_resp = _one_request(mutant)
    except Exception as ex:
        return {"ok": False, "error": f"mutated request died: {type(ex).__name__}: "
                                       f"{str(ex)[:120]}", "stage": "mutation"}
    m_status = int(mut_resp.get("status") or 0)

    # ── differential ──
    diffs = []
    if b_status != m_status:
        diffs.append(("status", b_status, m_status))
    bj, mj = _json_body(base_resp), _json_body(mut_resp)
    if bj is not None and mj is not None:
        diffs += _diff(bj, mj)
    elif str(base_resp.get("body")) != str(mut_resp.get("body")):
        diffs.append(("body", "<baseline body>",
                      f"len={len(str(mut_resp.get('body')))}"))
    bh, mh = _norm_headers(base_resp.get("headers")), \
        _norm_headers(mut_resp.get("headers"))
    for k in sorted((set(bh) | set(mh)) - {"date", "set-cookie"}):
        if bh.get(k) != mh.get(k):
            diffs.append((f"header.{k}", bh.get(k), mh.get(k)))

    fired, why = _check_oracle(oracle, mut_resp)

    # ── verdict ──
    if m_status == 0:
        verdict = "INCONCLUSIVE"
        reason = "mutated request never landed — network death, not a verdict"
    elif fired is None and not (oracle or {}).get(
            "expect_status") and not (oracle or {}).get(
            "expect_contains") and not (oracle or {}).get("expect_json_path"):
        # A4 (self-audit): NO oracle signature was specified — the tool must
        # not invent a verdict from silence. The differential is the report;
        # the verdict is the researcher's next call.
        verdict = "INCONCLUSIVE"
        reason = "no oracle signature given — differential reported, " \
                 "verdict reserved (an oracle-less test is a look, not " \
                 "an experiment)"
    elif not diffs:
        verdict = "INCONCLUSIVE"
        reason = "no differential at all — responses identical (or both " \
                 "failed the same way); the experiment discriminates nothing"
    elif direction == "violated":
        verdict = "CONFIRMED" if fired else "REFUTED"
        reason = why if fired else \
            "oracle silent on the mutant — the invariant held (guard exists)"
    else:  # held
        verdict = "CONFIRMED" if (fired is False or fired is None) else "REFUTED"
        reason = "oracle silent on the mutant — the defense HOLDS under " \
                 "mutation (dossier §1 material)" \
                 if verdict == "CONFIRMED" else why

    exploitable = True if verdict == "CONFIRMED" and direction == "violated" \
        else (False if verdict == "CONFIRMED" and direction == "held" else None)
    summary = (f"{verdict}: {hypothesis[:140]}" +
               (f" — {reason}" if reason else ""))

    card = {
        "tool": "hypothesis_test",
        "exploitable": exploitable,
        "summary": summary,
        "hypothesis": hypothesis[:400],
        "direction": direction,
        "verdict": verdict,
        "reason": reason[:300],
        "baseline_status": b_status,
        "mutant_status": m_status,
        "differential": [
            {"path": str(p)[:80],
             "baseline": str(a)[:_MAX],
             "mutant": str(b)[:_MAX]}
            for p, a, b in diffs[:20]
        ],
        "mutated_variable": {
            "what": (mutation or {}).get("path")
                    or (mutation or {}).get("name") or "",
            "type": (mutation or {}).get("type", "body_param"),
            "to": str((mutation or {}).get("value"))[:120],
        },
        "hint": ("evidence_pack (seal the differential proof)" if
                 verdict == "CONFIRMED" and direction == "violated" else
                 "re-test with a different mutation before writing the wall off"),
    }
    # ── G4 hook: every verdict is a tested belief — the science ledger
    # grows on its own; confidence revises on re-tests of the same claim.
    # A8 (self-audit): host "unknown" would collect every host-less test
    # into ONE polluted bucket — an empty netloc means NO ledger write.
    try:
        import urllib.parse as _up
        from core.beliefs import record as _brec
        _host = _up.urlsplit(str(baseline.get("url", ""))).hostname \
            or _up.urlsplit(str(baseline.get("url", ""))).netloc
        if _host:
            _brec(_host, hypothesis, verdict, direction=direction,
                  evidence=str(diffs[:3])[:400] or reason[:200],
                  source_tool="hypothesis_test")
    except Exception:
        pass
    return json.dumps(card, ensure_ascii=False, default=str)
