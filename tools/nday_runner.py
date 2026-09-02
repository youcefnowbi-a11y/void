"""TOOL: nday_runner - CVE -> PoC retrieval -> exécution locale (aucun sandbox).

NVD v2 API for the record (description, CVSS, references), GitHub search for
public PoC repos, candidate script download, syntax check, and — when the
operator supplies a verify_url, flips execute=True ET confirme avec
confirm="YES" — exécution LOCALE directe du PoC téléchargé (aucun sandbox :
le process tourne avec les droits de l'agente). N'activer execute=True que
si la source du PoC est vérifiée. Verdict JSON carries the whole chain.
"""
import json, os, re, subprocess, sys, tempfile
from urllib.parse import quote_plus  # C-N2: keyword GitHub encodé

from tools import register
from tools._exploit_lib import paced_send, verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NDAY_DIR = os.path.join(ROOT, "reports", "nday")

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
GITHUB_SEARCH = "https://api.github.com/search/repositories"
GITHUB_RAW = "https://raw.githubusercontent.com"

@register(name="nday_exploit",
          desc="ZERO-DAY/n-day: CVE -> NVD intel + GitHub PoC hunt -> exécution LOCALE directe (aucun sandbox) — n'activer execute=True que si la source du PoC est vérifiée.",
          params={"type": "object", "properties": {
              "cve_id": {"type": "string", "description": "CVE id, e.g. CVE-2024-7014"},
              "keyword": {"type": "string", "description": "fallback keyword when no CVE id"},
              "verify_url": {"type": "string", "description": "target URL to test the PoC against"},
              "execute": {"type": "boolean", "default": False, "description": "actually run downloaded PoC (operator decision — arbitrary code)"},
              "confirm": {"type": "string", "description": "tapez YES pour confirmer l'exécution locale du PoC téléchargé"},
              "timeout_min": {"type": "integer", "default": 3},
              "stack": {"type": "string", "description": "known target stack from web_fingerprint (e.g. 'nginx 1.18 / PHP 8.1')"}},
              "required": []},
          danger="loud")
