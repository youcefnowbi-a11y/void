# -*- coding: utf-8 -*-
"""
GRIMOIRE QUERY — the war library at her fingertips.

Feeds the GRIMOIRE knowledge base (53 techniques + 709-record ATT&CK
spine + 1695 CISA KEV entries + 288 Atomic Red Team tests) into the
fleet as a QUERYABLE tool. No full-dump ever — the 3.6MB feed stays
on disk; the LLM sees only compact, decision-ready slices.

Doctrine (LO's integration law, 2026-09-06):
- kev          → the nday lane: what is ACTIVELY exploited in the wild
                 right now for a given product/vendor — massively better
                 signal than NVD spraying (1695 reality-filtered CVEs).
- technique    → technique selection: blast/reliability/difficulty +
                 the detection pair (every move ships with its counter).
- spine        → ATT&CK technique knowledge (tactics, platforms) for
                 mapping a target's surface.
- atomic       → the exact tested command for a technique (with cleanup).
- catalog      → where to fetch deeper material (wordlists, PoCs).

CONSCIENCE (the loader's law, inherited here):
- requires_confirmation=true techniques are GATED: the tool tells her
  the gate and what confirmation means — she never fires them blind.
- spine records are KNOWLEDGE-TIER: execution-ineligible until an
  operator promotes them; this tool surfaces their info, never their
  execution.
"""
import json
import os
import re

from tools import register

_FEED_PATHS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "grimoire.feed.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "grimoire.feed.json"),
    os.path.expanduser(os.path.join("~", "Desktop", "grimoire",
                                    "grimoire.feed.json")),
]

_feed_cache = None


def _load_feed():
    global _feed_cache
    if _feed_cache is not None:
        return _feed_cache
    for p in _FEED_PATHS:
        try:
            with open(p, "r", encoding="utf-8") as f:
                _feed_cache = json.load(f)
                return _feed_cache
        except Exception:
            continue
    _feed_cache = {}
    return _feed_cache


def _fmt_technique(t, verbose=False):
    det = t.get("detection")
    if not isinstance(det, dict):
        det = {}          # DIFF-domain records carry detection as a plain
                          # string (RECON-SIGNAL: ... | ROOT-CAUSE: ...) —
                          # CP1 live bug: .get() on a str crashed verbose
                          # mode. The string surfaces via summary/verbose below.
    det_desc = det.get("description") or ""
    if not det_desc and isinstance(t.get("detection"), str):
        det_desc = t["detection"]
    lines = [
        f"{t['id']} — {t['name']}",
        f"  domain={t.get('_domain')} klass={t.get('klass')}",
        f"  difficulty={t.get('difficulty')} reliability={t.get('reliability')}",
        f"  blast_radius={t.get('blast_radius')} reversibility={t.get('reversibility')}",
        f"  requires_confirmation={'YES — operator-gated move' if t.get('requires_confirmation') else 'no'}",
        f"  mitre={','.join(t.get('mitre') or []) or '-'} capec={','.join(t.get('capec') or []) or '-'}",
    ]
    if verbose:
        lines.append(f"  summary: {(t.get('summary') or '')[:400]}")
        lines.append(f"  detection: {det_desc[:300]}")
        mits = det.get("mitigations") or []
        if mits:
            lines.append(f"  mitigations: {' | '.join(m[:90] for m in mits[:3])}")
        refs = t.get("references") or []
        if refs:
            lines.append(f"  refs: {refs[0]}")
    return "\n".join(lines)


def _fmt_kev(v):
    rw = v.get("knownRansomwareCampaignUse", "Unknown")
    return (f"{v['cveID']} [{rw}] {v['vendorProject']} {v['product']}: "
            f"{(v.get('vulnerabilityName') or '')[:80]} "
            f"(added {v.get('dateAdded', '?')}) — {(v.get('shortDescription') or '')[:220]}")


def _fmt_spine(r):
    return (f"{r['id']} :: {r['name']}\n"
            f"  tactics={','.join(r.get('tactics') or [])} "
            f"platforms={','.join((r.get('platforms') or [])[:5])}\n"
            f"  status={r.get('conscience_status')} (knowledge-tier: not execution-eligible)\n"
            f"  source={r.get('source_url', '')}\n"
            f"  {(r.get('description') or '')[:280]}")


def _fmt_atomic(a):
    return (f"{a['technique']} :: {a['test_name']} [{a.get('executor')}]"
            + (f" (elev req)" if a.get("elevation_required") else "")
            + f"\n  command: {(a.get('command') or '')[:400]}"
            + (f"\n  cleanup: {(a.get('cleanup') or 'none')[:200]}" if a.get("cleanup") else ""))


