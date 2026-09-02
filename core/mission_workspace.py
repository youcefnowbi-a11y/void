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
    # signaux de preuve : détectés MÉCANIQUEMENT à l'arrivée de chaque
    # réponse — c'est l'index que l'opérateur citait à la main avant.
    _PROOF_MARKERS = [
        ("client_secret", re.compile(r"clientSecret|cs_(?:live|test)_")),
        ("amount", re.compile(r"[\"']?(?:amount|unitAmount|amount_total)[\"']?\s*[:=]")),
        ("success_true", re.compile(r"[\"']success[\"']\s*:\s*true")),
        ("token_or_cookie", re.compile(
            r"(?:__session|__client|set-cookie|access_token)[\"']?\s*[:=]", re.I)),
        ("http_2xx", re.compile(r"[\"']?status[\"']?\s*:\s*2\d\d")),
        ("http_4xx", re.compile(r"[\"']?status[\"']?\s*:\s*4\d\d")),
        ("http_5xx", re.compile(r"[\"']?status[\"']?\s*:\s*5\d\d")),
        ("write_verb", re.compile(r"[\"']?(?:method|verb)[\"']?\s*:\s*[\"'](?:POST|PATCH|PUT|DELETE)", re.I)),
    ]

    def save_extraction(self, tool, out):
        if tool not in DATA_TOOLS or not out:
            return None
        fname = f"{time.strftime('%H%M%S')}_{os.urandom(2).hex()}_{_slug(tool)}.json"
        path = os.path.join(self.extractions, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False))
            self.stats["extractions"] += 1
        except Exception:
            return None
        # index de preuves : une ligne par extraction, signaux détectés
        # au moment de la frappe (pas d'archéologie après-coup).
        try:
            body = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
            url = status = None
            try:
                head = json.loads(body[:20000]) if body.lstrip().startswith("{") else None
                if isinstance(head, dict):
                    url = head.get("url")
                    status = head.get("status")
            except Exception:
                pass
            markers = [name for name, pat in self._PROOF_MARKERS if pat.search(body[:40000])]
            entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "tool": tool,
                     "file": fname, "bytes": len(body),
                     "url": (url or "")[:200] or None,
                     "status": status, "markers": markers}
            with open(os.path.join(self.extractions, "index.jsonl"), "a",
                      encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return path

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

    # ── the second deliverable: findings dossier, natural language ────
    @staticmethod
    def _mask_val(v):
        """Les secrets ne sortent JAMAIS entiers dans le dossier client —
        tronqués avec pointeur vers le fichier d'extraction qui les tient."""
        v = str(v or "")
        if re.match(r"^(eyJ|sk_|pk_|rk_|whsec_|ghp_|AKIA|AIza)", v):
            return v[:22] + "…(voir extractions/)"
        return v[:80] + ("…" if len(v) > 80 else "")

    def write_findings_dossier(self, transcript=None, board=None, final_text=None,
                               cap_total=60000):
        """Livrable n°2 — le DOSSIER DE FINDINGS en langage naturel : découvertes
        organisées en tableaux (sévérité, preuve citée), défenses confirmées,
        arsenal, surfaces — SANS le bruit brut du transcript. Le rapport
        d'engagement reste le dossier technique complet ; celui-ci est la
        lecture humaine, preuve par preuve."""
        try:
            rows = []
            try:
                with open(self.ledger_path, encoding="utf-8") as f:
                    rows = [json.loads(ln) for ln in f if ln.strip()]
            except Exception:
                pass

            confirmed, partial, negatives = [], [], []
            for fn in sorted(x for x in os.listdir(self.findings)
                             if x.endswith(".md") and x != "INDEX.md") \
                    if os.path.isdir(self.findings) else []:
                try:
                    with open(os.path.join(self.findings, fn), encoding="utf-8") as f:
                        card = f.read(14000)
                except Exception:
                    continue
                verdict = None
                m = re.search(r"```json\n(\{.*?\})", card, re.S)
                if m:
                    try:
                        verdict = json.loads(m.group(1))
                    except Exception:
                        verdict = None
                tag = "CONFIRMED" if "_confirmed" in fn else (
                    "PARTIAL" if "_partial" in fn else "VERDICT")
                sev = (verdict or {}).get("severity") or ("HIGH" if tag == "CONFIRMED" else "MEDIUM")
                tool = fn.split("_", 2)[-1].rsplit("_", 1)[0] if "_" in fn else fn
                summ = (verdict or {}).get("summary") or (card.splitlines()[0] if card else fn)
                row = {"file": fn, "sev": sev, "tool": tool, "tag": tag,
                       "summary": str(summ)[:220], "card": card[:1600]}
                (confirmed if tag == "CONFIRMED" else partial).append(row)

            n_err = sum(1 for r in rows if r.get("status") == "error")
            L = [f"# DOSSIER DE FINDINGS — {self.target or 'untitled'}",
                 f"*Miroir structuré généré du workspace — {time.strftime('%Y-%m-%d %H:%M:%S')} · "
                 f"{len(rows)} exécutions d'outils ({n_err} échec(s)) · "
                 f"{len(confirmed)} confirmé(s) · {len(partial)} partiel(s)*",
                 "",
                 "> Lecture humaine de la campagne : chaque découverte porte sa preuve citée.",
                 "> Le dossier technique complet (transcript + preuves brutes) vit dans",
                 "> `reports/` de ce même dossier de mission."]
            L.append("")

            # ── 1. défenses confirmées (les négatifs propres, d'abord —
            #    c'est la partie que les rapports d'attaque oublient) ──
            for r in rows:
                v = (r.get("verdict") or {})
                if v.get("exploitable") is False:
                    negatives.append(r)
            L.append("## 1. Défenses vérifiées (testées et tenues)")
            if negatives:
                L += ["| Vecteur testé | Outil | Verdict |", "|---|---|---|"]
                for r in negatives[:25]:
                    s = (r.get("verdict") or {}).get("summary") or "tenu"
                    L.append(f"| {self._mask_val(str(r.get('args',''))[:90])} | {r['tool']} "
                             f"r{r.get('round')} | {str(s)[:90]} |")
            else:
                L.append("*aucun contrôle négatif journalisé avec un contrat de verdict*")
            L.append("")

            # ── 2. findings avec preuve citée ──
            L.append("## 2. Découvertes")
            if confirmed or partial:
                L += ["| # | Sévérité | Statut | Découverte | Preuve |",
                      "|---|---|---|---|---|"]
                for i, c in enumerate(confirmed + partial, 1):
                    proof = f"`missions/{self.target}/findings/{c['file']}`"
                    L.append(f"| {i} | {c['sev']} | {c['tag']} "
                             f"| {self._mask_val(c['summary'])} | {proof} |")
                for c in confirmed + partial[:6]:
                    L += ["", f"### [{c['tag']}] {c['tool']}",
                          "", "```json", c["card"].split("## verdict JSON")[-1]
                          .strip("`\n ")[:1200], "```"]
            else:
                L.append("*aucun verdict exploitable journalisé — les découvertes "
                         "de cette campagne vivent dans le rapport final de l'agent "
                         "(section FINDINGS) et dans les extractions ci-dessous*")
            L.append("")

            # ── 3. surfaces cartographiées (Living Graph) ──
            if board is not None:
                try:
                    st = board.stats()
                    L.append(f"## 3. Surfaces cartographiées ({st['assets']} assets / "
                             f"{st['edges']} liens)")
                    by_kind = {}
                    for a in board.assets.values():
                        by_kind.setdefault(a["kind"], []).append(a)
                    for kind in sorted(by_kind):
                        items = sorted(by_kind[kind], key=lambda a: -a["confidence"])[:10]
                        L += ["", f"### {kind} ({len(by_kind[kind])})",
                              "| Valeur | Confiance | Sources |", "|---|---|---|"]
                        for a in items:
                            L.append(f"| {self._mask_val(a['value'])} "
                                     f"| {a['confidence']} | {len(a.get('sources', []))} |")
                    L.append("")
                except Exception:
                    pass

            # ── 4. arsenal ──
            if rows:
                L.append("## 4. Arsenal déployé")
                L += ["| Outil | Runs | Dernier round |", "|---|---|---|"]
                per = {}
                for r in rows:
                    t = per.setdefault(r["tool"], [0, 0])
                    t[0] += 1
                    t[1] = max(t[1], r.get("round") or 0)
                for t, (n, last) in sorted(per.items(), key=lambda kv: -kv[1][0])[:20]:
                    L.append(f"| {t} | {n} | {last} |")
                L.append("")

            # ── 5. inventaire des preuves : l'index mécanique d'abord
            #    (étiqueté à la frappe), proof_section en repli ──
            L.append("## 5. Inventaire des preuves")
            idx_rows = []
            try:
                with open(os.path.join(self.extractions, "index.jsonl"),
                          encoding="utf-8") as f:
                    idx_rows = [json.loads(ln) for ln in f if ln.strip()]
            except Exception:
                pass
            if idx_rows:
                n_mk = sum(1 for e in idx_rows if e.get("markers"))
                L += [f"*{len(idx_rows)} extraction(s) indexée(s) — {n_mk} porteuse(s) "
                      f"de signal de preuve (détection mécanique à la frappe)*", "",
                      "| Heure | Outil | Statut | Signaux | Fichier |", "|---|---|---|---|---|"]
                for e in idx_rows[-60:]:
                    mk = ", ".join(e.get("markers") or []) or "—"
                    st = e.get("status") if e.get("status") is not None else "—"
                    L.append(f"| {e.get('ts', '—')[11:19]} | {e['tool']} | {st} "
                             f"| {mk} | `extractions/{e['file']}` |")
            else:
                try:
                    L.append(self.proof_section(cap=4500))
                except Exception:
                    pass

            # ── 6. le récit de l'agent (couche humaine) ──
            if final_text:
                L += ["", "## 6. Le compte rendu de l'agent",
                      "", final_text[:12000]]
            elif transcript:
                last = next((t for k, t in reversed(transcript)
                             if k == "agent" and t), "")
                if last:
                    L += ["", "## 6. Le compte rendu de l'agent", "", last[:12000]]

            out = "\n".join(L)[:cap_total]
            path = os.path.join(self.reports,
                                f"findings_dossier_{time.strftime('%Y%m%d_%H%M%S')}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            return path
        except Exception as ex:
            # jamais silencieux : un dossier raté doit dire pourquoi (console backend)
            print(f"[dossier] WARN génération impossible : {type(ex).__name__}: {ex}")
            return None

    # ── the third deliverable: app-state report (incidents) ───────────
    @staticmethod
    def _extract_section(text, keyword, cap=6000):
        """Extrait verbatim la section markdown qui contient `keyword`."""
        if not text:
            return None
        idx = text.upper().find(keyword.upper())
        if idx < 0:
            return None
        rest = text[idx:]
        nxt = re.search(r"\n## ", rest[1:])
        return rest[:1 + nxt.start()].strip()[:cap] if nxt else rest.strip()[:cap]

    def write_app_state_report(self, transcript=None, final_text=None,
                               cap_total=40000):
        """Livrable n°3 — l'état de l'APPLICATION vue par la mission : outils
        qui ont échoué, capacités bloquées, environnements manquants. La boucle
        de correction du harnais : chaque mission documente ce qui a grippé
        pour que l'opérateur corrige VOIDFORGE jusqu'à la perfection.
        Couche mécanique (ledger) + la section de l'agent si elle l'a écrite."""
        try:
            rows = []
            try:
                with open(self.ledger_path, encoding="utf-8") as f:
                    rows = [json.loads(ln) for ln in f if ln.strip()]
            except Exception:
                pass
            fails = [r for r in rows if r.get("status") not in ("ok", None, "")]
            L = [f"# ÉTAT DE L'APPLICATION — {self.target or 'untitled'}",
                 f"*Rapport d'incidents de la mission — {time.strftime('%Y-%m-%d %H:%M:%S')} · "
                 f"{len(rows)} exécutions · {len(fails)} échec(s) "
                 f"({(1 - len(fails) / max(1, len(rows))):.0%} ok)*",
                 "",
                 "> Ce rapport nourrit la boucle de correction du harnais :",
                 "> chaque outil qui grippe ici est un correctif à faire côté VOIDFORGE.",
                 ""]
            if fails:
                per = {}
                for r in fails:
                    t = per.setdefault(r["tool"], {"n": 0, "rounds": [], "last": r})
                    t["n"] += 1
                    t["rounds"].append(r.get("round"))
                L += ["## Outils en échec", "",
                      "| Outil | Échecs | Rounds | Dernier incident |", "|---|---|---|---|"]
                for t, d in sorted(per.items(), key=lambda kv: -kv[1]["n"]):
                    L.append(f"| {t} | {d['n']} | {', '.join(str(x) for x in d['rounds'][-4:])} "
                             f"| {d['last'].get('ts', '—')} |")
                L += ["", "## Détail des échecs", "",
                      "| Heure | Round | Outil | Arguments (compacts) |",
                      "|---|---|---|---|"]
                for r in fails[-30:]:
                    L.append(f"| {r.get('ts', '—')[11:19]} | r{r.get('round')} | {r['tool']} "
                             f"| {self._mask_val(str(r.get('args', ''))[:110])} |")
                L += ["", "*Les réponses d'erreur complètes vivent dans `core/missions.db` "
                      f"(table `tool_runs`, dernière mission) et dans le ledger.*"]
            else:
                L.append("**Aucun échec d'outil cette mission** — harnais propre.")
            L.append("")

            # couche agent : sa section ÉTAT DE L'APPLICATION, verbatim
            section = self._extract_section(final_text, "ÉTAT DE L'APPLICATION")
            if not section and transcript:
                for k, t in reversed(transcript):
                    if k == "agent" and t:
                        section = self._extract_section(t, "ÉTAT DE L'APPLICATION")
                        if section:
                            break
            L += ["## Compte rendu d'environnement de l'agent", ""]
            L.append(section or ("*L'agent n'a pas signalé d'incident "
                                 "d'environnement (ou n'a pas suivi le protocole "
                                 "— règle 7 du system prompt).*"))

            out = "\n".join(L)[:cap_total]
            path = os.path.join(self.reports,
                                f"app_state_{time.strftime('%Y%m%d_%H%M%S')}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            return path
        except Exception as ex:
            print(f"[app_state] WARN génération impossible : {type(ex).__name__}: {ex}")
            return None

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
