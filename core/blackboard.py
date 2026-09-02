"""VOIDFORGE :: Living Graph — event-sourced target intelligence.

Every tool observation becomes a Fact with provenance and calibrated
confidence. Assets are graph nodes, relationships are edges. The board
persists per-target (data/intel/<domain>.json + .events.jsonl audit log),
powers the MCTS planner, the swarm coordinator, the report generator, and
the unmade-connections engine that hunts pairs the agent never tried.

Design invariants:
  - facts are append-only (event log); assets/edges are fold(facts) + cache
  - confidence is fused in log-odds space with same-source discounting
  - every mutation is thread-safe (RLock) and persisted atomically
"""
import json, os, re, threading, time, hashlib, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTEL_DIR = os.path.join(ROOT, "data", "intel")

ASSET_KINDS = ("domain", "endpoint", "identity", "key", "bucket", "service", "tech", "account")
RELATIONS = ("authenticates_to", "references", "called_by", "hosted_on", "extracted_from", "same_origin")

_URL_RE = re.compile(r"https?://[a-zA-Z0-9.\-]+(?::\d+)?(?:/[a-zA-Z0-9/_.\-~%]*)?")
_JWT_RE = re.compile(r"eyJhbGci[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_KEY_RE = re.compile(r"(?:sk_|pk_|sb_secret_|whsec_|AIza|xoxb-|ghp_)[A-Za-z0-9_\-]{16,}")
_ANON_RE = re.compile(r"eyJ[a-zA-Z0-9_-]{80,}\.eyJ[a-zA-Z0-9_-]{80,}\.[A-Za-z0-9_-]{20,}")
_SUPA_RE = re.compile(r"([a-z0-9]{20})\.supabase\.co")
_R2_RE = re.compile(r"https://[a-z0-9\-]+\.r2\.dev[^\s'\"]*")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def _norm_endpoint(url):
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url.strip())
        path = p.path.rstrip("/") or "/"
        return f"{p.scheme}://{p.netloc}{path}"
    except Exception:
        return url.strip()[:200]


def _fuse(confs, sources):
    """Fuse confidence scores in log-odds space. Repeated observations from
    the SAME source are geometrically discounted (0.4^k: the 1st corroborates,
    the 2nd whispers, the 3rd is an echo) — they corroborate, they don't
    multiply."""
    lo = 0.0
    seen = {}
    for c, s in zip(confs, sources):
        c = max(0.01, min(0.99, float(c)))
        discount = 0.4 ** seen.get(s, 0)
        seen[s] = seen.get(s, 0) + 1
        lo += discount * math.log(c / (1 - c))
    lo += 1.0  # prior odds ~ e^1 ≈ 2.7 for anything *observed at all*
    p = 1 / (1 + math.exp(-lo))
    return round(p, 3)


def _replace_with_retry(tmp, dst, attempts=3, delay=0.2):
    """os.replace peut échouer sous Windows si un lecteur tient la destination
    (R2-4) — retry court puis avertissement visible, jamais silencieux."""
    for attempt in range(attempts):
        try:
            os.replace(tmp, dst)
            return True
        except PermissionError:
            if attempt < attempts - 1:
                time.sleep(delay)
    print(f"[blackboard] WARN: remplacement impossible de {dst} "
          "(fichier tenu par un lecteur concurrent) — état non persisté ce tour")
    return False