def _register(name, desc, params):
    return register(name, desc, params)


@_register(
    "grimoire_query",
    "War library oracle. Queries the GRIMOIRE knowledge base (141 offense techniques with detection pairs — "
    "incl. the DIFF domain: 84 interpretation-differential techniques 2024-2026, from TE.0 smuggling to "
    "AI-agent poisoning, each carrying its recon-signal trigger, "
    "709 ATT&CK spine records, 1695 CISA KEV actively-exploited CVEs, 288 tested Atomic Red Team commands, "
    "31 tool catalogs). Modes: "
    "'kev' — given a product/vendor keyword (e.g. 'nginx', 'wordpress', 'chrome'), list the CVEs KNOWN to be "
    "exploited in the wild right now: this is the nday lane — a KEV hit on the target's stack is a "
    "reality-tested strike, infinitely better signal than NVD possibility-spraying. "
    "'technique' — offense technique selection: filter by domain (cloud/identity/webapp/injection/privesc/"
    "evasion/network/exploitation/wireless/social/telegram/diff), klass, max_blast, max_difficulty; every "
    "technique ships with its detection pair + mitigations (the counter). The DIFF domain is the 2024-26 "
    "era library: hunt DISAGREEMENT SURFACES between components (parser vs parser, cache vs origin, "
    "human-visible vs model-visible) — scanners test what a request does, you test what two components "
    "disagree about. Techniques with requires_confirmation=true are "
    "operator-gated — the tool names the gate, never fires the move. "
    "'spine' — ATT&CK knowledge lookup by technique id (T1558.003 etc) or keyword: tactics, platforms, "
    "description — knowledge-tier only. "
    "'atomic' — the exact TESTED command (+cleanup) for a technique id, from Atomic Red Team. "
    "'catalog' — where to fetch deeper material: wordlists, PoC repos, frameworks for a category keyword. "
    "'stats' — one-screen inventory of the library.",
    {"type": "object", "properties": {
        "mode": {"type": "string", "description": "kev | technique | spine | atomic | catalog | stats"},
        "keyword": {"type": "string", "description": "product/vendor (kev), technique id (spine/atomic), "
                                                     "or filter keyword (technique/catalog)"},
        "domain": {"type": "string", "description": "technique mode: cloud|identity|webapp|injection|"
                                                     "privesc|evasion|network|exploitation|wireless|social|"
                                                     "telegram|diff (2024-26 interpretation differentials)"},
        "max_blast": {"type": "string", "description": "technique mode: low|medium|high|critical — cap on blast radius"},
        "max_difficulty": {"type": "string", "description": "technique mode: low|medium|high"},
        "limit": {"type": "integer", "description": "max results (default 8, cap 20)"},
        "verbose": {"type": "boolean", "description": "full summaries + detection pairs (default false)"},
        "ransomware_only": {"type": "boolean", "description": "kev mode: only ransomware-flagged CVEs"},
     },
     "required": ["mode"]})
