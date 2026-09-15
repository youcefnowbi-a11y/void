"""FOUNDRY (Vague 4) -- repro_harness: the field-truth judge.

The exploit_smith proves a weapon against ONE live target. That is a
point. The repro_harness turns the point into a PATTERN by re-firing the
weapon against SYNTHESIZED variants of the same vulnerability class and
comparing its self-report to the synth's own ground truth (/__oracle).

    weapon claim          oracle truth      judgement
    --------------------------------------------------------
    True                  exploited    ->   TRUE_POSITIVE
    True                  not          ->   FALSE_POSITIVE   (the killer)
    partial               exploited    ->   CONFIRMED_OOB
    partial               not          ->   INCONCLUSIVE
    False                 exploited    ->   MISSED           (blind weapon)
    False                 not          ->   HONEST_FAIL

    generalization_score = fired / tested   (fired = TP + CONFIRMED_OOB)

The verdict, given the real-target proof status:

    real proven    + fired >= 1   ->  GENERAL    (technique, not coincidence)
    real proven    + fired == 0   ->  NOVEL      (the synth library does not
                                                    know this class -- the
                                                    foundry LEARNS the shape)
    real unproven  + fired >= 1   ->  OVERFIT    (synth-only -- too specific
                                                    to be banked as a family)
    real unproven  + fired == 0   ->  FAILED

NOVEL is the jackpot: it means the weapon cracked something our synth
library could not model -- the foundry appends the shape to
data/learned/foundry_novel.json, so the next mission starts with a
target the current one taught the system to build.

SAFETY: this tool spawns LOOPBACK-ONLY synth targets (vuln_synth) and
fires already-tested weapons at them. No remote wire is touched.
"""
import json
import os
import re
import time

from tools import register
from tools._exploit_lib import verdict as _v

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NOVEL = os.path.join(_ROOT, "data", "learned", "foundry_novel.json")


def _load_novel():
    try:
        with open(_NOVEL, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _learn_novel(record):
    """Append-only, atomic-write learning ledger. The next session reads
    it to know which synth classes to enrich first."""
    try:
        os.makedirs(os.path.dirname(_NOVEL), exist_ok=True)
        rows = _load_novel()
        rows.append(record)
        rows = rows[-200:]           # hard cap — the ledger never floods
        tmp = _NOVEL + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _NOVEL)
    except Exception:
        pass


def _weapon_verdict(raw):
    """Normalize whatever the candidate's run() returned into
    {claim: True|False|"partial", summary: str}."""
    if raw is None:
        return {"claim": False, "summary": "empty return"}
    d = raw
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except Exception:
            return {"claim": "partial", "summary": str(raw)[:200]}
    if isinstance(d, dict):
        ex = d.get("exploitable", d.get("ok"))
        if ex is True:
            return {"claim": True, "summary": str(d.get("summary", ""))[:200]}
        if ex is False:
            return {"claim": False, "summary": str(d.get("summary", ""))[:200]}
        if isinstance(ex, str) and ex.lower() == "partial":
            return {"claim": "partial", "summary": str(d.get("summary", ""))[:200]}
        return {"claim": "partial", "summary": str(d)[:200]}
    return {"claim": "partial", "summary": str(d)[:200]}


def _read_oracle(oracle_url, timeout_s=8):
    """The GROUND TRUTH: /__oracle flips only when the synth target
    genuinely exercised the vulnerability. Returns (exploited, evidence)."""
    try:
        from tools._transport import fetch as _f
        r = _f(oracle_url, timeout=timeout_s)
        st = r.get("status", 0)
        body = r.get("body", "")
        if st != 200:
            return None, f"oracle unreachable (status {st})"
        d = json.loads(body)
        return bool(d.get("exploited")), d.get("evidence", [])
    except Exception as ex:
        return None, f"oracle read failed: {type(ex).__name__}: {str(ex)[:120]}"


def _judge(claim, exploited):
    """The 2x2 truth table -- the FP killer."""
    if exploited is None:
        return "ORACLE_DOWN"
    if claim is True:
        return "TRUE_POSITIVE" if exploited else "FALSE_POSITIVE"
    if claim is False:
        return "MISSED" if exploited else "HONEST_FAIL"
    # partial
    return "CONFIRMED_OOB" if exploited else "INCONCLUSIVE"


def _fired(judgement):
    return judgement in ("TRUE_POSITIVE", "CONFIRMED_OOB")


