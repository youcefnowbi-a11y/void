"""VOIDFORGE :: mission workspace — the evidence ledger per target.

One folder per target. Everything the agent does leaves a trace:
    missions/<target>/
        ledger.jsonl        every tool run: ts, round, tool, args, status, verdict
        extractions/        every data dump (sqli rows, API bodies, recon maps)
        findings/           every confirmed/partial vulnerability + INDEX.md
        reports/            the final mission report + the POWER REPORT
                            (where the agent is strong, where she is weak)

Why: one final report hides the campaign. The ledger shows HOW she fought —
which weapons fired clean, which jammed, which extractions returned gold
and which returned dust. The power report is her self-audit, written from
the ledger, so the operator sees exactly where to train her next.
"""
import json, os, re, time
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACES = os.path.join(ROOT, "missions")

# tools whose output IS collected intelligence (persisted to extractions/)
DATA_TOOLS = {
    "sqli_union_dump", "sqli_blind_extract", "data_extract", "data_dump_paginated",
    "api_sweep", "supabase_exfil", "supabase_full_assault", "realtime_tap",
    "har_dissect", "har_tokens", "secret_scan", "wayback_urls", "js_mine_url",
    "js_mine_site", "subdomain_enum", "endpoint_oracle", "ip_intel",
    "port_scan_sync", "tg_messages_dump", "tg_history_harvest",
    "tg_members_scrape", "tg_market_scan", "graphql_introspect", "deploy_watch",
    "nvd_search", "cisa_kev", "fuzz_attack_surface", "crash_triage_next",
    "web_fingerprint", "spa_crawl", "race_smash", "smuggle_probe",
    "proto_pollute", "xxe_probe", "redirect_cast",
}


def _slug(name):
    s = re.sub(r"[^a-z0-9._-]+", "_", (name or "").lower()).strip("_")
    # R2-8 : ".." ne doit jamais survivre au slug (garde anti-traversée réelle)
    if not s or set(s) <= {".", "-"}:
        return "target"
    return s[:48] or "target"