def grimoire_query(mode="stats", keyword="", domain="", max_blast="",
                   max_difficulty="", limit=8, verbose=False,
                   ransomware_only=False):
    feed = _load_feed()
    if not feed:
        return json.dumps({"error": "grimoire feed not found — expected data/grimoire.feed.json"})
    limit = max(1, min(int(limit or 8), 20))
    out = {"mode": mode}

    # ── STATS ──────────────────────────────────────────────
    if mode == "stats":
        pm = feed.get("pack_meta") or {}
        out["library"] = {
            "techniques": pm.get("technique_count"),
            "domains": pm.get("domain_count"),
            "mitre_refs_verified": (pm.get("fetched_material") or {}).get("mitre_library_refs_verified"),
            "kev_entries": pm.get("kev_entries"),
            "kev_mode": pm.get("kev_mode"),
            "atomic_tests": (pm.get("fetched_material") or {}).get("atomic_tests_count"),
            "spine_records": (pm.get("spine") or {}).get("record_count"),
            "conscience": pm.get("conscience"),
        }
        out["usage"] = ("modes: kev(keyword=product) | technique(domain=...) | "
                        "spine(keyword=Txxxx) | atomic(keyword=Txxxx) | "
                        "catalog(keyword=category)")
        return json.dumps(out, ensure_ascii=False, indent=1)

    kw = (keyword or "").lower().strip()
    # technique mode needs NO keyword — domain/blast/difficulty filters
    # alone are a legal query (the early kw-gate starved it)
    if not kw and mode != "technique":
        out["hint"] = "provide keyword (product/vendor for kev, technique id for spine/atomic)"
        return json.dumps(out, ensure_ascii=False, indent=1)

    # ── KEV: actively-exploited nday lane ─────────────────
    if mode == "kev":
        vulns = (feed.get("kev") or {}).get("vulnerabilities") or []
        hits = []
        for v in vulns:
            blob = " ".join(str(v.get(k, "")) for k in
                            ("cveID", "vendorProject", "product", "vulnerabilityName"))
            if kw in blob.lower():
                if ransomware_only and str(v.get("knownRansomwareCampaignUse", "")).lower() != "known":
                    continue
                hits.append(v)
        out["total_kev"] = len(vulns)
        out["keyword"] = kw
        out["hits"] = len(hits)
        out["note"] = ("these CVEs are ACTIVELY EXPLOITED IN THE WILD (CISA KEV) — "
                       "reality-tested strikes; check the target's stack version "
                       "against them")
        out["entries"] = [_fmt_kev(v) for v in hits[:limit]]
        if hits and verbose:
            out["descriptions"] = [h.get("shortDescription", "")[:400] for h in hits[:limit]]
        return json.dumps(out, ensure_ascii=False, indent=1)

    # ── TECHNIQUE: offense selection with conscience ──────
    if mode == "technique":
        ts = feed.get("techniques") or []
        _BLAST_ORDER = ["low", "medium", "high", "critical"]
        sel = []
        for t in ts:
            # domain filter = substring both ways ("telegram" matches the
            # v2 feed's long domain names like "Telegram bot platform abuse")
            if domain:
                d, q = t.get("_domain", "").lower(), domain.lower()
                if d != q and q not in d and d not in q:
                    continue
            if kw and kw not in json.dumps(t, ensure_ascii=False).lower():
                continue
            if max_blast and _BLAST_ORDER.index(t.get("blast_radius", "low")) > \
                    _BLAST_ORDER.index(max_blast.lower()):
                continue
            if max_difficulty and t.get("difficulty") != max_difficulty.lower() \
                    and max_difficulty.lower() != "any":
                # difficulty filter = ceiling unless 'any'
                _DIFF = ["low", "medium", "high"]
                if _DIFF.index(t.get("difficulty", "high")) > _DIFF.index(max_difficulty.lower()):
                    continue
            sel.append(t)
        out["matches"] = len(sel)
        out["gated_warning"] = ("requires_confirmation=true techniques are OPERATOR-GATED: "
                                "name the move + the gate in your report and WAIT — "
                                "never fire them autonomously")
        out["techniques"] = [_fmt_technique(t, verbose) for t in sel[:limit]]
        return json.dumps(out, ensure_ascii=False, indent=1)

    # ── SPINE: ATT&CK knowledge tier ──────────────────────
    if mode == "spine":
        recs = ((feed.get("spine") or {}).get("records")) or []
        hits = []
        if kw.upper().startswith("T") and re.match(r"^T\d{4}", kw.upper()):
            hits = [r for r in recs if r.get("id") == f"ATTACK-{kw.upper()}"]
        if not hits:
            hits = [r for r in recs if kw in (r.get("name") or "").lower()
                    or kw in (r.get("description") or "").lower()][:limit]
        out["matches"] = len(hits)
        out["note"] = "knowledge-tier: execution-ineligible until operator promotes"
        out["records"] = [_fmt_spine(r) for r in hits[:limit]]
        return json.dumps(out, ensure_ascii=False, indent=1)

    # ── ATOMIC: tested commands ────────────────────────────
    if mode == "atomic":
        tests = (feed.get("atomic_tests") or {}).get("tests") or []
        hits = [a for a in tests if kw.upper() in (a.get("technique") or "")]
        if not hits:
            hits = [a for a in tests if kw in (a.get("test_name") or "").lower()]
        out["matches"] = len(hits)
        out["note"] = "tested simulations from Atomic Red Team — commands carry cleanup"
        out["tests"] = [_fmt_atomic(a) for a in hits[:limit]]
        return json.dumps(out, ensure_ascii=False, indent=1)

    # ── CATALOG: deeper material sources ─────────────────
    if mode == "catalog":
        cats = feed.get("catalogs") or []
        hits = [c for c in cats if kw in json.dumps(c, ensure_ascii=False).lower()]
        out["matches"] = len(hits)
        out["entries"] = [
            f"{c.get('name')} [{c.get('category')}] — {c.get('purpose')}\n"
            f"  url: {c.get('url')}\n  license: {c.get('license')}"
            for c in hits[:limit]
        ]
        return json.dumps(out, ensure_ascii=False, indent=1)

    out["error"] = f"unknown mode '{mode}' — use kev|technique|spine|atomic|catalog|stats"
    return json.dumps(out, ensure_ascii=False, indent=1)