@register(name="repro_harness",
          desc="FOUNDRY (Vague 4): the field-truth judge. Re-fire a banked (or "
               "fresh) weapon against SYNTHESIZED variants of the same vulnerability "
               "class (vuln_synth), compare the weapon's self-report against the "
               "synth's /__oracle ground truth, and return a generalization score. "
               "Verdicts: GENERAL (technique proven -- fires synth and target), "
               "OVERFIT (synth-only -- too specific to bank as a family), NOVEL "
               "(real target fires but our synth library cannot model the class -- "
               "the foundry LEARNS the shape), FAILED, ORACLE_DOWN. Feeds "
               "data/learned/foundry_novel.json on every NOVEL. Call it right after "
               "exploit_smith banks a weapon, or standalone on any bank_id/code.",
          params={"type": "object", "properties": {
              "bank_id": {"type": "string",
                          "description": "weapon id from exploit_bank_list (real "
                                         "target already proven at bank time)"},
              "code": {"type": "string",
                       "description": "OR a raw candidate module (real_proven flag "
                                      "tells the judge its target status)"},
              "vuln_class": {"type": "string",
                             "description": "required with code; inferred from the "
                                            "bank entry when bank_id is used"},
              "variants": {"type": "array",
                           "description": "variants to test (default: the class's "
                                          "supported set, minus none -- base is "
                                          "always included)"},
              "real_proven": {"type": "boolean",
                              "description": "with code only: did the real-target "
                                             "proof pass? (default false)"},
              "stack_match": {"type": "string",
                              "description": "target stack profile, for the novel "
                                             "learning record"},
              "param": {"type": "string",
                        "description": "synth target param (default: class default)"},
              "path": {"type": "string",
                       "description": "synth target path (default: class default)"},
              "timeout_s": {"type": "number",
                            "description": "per-weapon-run wall budget (default 30)"},
          }, "required": []},
          danger="safe")