class Blackboard:
    def __init__(self, target, fresh=False):
        self.target = (target or "unknown").strip().lower()
        safe = re.sub(r"[^a-z0-9.\-]", "_", self.target)[:60] or "unknown"
        self.path = os.path.join(INTEL_DIR, f"{safe}.json")
        self.events_path = self.path.replace(".json", ".events.jsonl")
        self.lock = threading.RLock()
        self.assets = {}      # key -> {kind, value, props, confidence, sources[], ts}
        self.edges = {}       # (src,rel,dst) -> {confidence, sources[], ts}
        self.facts = []       # event log (capped on save)
        self.tested = {}      # asset key -> {tool: "verdict"}
        self._seq = 0
        self._last_save = 0.0  # monotonic ts du dernier save (R2-6, coalescing)
        self._dirty = False    # mutation non persistée ?
        if not fresh:
            self.load()

    # ── ingestion ────────────────────────────────────────────────
    def add_asset(self, kind, value, props=None, confidence=0.6, source_tool="agent", evidence=""):
        kind = kind if kind in ASSET_KINDS else "service"
        value = (value or "").strip()[:400]
        if not value:
            return None
        if kind == "endpoint":
            value = _norm_endpoint(value)
        key = f"{kind}:{value}"
        with self.lock:
            self._seq += 1
            self.facts.append({"seq": self._seq, "ts": _now(), "op": "asset",
                               "kind": kind, "key": key, "value": value,
                               "confidence": confidence, "source": source_tool,
                               "evidence": evidence[:300]})
            a = self.assets.get(key)
            if a:
                # D-B2 : rejouer les observations BRUTES. L'ancienne forme
                # _fuse([fusé, nouveau], …) re-stackait prior +1.0 ET le
                # logit du résultat précédent à chaque ré-observation
                # (0.60 → 0.83 → 0.94 → 0.995 — runaway). Le replay des raw
                # rend le discount 0.4^k stable (l'écho même-source plafonne
                # ~0.842) et la corroboration indépendante reprend la main.
                a.setdefault("_raw", []).append((confidence, source_tool))
                a["confidence"] = _fuse([c for c, _ in a["_raw"]],
                                        [s for _, s in a["_raw"]])
                if props:
                    a["props"].update({k: v for k, v in props.items() if v not in (None, "")})
                if source_tool not in a["sources"]:
                    a["sources"].append(source_tool)
            else:
                self.assets[key] = {"kind": kind, "value": value, "props": dict(props or {}),
                                    "confidence": confidence, "sources": [source_tool], "ts": _now(),
                                    "_raw": [(confidence, source_tool)]}
            self._append_event({"seq": self._seq, "op": "asset", "key": key})
            return key

    def link(self, src_key, rel, dst_key, confidence=0.6, source_tool="agent"):
        rel = rel if rel in RELATIONS else "references"
        if src_key not in self.assets or dst_key not in self.assets:
            return None
        ekey = (src_key, rel, dst_key)
        with self.lock:
            self._seq += 1
            self.facts.append({"seq": self._seq, "ts": _now(), "op": "link", "key": str(ekey),
                               "confidence": confidence, "source": source_tool})
            e = self.edges.get(ekey)
            if e:
                # D-B2 : même replay raw que les assets (pas de re-stack du prior).
                e.setdefault("_raw", []).append((confidence, source_tool))
                e["confidence"] = _fuse([c for c, _ in e["_raw"]],
                                        [s for _, s in e["_raw"]])
                if source_tool not in e["sources"]:
                    e["sources"].append(source_tool)
            else:
                self.edges[ekey] = {"confidence": confidence, "sources": [source_tool], "ts": _now(),
                                    "_raw": [(confidence, source_tool)]}
            self._append_event({"seq": self._seq, "op": "link", "key": str(ekey)})
            return ekey

    def mark_tested(self, asset_key, tool, verdict):
        """Record that an asset was actively probed — drives coverage."""
        with self.lock:
            self.tested.setdefault(asset_key, {})[tool] = str(verdict)[:120]

    def is_tested(self, asset_key):
        return asset_key in self.tested

    # ── queries ──────────────────────────────────────────────────
    def assets_of(self, kind):
        return [a for a in self.assets.values() if a["kind"] == kind]

    def edges_of(self, rel=None):
        return [(k, v) for k, v in self.edges.items() if rel is None or k[1] == rel]

    def linked(self, a, b):
        for (s, _r, d) in self.edges:
            if (s, d) in ((a, b), (b, a)):
                return True
        return False

    def coverage(self):
        """Tested vs untouched per asset kind."""
        cov = {}
        for k, a in self.assets.items():
            c = cov.setdefault(a["kind"], {"total": 0, "tested": 0})
            c["total"] += 1
            if k in self.tested:
                c["tested"] += 1
        return cov

    def unmade_connections(self, limit=8):
        """Hunt pairs the agent never tried. Returns ranked suggestions."""
        out = []
        keys = [a for a in self.assets.values() if a["kind"] == "key"]
        endpoints = [a for a in self.assets.values() if a["kind"] == "endpoint"]
        for k in keys:
            for e in endpoints:
                kk, ek = f"key:{k['value']}", f"endpoint:{e['value']}"
                if self.linked(kk, ek):
                    continue
                boost = 0.15 if not self.is_tested(ek) else 0.0
                out.append({"suggestion": f"probe {e['value']} using {k['kind']} {k['value'][:24]}…",
                            "why": "key asset exists, endpoint reachable, pairing never attempted",
                            "assets": [kk, ek], "suggested_tool": "data_extract",
                            "confidence": round(min(k["confidence"], e["confidence"]) + boost, 3)})
        for a in self.assets.values():
            if a["kind"] in ("bucket",) and not self.is_tested(f"{a['kind']}:{a['value']}"):
                out.append({"suggestion": f"probe storage surface {a['value'][:60]}",
                            "why": "storage bucket discovered but never probed",
                            "assets": [f"{a['kind']}:{a['value']}"], "suggested_tool": "data_extract",
                            "confidence": a["confidence"]})
        for a in self.assets.values():
            if a["kind"] == "identity":
                for e in endpoints:
                    if "/admin" in e["value"] or "/auth" in e["value"]:
                        kk = f"identity:{a['value']}"
                        ek = f"endpoint:{e['value']}"
                        if not self.linked(kk, ek):
                            out.append({"suggestion": f"attempt identity '{a['value'][:30]}' against {e['value'][:60]}",
                                        "why": "identity discovered, auth/admin endpoint never paired",
                                        "assets": [kk, ek], "suggested_tool": "data_extract",
                                        "confidence": round(min(a["confidence"], e["confidence"]) + 0.1, 3)})
        out.sort(key=lambda s: -s["confidence"])
        return out[:limit]

    # ── generic tool-result ingestion (passive intel bridge) ─────
    def from_tool_result(self, tool_name, result):
        """Walk any tool result (dict/list/str) and auto-ingest assets."""
        origin = ""
        seen_strings = set()

        def classify(s):
            for m in _JWT_RE.finditer(s):
                self.add_asset("key", m.group(0)[:400],
                               props={"kind_of_key": "jwt"},
                               confidence=0.8, source_tool=tool_name, evidence=s[:200])
            for m in _ANON_RE.finditer(s):
                self.add_asset("key", m.group(0)[:400],
                               props={"kind_of_key": "anon_key"},
                               confidence=0.85, source_tool=tool_name, evidence=s[:200])
            for m in _KEY_RE.finditer(s):
                self.add_asset("key", m.group(0)[:200],
                               props={"kind_of_key": "api_key"},
                               confidence=0.8, source_tool=tool_name, evidence=s[:200])
            for m in _SUPA_RE.finditer(s):
                ref = m.group(1)
                d = self.add_asset("domain", f"{ref}.supabase.co",
                                   props={"service": "supabase", "ref": ref},
                                   confidence=0.9, source_tool=tool_name)
                if origin and d:
                    self.link(f"endpoint:{_norm_endpoint(origin)}", "references", d, 0.7, tool_name)
            for m in _R2_RE.finditer(s):
                self.add_asset("bucket", m.group(0)[:200], confidence=0.75,
                               source_tool=tool_name)
            for m in _URL_RE.finditer(s):
                u = m.group(0)
                if u in seen_strings or len(u) < 12:
                    continue
                seen_strings.add(u)
                if origin and u.startswith(origin):
                    self.add_asset("endpoint", u, confidence=0.7, source_tool=tool_name)
                else:
                    from urllib.parse import urlsplit
                    self.add_asset("domain", urlsplit(u).netloc,
                                   confidence=0.7, source_tool=tool_name)
            # relative URLs (SPA-style "/api/x") resolve against the target origin
            for m in re.finditer(r'"(/(?:api|rest/v1|auth/v1|functions/v1|_serverFn|admin|[a-z_]+/v1)[a-zA-Z0-9/_.\-]*)"', s):
                if not origin:
                    continue
                self.add_asset("endpoint", origin.rstrip("/") + m.group(1),
                               confidence=0.6, source_tool=tool_name)

        def walk(node, depth=0):
            if depth > 8:
                return
            if isinstance(node, str):
                if 8 < len(node) < 20000:
                    classify(node)
            elif isinstance(node, dict):
                for v in node.values():
                    walk(v, depth + 1)
            elif isinstance(node, list):
                for v in node[:200]:
                    walk(v, depth + 1)

        try:
            parsed = result if isinstance(result, (dict, list)) else json.loads(result)
        except Exception:
            parsed = result if isinstance(result, str) else str(result)

        # origin = first URL in the tool args-ish result (best effort)
        m = _URL_RE.search(json.dumps(parsed)[:4000]) if isinstance(parsed, (dict, list)) else _URL_RE.search(str(parsed))
        if m:
            origin = m.group(0)
        walk(parsed)
        # R2-6 : save coalescé — from_tool_result tourne à chaque observation
        # dans les 5 workers concurrents ; on marque dirty et on ne dump que
        # si le dernier save date de > 2s (le prochain save() complet rattrape).
        with self.lock:
            self._dirty = True
            if time.monotonic() - self._last_save > 2.0:
                self.save()

    # ── persistence ──────────────────────────────────────────────
    def _append_event(self, ev):
        try:
            os.makedirs(INTEL_DIR, exist_ok=True)
            # R2-6 : rotation unique quand le journal d'events dépasse 5 Mo
            # (facts est cappé à 2000, events ne l'était pas du tout).
            try:
                if (os.path.exists(self.events_path)
                        and os.path.getsize(self.events_path) > 5_000_000):
                    stamp = time.strftime("%Y%m%d_%H%M%S")
                    os.replace(self.events_path,
                               f"{self.events_path}.{stamp}")
            except OSError:
                pass  # rotation non critique : l'append continue
            with open(self.events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": _now(), **ev}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def save(self):
        with self.lock:
            try:
                os.makedirs(INTEL_DIR, exist_ok=True)
                data = {"target": self.target, "updated": _now(),
                        "assets": self.assets,
                        "edges": {f"{s}|{r}|{d}": v for (s, r, d), v in self.edges.items()},
                        "tested": self.tested,
                        "facts": self.facts[-2000:]}
                # per-thread tmp: concurrent swarm saves must not clobber each other
                tmp = f"{self.path}.{threading.get_ident()}.tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=1)
                _replace_with_retry(tmp, self.path)
                self._last_save = time.monotonic()  # R2-6 : repère du coalescing
                self._dirty = False
            except Exception:
                pass

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.assets = data.get("assets", {})
            self.edges = {tuple(k.split("|", 2)): v for k, v in data.get("edges", {}).items()}
            self.tested = data.get("tested", {})
            self.facts = data.get("facts", [])
            self._seq = max((f.get("seq", 0) for f in self.facts), default=0)
        except Exception:
            pass

    # ── rendering ────────────────────────────────────────────────
    def stats(self):
        with self.lock:
            return {"target": self.target, "assets": len(self.assets),
                    "edges": len(self.edges), "facts": len(self.facts),
                    "tested": sum(len(v) for v in self.tested.values()),
                    "coverage": self.coverage()}

    def to_prompt(self, max_lines=48):
        """Compact rendering for injection into an agent system prompt."""
        with self.lock:
            lines = [f"TARGET INTEL — {self.target} "
                     f"({len(self.assets)} assets, {len(self.edges)} links, "
                     f"{len(self.facts)} events)"]
            by_kind = {}
            for k, a in sorted(self.assets.items(), key=lambda kv: -kv[1]["confidence"]):
                by_kind.setdefault(a["kind"], []).append((k, a))
            for kind in ASSET_KINDS:
                group = by_kind.get(kind)
                if not group:
                    continue
                shown = 0
                for k, a in group:
                    if shown >= 6 or len(lines) >= max_lines - 6:
                        break
                    t = " ✓tested" if k in self.tested else ""
                    lines.append(f"  [{kind}] {a['value'][:90]} (conf {a['confidence']}){t}")
                    shown += 1
                rest = len(group) - shown
                if rest > 0:
                    lines.append(f"  [{kind}] …+{rest} more")
            for s in self.unmade_connections(4):
                lines.append(f"  → TRY: {s['suggestion'][:100]} (conf {s['confidence']})")
            return "\n".join(lines[:max_lines])


# ── context-global active board (transport hooks write here) ─────
_active = None
_active_lock = threading.Lock()


def set_active(board):
    global _active
    with _active_lock:
        _active = board


def get_active():
    with _active_lock:
        return _active


def observe(tool_name, result):
    """One-liner every tool can call: feeds the active blackboard."""
    b = get_active()
    if b is not None:
        try:
            b.from_tool_result(tool_name, result)
        except Exception:
            pass
    return b