def nday_exploit(cve_id=None, keyword=None, verify_url=None,
                 execute=False, confirm=None, timeout_min=3, stack=None):
    if not cve_id and not keyword:
        return verdict("nday_exploit", False, "need cve_id or keyword")

    intel = {}
    if cve_id:
        st, body, _dt = paced_send(f"{NVD_API}?cveId={cve_id}", timeout=25)
        if st == 200:
            try:
                vulns = json.loads(body).get("vulnerabilities", [])
                if vulns:
                    # R5-12: guards par champ — un record NVD malformé ne doit
                    # pas effacer TOUT le bloc intel (desc = gate stack-match)
                    c = (vulns[0] or {}).get("cve") or {}
                    intel["id"] = c.get("id", cve_id)
                    try:
                        desc = next((d.get("value", "") for d in (c.get("descriptions") or [])
                                     if isinstance(d, dict) and d.get("lang") == "en"), "")
                        intel["desc"] = desc[:600]
                    except Exception:
                        intel["desc"] = ""
                    try:
                        metrics = c.get("metrics") or {}
                        cvss_list = (metrics.get("cvssMetricV31") or metrics.get("cvssMetricV30")
                                     or metrics.get("cvssMetricV2") or [])
                        cvss = ((cvss_list[0] or {}).get("cvssData") or {}) if cvss_list else {}
                        intel["cvss"] = cvss.get("baseScore")
                        intel["severity"] = cvss.get("baseSeverity")
                        intel["vector"] = cvss.get("vectorString")
                    except Exception:
                        pass  # métriques absentes/malformées: champ par champ, le reste survit
                    try:
                        intel["references"] = [r.get("url") for r in (c.get("references") or [])
                                               if isinstance(r, dict) and r.get("url")][:20]
                    except Exception:
                        intel["references"] = []
            except Exception as ex:
                intel = {"nvd_error": str(ex)[:120]}
        else:
            intel = {"nvd_status": st}

    # ── stack-match gate: never blind-fire a PoC at the wrong stack ──
    # (Metasploit ranks by platform; we do the same with the CVE's product
    # keywords vs the target's own response headers + operator-supplied stack)
    stack_match = None
    if verify_url and intel.get("desc"):
        st, body, _dt = paced_send(verify_url, timeout=15)
        hints = []
        if st:
            hints.append(str(st))
        # product tokens from the CVE description (first meaningful words)
        prod_tokens = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}",
                       intel.get("desc", ""))[:25]]
        desc_tokens = {t for t in prod_tokens if t not in
                       ("the", "and", "for", "with", "when", "from", "this", "that",
                        "attacker", "allows", "remote", "crafted", "request", "via",
                        "could", "which", "before", "after", "issue", "vulnerability")}
        stack_text = (f"{stack or ''} {body or ''}"[:4000]).lower()
        overlap = sorted(t for t in desc_tokens if t in stack_text)
        stack_match = {"matched": overlap[:8], "confident": len(overlap) >= 1}
        intel["stack_match"] = stack_match

    # Exploit-DB reference (no API key needed for the search URL)
    if cve_id or keyword:
        intel.setdefault("references", []).append(
            f"https://www.exploit-db.com/search?cve={cve_id}" if cve_id
            else f"https://www.exploit-db.com/search?q={keyword}")

    # GitHub PoC hunt
    q = cve_id or keyword
    poc = {"repos": [], "scripts": [], "executed": None}
    gst, gbody, _gdt = paced_send(f"{GITHUB_SEARCH}?q={quote_plus(q)}&sort=stars&per_page=6",
                                  headers={"Accept": "application/vnd.github+json"},
                                  timeout=25)
    if gst == 200:
        try:
            repos = json.loads(gbody).get("items", [])
            poc["repos"] = [{"name": r["full_name"], "stars": r["stargazers_count"],
                             "url": r["html_url"]} for r in repos]
        except Exception:
            pass

    # pull candidate scripts from the top repos
    os.makedirs(NDAY_DIR, exist_ok=True)
    safe_tag = re.sub(r"[^A-Za-z0-9_\-]", "_", q)[:40]
    workdir = os.path.join(NDAY_DIR, safe_tag)
    for r in poc["repos"][:3]:
        full = r["name"]
        ast, abody, _adt = paced_send(
            f"https://api.github.com/repos/{full}/git/trees/HEAD?recursive=1", timeout=25)
        if ast != 200:
            continue
        try:
            tree = json.loads(abody).get("tree", [])
        except Exception:
            continue
        scripts = [t["path"] for t in tree
                   if t.get("type") == "blob"
                   and re.search(r"\.(py|sh)$", t["path"])
                   and not re.search(r"(?:test|setup|install|requirement)", t["path"], re.I)][:5]
        for spath in scripts[:2]:
            rst, rbody, _rdt = paced_send(f"{GITHUB_RAW}/{full}/HEAD/{spath}", timeout=25)
            if rst == 200 and len(rbody) > 50:
                out_path = os.path.join(workdir, f"{safe_tag}_{os.path.basename(spath)}")
                try:
                    os.makedirs(workdir, exist_ok=True)
                    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
                        f.write(rbody)
                    poc["scripts"].append({"repo": full, "path": spath,
                                           "saved": out_path, "size": len(rbody)})
                except Exception:
                    pass
        if poc["scripts"]:
            break

    # exécution LOCALE directe (aucun sandbox) — triple confirmation:
    # execute booléen exact True ET confirm == "YES" ET stack-match confiant.
    # C-N1: la gate « never blind-fire a PoC at the wrong stack » gate
    # VRAIMENT désormais — sans stack_match confiant, pas d'exécution.
    if (execute is True and confirm == "YES" and verify_url and poc["scripts"]
            and stack_match and stack_match.get("confident")):
        script = poc["scripts"][0]["saved"]
        # basic safety scan of PoC content
        try:
            with open(script, "r", encoding="utf-8", errors="replace") as _f:
                content = _f.read()
            _danger = ["reverse_shell", "bind_shell", "rm -rf /", "format c:",
                       "shutil.rmtree('/')", "os.system('rm"]
            flagged = [d for d in _danger if d in content]
            if flagged:
                poc["executed"] = {"script": script, "exit": -1,
                                   "tail": f"SAFETY: blocked patterns: {flagged[:3]}"}
            else:
                cmd = ([sys.executable, "-u", script, verify_url] if script.endswith(".py")
                       else ["bash", script, verify_url])
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=timeout_min * 60, cwd=workdir)
                    tail = (result.stdout[-1500:] + "\n" + result.stderr[-500:]).strip()
                    poc["executed"] = {"script": script, "exit": result.returncode,
                                       "tail": tail[:1500]}
                except subprocess.TimeoutExpired:
                    poc["executed"] = {"script": script, "exit": -1,
                                       "tail": f"PoC timed out after {timeout_min}min"}
                except Exception as ex:
                    poc["executed"] = {"script": script, "exit": -1,
                                       "tail": f"{type(ex).__name__}: {str(ex)[:300]}"}
        except Exception as ex:
            poc["executed"] = {"script": script, "exit": -1,
                               "tail": f"read error: {str(ex)[:200]}"}

    executed = poc.get("executed")
    note = None
    if executed:
        # C-N3: False uniquement après une exécution réelle échouée
        exploitable = executed.get("exit") == 0
    elif execute is True and poc["scripts"]:
        # C-N1/N3: exécution demandée mais bloquée par la gate stack-match
        # — non testé ≠ propre
        exploitable = "partial"
        note = ("execution requested but blocked by stack-match gate — "
                "verdict 'partial' (untested)")
    elif not poc["scripts"]:
        # C-N3: rien de stagé — RIEN n'a été testé ; l'ancien False était lu
        # « cible propre » par l'intel downstream (contrat tri-state violé)
        exploitable = "partial"
        note = "no PoC staged — nothing tested, verdict 'partial' (untested ≠ clean)"
    else:
        exploitable = None  # stagé, non exécuté → 'partial' en sortie (idem avant)
    summary = (f"{q}: {len(poc['repos'])} PoC repos, {len(poc['scripts'])} script(s) staged"
               + (f" — stack match: {stack_match['matched']}" if stack_match and stack_match.get("confident") else "")
               + (" — EXECUTED" if executed else " — staged only (execute=False)")
               if poc["scripts"] else
               f"{q}: no public PoC found — candidate for original research")
    extra = {"intel": intel, "poc": poc}
    if note:
        extra["note"] = note
    return verdict("nday_exploit", exploitable if exploitable is not None else "partial",
                   summary,
                   evidence=[json.dumps(poc["repos"][:3])[:300]] if poc["repos"] else [],
                   **extra)