def repro_harness(bank_id=None, code=None, vuln_class=None, variants=None,
                  real_proven=None, stack_match="", param=None, path=None,
                  timeout_s=30):
    # NOTE: tools.vuln_synth is BOTH a module and a tool name -- `from
    # tools import vuln_synth` binds the MODULE (not callable). Import
    # the decorated function via its full module path.
    from tools.vuln_synth import vuln_synth
    from tools.exploit_test import _load_candidate, _run_with_timeout

    # ── resolve the weapon: bank entry or raw candidate ──
    real = bool(real_proven)
    weapon_id = bank_id or "(raw candidate)"
    if bank_id:
        from core import exploit_bank as bank
        entry = bank.get(bank_id)
        if not entry:
            known = ", ".join(e["id"] for e in bank.list_bank()[:10]) or "none"
            return _v("repro_harness", False,
                      f"unknown bank_id {bank_id!r} -- known: {known}")
        code = entry["code"]
        vuln_class = vuln_class or entry.get("vuln_class", "unknown")
        stack_match = stack_match or entry.get("stack_match", "")
        real = True                   # banked weapons required a target proof
    if not code:
        return _v("repro_harness", False,
                  "need bank_id OR code (+ vuln_class when using code)")
    if not vuln_class:
        return _v("repro_harness", False,
                  "vuln_class required with a raw code candidate")
    cls = str(vuln_class).lower().strip()

    # ── which variants to test ──
    from tools.vuln_synth import _VARIANTS, _DEFAULTS, _BODIES
    if cls not in _BODIES:
        return _v("repro_harness", False,
                  f"no synth library for class {cls!r} -- known: "
                  + ", ".join(_BODIES) + ". This is the honest NOVEL gate: "
                  "the foundry has nothing to model the weapon against.",
                  novel_candidate=True, novel_class=cls,
                  novel_record={"class": cls, "weapon_id": weapon_id,
                                "stack_match": stack_match,
                                "reason": "no synth library for this class"})
    want = variants or _VARIANTS.get(cls, ["base"])
    want = [w for w in want if w in _VARIANTS.get(cls, [])] or ["base"]
    if "base" not in want:
        want = ["base"] + want

    d_param, d_path = _DEFAULTS[cls]
    p = (param or d_param)
    pa = (path or d_path)
    if not pa.startswith("/"):
        pa = "/" + pa

    # ── load the weapon ONCE (isolated, never hot-registered) ──
    try:
        mod, wdir = _load_candidate(code)
    except Exception as ex:
        return _v("repro_harness", False,
                  f"candidate will not compile: {type(ex).__name__}: {str(ex)[:160]}")
    try:
        run = getattr(mod, "run", None)
        if not callable(run):
            return _v("repro_harness", False,
                      "candidate exposes no callable run(url, **kw)")
        per_variant = []
        started = []
        try:
            for var in want:
                # spawn the PREY for this variant
                s = json.loads(vuln_synth(action="start", vuln_class=cls,
                                          variant=var, param=p, path=pa))
                if not s.get("exploitable"):
                    per_variant.append({"variant": var,
                                        "judgement": "SYNTH_DOWN",
                                        "detail": str(s.get("summary", ""))[:120]})
                    continue
                tid = s.get("target_id")
                started.append(tid)
                root = s.get("url", "").rstrip("/")
                oracle = s.get("oracle_url", root + "/__oracle")

                # fire the weapon at the synth root
                args = {"url": root}
                raw, err = _run_with_timeout(run, args,
                                             timeout_s=int(timeout_s or 30))
                if err:
                    claim = {"claim": False, "summary": err[:160]}
                    err_flag = True
                else:
                    claim = _weapon_verdict(raw)
                    err_flag = False

                exploded, ev = _read_oracle(oracle)
                j = _judge(claim["claim"], exploded)
                per_variant.append({
                    "variant": var,
                    "weapon_claim": claim["claim"],
                    "oracle_exploited": exploded,
                    "judgement": j,
                    "weapon_summary": claim["summary"][:140],
                    "oracle_evidence": (ev if isinstance(ev, list) else [str(ev)])[:1],
                    "error": ("timeout/exception" if err_flag else None),
                })
        finally:
            # cleanup: every spawned synth target dies, no exceptions
            for tid in started:
                try:
                    vuln_synth(action="stop", target_id=tid)
                except Exception:
                    pass

        # ── score + classify ──
        tested = [r for r in per_variant
                  if r.get("judgement") not in ("SYNTH_DOWN", "ORACLE_DOWN")]
        fired = sum(1 for r in tested if _fired(r.get("judgement")))
        fp = sum(1 for r in tested if r.get("judgement") == "FALSE_POSITIVE")
        score = round(fired / len(tested), 3) if tested else 0.0

        if real and fired >= 1:
            verdict = "GENERAL"
            exploitable = True
        elif real and fired == 0:
            verdict = "NOVEL"
            exploitable = True     # the weapon still works on the real target
        elif (not real) and fired >= 1:
            verdict = "OVERFIT"
            exploitable = False
        else:
            verdict = "FAILED"
            exploitable = False

        out = {
            "weapon": weapon_id,
            "synth_class": cls,
            "stack_match": stack_match,
            "variants_tested": len(tested),
            "variants_fired": fired,
            "false_positives": fp,
            "generalization_score": score,
            "verdict": verdict,
            "per_variant": per_variant,
        }
        if verdict == "NOVEL":
            rec = {"class": cls, "weapon_id": weapon_id,
                   "stack_match": stack_match,
                   "evidence": [r.get("weapon_summary") for r in per_variant][:2],
                   "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
            _learn_novel(rec)
            out["novel_record"] = rec
            out["summary"] = (f"NOVEL -- real target fired, but the synth library "
                              f"could not model {cls}: the foundry learned the shape. "
                              f"score {score} on {len(tested)} variants.")
        elif verdict == "GENERAL":
            out["summary"] = (f"GENERAL -- technique proven: {fired}/{len(tested)} "
                              f"variants cracked on the synth AND the real target. "
                              f"score {score}."
                              + (f" ({fp} false positive(s) -- watch the oracle.)"
                                 if fp else ""))
        elif verdict == "OVERFIT":
            out["summary"] = (f"OVERFIT -- fires on the synth ({fired}/{len(tested)}) "
                              f"but the real target was never proven -- too specific "
                              f"to bank as a family. score {score}.")
        else:
            out["summary"] = (f"FAILED -- neither the synth nor the real proof "
                              f"fired. score {score} on {len(tested)} variants.")
        out["iterate_hint"] = (
            "The per_variant table is the spec: which shapes did the weapon miss? "
            "Filtered variants missing -> add a bypass; blind variants missing -> "
            "you need an oracle(); POST variants missing -> the wire shape must "
            "change. Fix the code and re-fire exploit_smith on the real target, "
            "then re-run repro_harness to recompute the score.")
        out["tool"] = "repro_harness"
        out["exploitable"] = exploitable
        return _v("repro_harness", exploitable, out["summary"],
                  verdict=verdict, weapon=weapon_id, synth_class=cls,
                  generalization_score=score, variants_tested=len(tested),
                  variants_fired=fired, false_positives=fp,
                  per_variant=per_variant,
                  novel_record=out.get("novel_record"),
                  iterate_hint=out["iterate_hint"])
    finally:
        try:
            import shutil
            shutil.rmtree(wdir, ignore_errors=True)
        except Exception:
            pass