def extract_target(mission):
    """Best-effort target name from the mission text (hostname preferred,
    port stripped — one folder per target, whatever the service)."""
    m = re.search(r"https?://([^/\s,;\"]+)", mission or "")
    if m:
        return _slug(m.group(1).split(":")[0])
    m = re.search(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b", (mission or "").lower())
    if m:
        return _slug(m.group(1).split(":")[0])
    return None


class Workspace:
    def __init__(self, target=None):
        self.created = time.strftime("%Y%m%d_%H%M%S")
        self.target = _slug(target) if target else None
        base = os.path.join(WORKSPACES, self.target or f"untitled_{self.created}")
        self.dir = base
        self.extractions = os.path.join(base, "extractions")
        self.findings = os.path.join(base, "findings")
        self.reports = os.path.join(base, "reports")
        for d in (base, self.extractions, self.findings, self.reports):
            os.makedirs(d, exist_ok=True)
        self.ledger_path = os.path.join(base, "ledger.jsonl")
        self.stats = {"runs": 0, "ok": 0, "failed": 0,
                      "findings": 0, "extractions": 0}

    # ── ledger: every tool run, one JSON line ────────────────────────
    def log_run(self, tool, args, out, duration, status, round_num):
        verdict = None
        try:
            parsed = json.loads(out) if isinstance(out, str) and out.startswith("{") else None
            if isinstance(parsed, dict) and "exploitable" in parsed:
                verdict = {"exploitable": parsed.get("exploitable"),
                           "summary": (parsed.get("summary") or "")[:300]}
        except Exception:
            pass
        entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "round": round_num,
                 "tool": tool, "args": _json_compact(args), "status": status,
                 "duration": duration, "verdict": verdict}
        try:
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        self.stats["runs"] += 1
        self.stats["ok" if status == "ok" else "failed"] += 1

    # ── extractions: the data she pulled out of the target ───────────
    def save_extraction(self, tool, out):
        if tool not in DATA_TOOLS or not out:
            return None
        fname = f"{time.strftime('%H%M%S')}_{os.urandom(2).hex()}_{_slug(tool)}.json"
        path = os.path.join(self.extractions, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False))
            self.stats["extractions"] += 1
            return path
        except Exception:
            return None

    # ── findings: every verdict that says exploitable ────────────────
    def save_finding(self, tool, out):
        try:
            d = json.loads(out) if isinstance(out, str) and out.startswith("{") else None
            if not (isinstance(d, dict) and "exploitable" in d):
                return None
            exploitable = d.get("exploitable")
            if exploitable is False or exploitable is None:
                return None
            tag = "CONFIRMED" if exploitable is True else "PARTIAL"
            fname = f"{time.strftime('%H%M%S')}_{os.urandom(2).hex()}_{_slug(tool)}_{tag.lower()}.md"
            path = os.path.join(self.findings, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# [{tag}] {tool}\n\n"
                        f"- **when**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"- **verdict**: {d.get('summary', '')}\n\n"
                        f"## verdict JSON\n```json\n{json.dumps(d, ensure_ascii=False, indent=1)[:12000]}\n```\n")
            self.stats["findings"] += 1
            return path
        except Exception:
            return None

    # ── the POWER REPORT: where she is strong, where she is weak ────
    def write_power_report(self, transcript=None):
        rows = []
        try:
            with open(self.ledger_path, encoding="utf-8") as f:
                rows = [json.loads(ln) for ln in f if ln.strip()]
        except Exception:
            pass
        if not rows:
            return None

        per_tool = {}
        for r in rows:
            t = per_tool.setdefault(r["tool"], {"runs": 0, "ok": 0, "conf": 0,
                                                "partial": 0, "neg": 0, "dur": 0.0})
            t["runs"] += 1
            t["ok"] += 1 if r["status"] == "ok" else 0
            t["dur"] += r.get("duration") or 0
            v = (r.get("verdict") or {}).get("exploitable")
            if v is True: t["conf"] += 1
            elif v == "partial": t["partial"] += 1
            elif v is False: t["neg"] += 1

        strong, weak, dead, intel = [], [], [], []
        for name, t in sorted(per_tool.items(), key=lambda kv: -kv[1]["runs"]):
            rate = t["ok"] / max(1, t["runs"])
            line = (f"- `{name}` — {t['runs']} run(s), {rate:.0%} ok, "
                    f"verdicts: {t['conf']} confirmed / {t['partial']} partial / {t['neg']} negative, "
                    f"{t['dur']:.1f}s total")
            if t["conf"] > 0:
                strong.append(line)
            elif t["partial"] > 0:
                strong.append(line + " *(partial — worth re-aiming)*")
            elif t["ok"] < t["runs"]:
                weak.append(line)
            elif t["conf"] + t["partial"] + t["neg"] == 0:
                # pas de contrat de verdict (recon/extraction) — ni fort ni faible,
                # du renseignement ; mort seulement si massif sans strike derrière
                if name in DATA_TOOLS and t["runs"] >= 4:
                    dead.append(f"- `{name}` — {t['runs']} runs sans strike derrière "
                                f"({t['dur']:.1f}s) — extraction sans ouverture")
                else:
                    intel.append(line)
            else:
                weak.append(line)

        domain_counts = {
            "recon": sum(1 for r in rows if r["tool"] in
                         ("web_fingerprint", "subdomain_enum", "waf_detect", "dir_brute",
                          "wayback_urls", "ip_intel", "port_scan_sync", "js_mine_url", "js_mine_site")),
            "scout": sum(1 for r in rows if r["tool"] in
                         ("sqli_probe_param", "nuclei_scan", "param_brute", "ssrf_probe",
                          "endpoint_oracle", "graphql_introspect", "fuzz_attack_surface")),
            "strike": sum(1 for r in rows if r["tool"] in
                          ("sqli_union_dump", "sqli_blind_extract", "cmd_exec_probe", "shell_exec",
                           "ssti_detect_rce", "lfi_file_read", "jwt_forge_replay", "idor_enum",
                           "idor_b64_walk", "upload_webshell", "race_smash", "smuggle_probe",
                           "proto_pollute", "xxe_probe", "redirect_cast")),
            "exfil": sum(1 for r in rows if r["tool"] in
                         ("data_extract", "data_dump_paginated", "api_sweep", "supabase_exfil")),
        }
        balance = []
        labels = {"recon": "Reconnaissance", "scout": "Détection (scouts)",
                  "strike": "Frappe (strikes)", "exfil": "Extraction de données"}
        for k, lbl in labels.items():
            n = domain_counts[k]
            bar = "█" * min(30, n)
            balance.append(f"- {lbl:<26} {bar} {n}")

        md = [f"# RAPPORT DE PUISSANCE — {self.target or 'untitled'}",
              f"*auto-généré du ledger — {time.strftime('%Y-%m-%d %H:%M:%S')} · "
              f"{len(rows)} exécutions · {self.stats['findings']} finding(s) · "
              f"{self.stats['extractions']} extraction(s)*",
              "",
              "## Où elle est FORTE",
              *(strong or ["*aucune arme n'a confirmé d'exploit cette mission*"]),
              "",
              "## Où elle est FAIBLE",
              *(weak or ["*aucune faiblesse détectée — mission propre*"]),
              ""]
        if intel:
            md += ["## Renseignement (outils sans verdict — ni fort ni faible)",
                   *intel, ""]
        if dead:
            md += ["## Où elle a perdu son temps",
                   *(f"- `{ln.strip('- ')}`" for ln in dead), ""]
        md += ["## Équilibre de la campagne (runs par domaine)",
               *balance, ""]
        if transcript:
            tool_calls = sum(1 for k, _ in transcript if k == "tool")
            rounds = len([k for k, _ in transcript if k == "agent"])
            md += ["## Effort", f"- rounds de raisonnement: {rounds}", f"- appels d'outils: {tool_calls}", ""]
        path = os.path.join(self.reports, "power_report.md")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(md))
            self._write_findings_index()
            return path
        except Exception:
            return None

    def _write_findings_index(self):
        files = sorted(os.listdir(self.findings)) if os.path.isdir(self.findings) else []
        if not files:
            return
        lines = ["# INDEX DES FINDINGS", ""]
        for fn in files:
            if fn == "INDEX.md" or not fn.endswith(".md"):
                continue
            lines.append(f"- [[{fn}]]")
        try:
            with open(os.path.join(self.findings, "INDEX.md"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    # ── final report saved into the workspace too ────────────────────
    def save_final_report(self, content):
        fname = f"rapport_final_{time.strftime('%Y%m%d_%H%M%S')}.md"
        path = os.path.join(self.reports, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")
            return path
        except Exception:
            return None

    # ── the agent's own pen: reports she writes mid-mission ─────────
    def write_report(self, title, content, kind="progress"):
        """The model writes her own report into the workspace."""
        safe = _slug(title) or "note"
        fname = f"{kind}_{time.strftime('%H%M%S')}_{safe}.md"
        path = os.path.join(self.reports, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n*[{kind} · {time.strftime('%Y-%m-%d %H:%M:%S')} · "
                        f"cible {self.target}]*\n\n{content}\n")
            return path
        except Exception:
            return None

    def log_comm(self, text, kind="info"):
        """Operator comms — everything she says to the user is journaled."""
        try:
            with open(os.path.join(self.dir, "comm.log"), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} [{kind}] {text}\n")
            return True
        except Exception:
            return False

    def status(self):
        """What is archived so far — so she can reference her own evidence."""
        def _n(d):
            p = os.path.join(self.dir, d)
            return sorted(os.listdir(p)) if os.path.isdir(p) else []
        return {"target": self.target,
                "ledger_entries": self.stats["runs"],
                "extractions": _n("extractions"),
                "findings": _n("findings"),
                "reports": _n("reports")}

    # ── THE PROOF SECTION: every datum, cited, for the final report ──
    def proof_section(self, cap=7000):
        """Markdown dossier of EVERYTHING archived — findings verdicts,
        extraction previews, campaign summary. Appended to the final report
        so the deliverable always carries the data, even if the model
        writes from memory."""
        out = []
        # 1. findings — verdict + summary per finding card
        fdir = self.findings
        ffiles = sorted(x for x in os.listdir(fdir) if x.endswith(".md") and x != "INDEX.md") \
            if os.path.isdir(fdir) else []
        out.append(f"\n\n## 🗂 PREUVES ARCHIVÉES — missions/{self.target or 'untitled'}/")
        out.append(f"\n### Findings ({len(ffiles)})")
        if not ffiles:
            out.append("*aucun verdict exploitable cette campagne*")
        for fn in ffiles:
            try:
                with open(os.path.join(fdir, fn), encoding="utf-8") as f:
                    head = f.read(400)
                first = head.splitlines()[0] if head else fn
                out.append(f"- {first} `({fn})`")
            except Exception:
                out.append(f"- {fn}")
        # 2. extractions — what came OUT of the target, with previews
        edir = self.extractions
        efiles = sorted(x for x in os.listdir(edir) if x.endswith(".json")) \
            if os.path.isdir(edir) else []
        out.append(f"\n### Données extraites ({len(efiles)} fichiers)")
        budget = cap - sum(len(x) for x in out) - 400
        for fn in efiles:
            if budget <= 60:
                out.append(f"- … et {len(efiles) - efiles.index(fn)} autres dans extractions/")
                break
            try:
                p = os.path.join(edir, fn)
                size = os.path.getsize(p)
                with open(p, encoding="utf-8") as f:
                    raw = f.read(1200)
                preview = ""
                try:
                    d = json.loads(raw if raw.endswith("}") or raw.endswith("]")
                                   else raw[:raw.rfind("}") + 1] or raw[:raw.rfind("]") + 1] or raw)
                    if isinstance(d, list):
                        preview = f"{len(d)} items — 1er: {str(d[0])[:140]}"
                    elif isinstance(d, dict):
                        keys = ", ".join(list(d.keys())[:8])
                        preview = f"clés [{keys}] — {str(list(d.values())[0])[:120] if d else ''}"
                except Exception:
                    preview = raw[:140]
                line = f"- `{fn}` ({size}o) — {preview}"
                out.append(line)
                budget -= len(line)
            except Exception:
                out.append(f"- `{fn}` (lecture impossible)")
        # 3. ledger summary
        try:
            with open(self.ledger_path, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            n_err = sum(1 for r in rows if r["status"] == "error")
            out.append(f"\n### Campagne (ledger) — {len(rows)} exécutions, {n_err} échec(s)")
        except Exception:
            pass
        text = "\n".join(out)
        return text[:cap]


def _json_compact(args):
    try:
        return json.dumps(args, ensure_ascii=False)[:300]
    except Exception:
        return "{}"


# ── active workspace: the current mission's folder, reachable from TOOLS ──
# (same pattern as core.blackboard.set_active — the executing tool asks the
#  module for the mission context the agent loop established)
import threading
_thread_local = threading.local()


def set_active(ws):
    _thread_local.active_ws = ws


def get_active():
    return getattr(_thread_local, "active_ws", None)


def workspace_for(mission):
    """Create (or reuse) the workspace for this mission's target."""
    return Workspace(extract_target(mission))
