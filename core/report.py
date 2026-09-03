"""VOIDFORGE :: engagement report generator.
Transforms a raw agent transcript into a professional engagement deliverable:
ROE/scope header (from config/engagement.yaml), tool ledger, severity-ranked
findings, then the full transcript for evidence."""
import json, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGAGEMENT_FILE = os.path.join(ROOT, "config", "engagement.yaml")

SEVERITY_RULES = [
    # rule_kind: "secret" (real key material, provenance-proof) | "jwt" |
    # "cred" (credential assignment) | "cloudkey" | "infra" — W1 provenance
    # gate needs to know WHAT matched, not only how bad it looks.
    ("CRITICAL", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|sk_live_[A-Za-z0-9]{16,}|service_role", re.I), "secret"),
    ("CRITICAL", re.compile(r"(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^\s'\"]{8,}", re.I), "secret"),
    ("HIGH",     re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}(\.[A-Za-z0-9_-]{10,})?"), "jwt"),  # JWT (2 ou 3 segments)
    ("HIGH",     re.compile(r"(?:anon[_\s-]?key|api[_\s-]?key|access[_\s-]?token|webhook[_\s-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{12,}", re.I), "cred"),
    ("HIGH",     re.compile(r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xoxb-[A-Za-z0-9\-]{10,}|AIza[A-Za-z0-9_\-]{35}"), "cloudkey"),
    ("MEDIUM",   re.compile(r"\.r2\.dev|\.s3\.amazonaws\.com|storage/v1/bucket|supabase\.co", re.I), "infra"),
    ("MEDIUM",   re.compile(r"(?:/rest/v1/|/auth/v1/(?:signup|anonymous-signin)|/functions/v1/)[^\s]*\s*[-–]\s*(?:200|201|307)", re.I), "infra"),
    ("MEDIUM",   re.compile(r"(?:waf|cloudflare|edge function|redirect)[:,]", re.I), "infra"),
]

# ── W1 (mission-76 autopsy): finding quality is PROVENANCE-AWARE ──────
# The engagement report claimed "25 HIGH findings" that were 25 raw JWT
# blobs — six of them HER OWN alg=none forgeries, the rest self-minted
# session tokens, all harvested mechanically from the transcript while the
# agent's own honest verdict count said ZERO. Rules:
#   1. PROVENANCE — material inside our strike/forge/crypto tools is our
#      own MUNITION (we made it, we know it), never a discovery. Real key
#      material (secret/cloudkey kinds) still passes: if OUR tool output
#      carries the target's live key, that IS a finding.
#   2. NATURE — a captured JWT without an administrative marker in its
#      context is credential material in transit: evidence (MEDIUM), not
#      impact (HIGH). Rule 8: no demonstrated end-state = no HIGH.
#   3. IDENTITY DEDUP — two JWTs of the same (iss, sub, aud) are ONE
#      finding; the old exact-blob dedup counted every re-mint as a new
#      discovery (mission 76 minted ~14 near-identical session tokens).
_SELF_ARTIFACT_TOOLS = {
    "jwt_forge_replay", "jwt_analyst", "crypto_hash", "session_keep",
    "payload_library", "har_tokens", "replay_mutate", "arsenal_selftest",
}
_ADMIN_MARKER = re.compile(
    r"(?i)\b(service[_\s-]?role|admin|internal|secret[_\s-]?key|"
    r"sk_live|privilege|root[_\s-]?token|api[_\s-]?key)\b")


def _jwt_identity(blob):
    """Structural identity (iss|sub|aud) of a JWT — same identity = same
    finding, however many times it was re-minted. Best-effort b64 decode;
    blob-prefix fallback (header b64 is identical per signing key)."""
    import base64
    try:
        seg = blob.split(".")
        if len(seg) < 2:
            return blob[:48]
        pad = "=" * (-len(seg[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(seg[1] + pad) or b"{}")
        ident = "|".join(str(payload.get(k, "")) for k in ("iss", "sub", "aud"))
        return ident or blob[:48]
    except Exception:
        return blob[:48]

def _load_engagement():
    try:
        import yaml
        with open(ENGAGEMENT_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _egress_line():
    """Egress posture dans l'en-tête ROE — relayed (exit compté, jamais nommé)
    ou direct. Le scrub passe APRÈS : une URL de relay résiduelle est masquée."""
    try:
        from core.scrub import egress_summary
        e = egress_summary()
        return [f"| Egress | {e['mode']} ({e['exits']} exit(s), sticky per target) |"]
    except Exception:
        return []


def _identity_line():
    """Tier C — posture d'identité opérationnelle : accents dérivés par cible,
    brûlés sur bloc (captcha / 403-flood). Les hosts listés sont ceux de la
    CIBLE — ils appartiennent au rapport."""
    try:
        from core.op_identity import summary as id_summary
        s = id_summary()
        n_live, n_dead = len(s["live"]), len(s["burned"])
        return [f"| Op identity | per-target derived persona "
                f"({n_live} live, {n_dead} burned during campaign) |"]
    except Exception:
        return []


def _profile_line():
    """E1 — la FORME du trafic présentée au target, comme donnée: quel
    profil malleable était de service + hash de sa shape déclarée."""
    try:
        from tools._transport import profile_hash
        ph = profile_hash()
        return [f"| Traffic profile | {ph} |"]
    except Exception:
        return []

def _extract_findings(transcript):
    """Scan transcript text, dedupe matches, rank by severity.

    W1 (mission-76 autopsy): PROVENANCE-AWARE finding quality — our own
    strike-munition (JWTs inside jwt_forge_replay/crypto_hash/forged_*)
    is never a discovery; a captured JWT without an administrative marker
    is evidence (MEDIUM), not impact (HIGH); same-identity JWTs collapse
    to one finding. A report's FINDINGS section must read like findings,
    not like our ammo inventory."""
    seen, jwt_seen, findings = set(), set(), []
    for kind, text in transcript:
        # ── provenance: whose bytes are these? ──
        tool_name = ""
        if kind == "tool" or kind.endswith(":tool"):
            tool_name = (text or "").split(":", 1)[0].strip()
        is_self_artifact = (tool_name in _SELF_ARTIFACT_TOOLS
                            or tool_name.startswith("forged_"))
        for sev, pat, rule_kind in SEVERITY_RULES:
            for m in pat.finditer(text or ""):
                # B-R2 : clé de dédup = match COMPLET. Le préfixe [:80] avalait
                # deux secrets DISTINCTS partageant 80 chars (JWTs du même
                # issuer) — le second disparaissait du livrable client.
                key = (sev, m.group(0))
                if key in seen:
                    continue
                snippet = m.group(0)
                # contexte : la ligne qui contient le match
                line = next((ln.strip()[:160] for ln in (text or "").splitlines() if m.group(0) in ln), snippet)
                # W1-1 PROVENANCE: munition made by our own tools is not a
                # discovery — EXCEPT real target key material (secret/cloudkey:
                # if our forge output carries the target's live key, the
                # target leaked it and it counts).
                if is_self_artifact and rule_kind in ("jwt", "cred", "infra"):
                    continue
                # W1-3 IDENTITY DEDUP: re-minted same-identity JWTs are one
                # finding, not N (mission 76: 14 near-identical session tokens
                # each counted as a fresh HIGH discovery).
                if rule_kind == "jwt":
                    ident = _jwt_identity(snippet)
                    if ident in jwt_seen:
                        continue
                    jwt_seen.add(ident)
                # W1-2 NATURE: a captured JWT with no administrative marker in
                # its context line is credential material in transit —
                # evidence, not demonstrated impact (rule 8: no end-state, no
                # HIGH).
                if rule_kind == "jwt" and sev == "HIGH" \
                        and not _ADMIN_MARKER.search(line):
                    sev = "MEDIUM"
                seen.add(key)
                cap = 400 if any(p in snippet for p in ("eyJ", "sk_", "AKIA")) else 120
                findings.append({"severity": sev, "evidence": snippet[:cap], "context": line})
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))
    # B-R4 : la troncature à 40 ne se fait plus en silence — write_report
    # affiche le total réel et une ligne "+N additional findings suppressed".
    suppressed = max(0, len(findings) - 40)
    return findings[:40], suppressed

def _tool_ledger(transcript):
    """Aggregate tool usage: counts per module, order of first appearance.
    Swarm transcripts use kinds like 'recon:tool' — count those too."""
    ledger, order = {}, []
    for kind, text in transcript:
        if not (kind == "tool" or kind.endswith(":tool")):
            continue
        name = (text or "").split(":", 1)[0].strip()
        if not name:
            continue
        if name not in ledger:
            ledger[name] = 0
            order.append(name)
        ledger[name] += 1
    return [(n, ledger[n]) for n in order]

def write_report(mission, transcript, folder, board=None):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(folder, f"report_{ts}.md")
    eng = (_load_engagement() or {}).get("engagement", {}) or {}
    roe = eng.get("rules_of_engagement", {}) or {}

    findings, suppressed = _extract_findings(transcript)
    ledger = _tool_ledger(transcript)
    tool_calls = sum(n for _, n in ledger)

    def _or(val, fallback="NOT RECORDED"):
        v = (val or "").strip() if isinstance(val, str) else val
        return v if v else fallback

    scope_in = ", ".join(eng.get("scope", {}).get("in_scope", []) or []) or "NOT RECORDED"
    scope_out = ", ".join(eng.get("scope", {}).get("out_of_scope", []) or []) or "none specified"

    lines = [
        f"# VOIDFORGE :: ENGAGEMENT REPORT — {ts}",
        "",
        "## EXECUTIVE SUMMARY",
        f"- **Mission:** {_or(mission)[:200]}",
        f"- **Outcome:** {tool_calls} tool executions across {len(ledger)} distinct modules",
        f"- **Findings:** {len(findings) + suppressed} "
        f"({sum(1 for f in findings if f['severity']=='CRITICAL')} critical / "
        f"{sum(1 for f in findings if f['severity']=='HIGH')} high / "
        f"{sum(1 for f in findings if f['severity']=='MEDIUM')} medium)",
        "",
        "## ENGAGEMENT & RULES OF ENGAGEMENT",
        f"| Field | Value |",
        f"|---|---|",
        f"| Client | {_or(eng.get('client'))} |",
        f"| Contact | {_or(eng.get('contact'))} |",
        f"| Authorization ref | {_or(eng.get('authorization_ref'))} |",
        f"| In scope | {scope_in} |",
        f"| Out of scope | {scope_out} |",
        f"| Intensity | {_or(roe.get('intensity'))} |",
        f"| Timing window | {_or(roe.get('timing_window'))} |",
        f"| Do-not-exploit mode | {_or(str(roe.get('do_not_exploit', 'NOT RECORDED')))} |",
        f"| Max request rate | {_or(str(roe.get('max_request_rate', 'NOT RECORDED')))} /min |",
        *(_egress_line()),
        *(_identity_line()),
        *(_profile_line()),
        f"| Operator / Agent | LO / VOIDFORGE |",
        f"| Generated | {ts} |",
        "",
        "> ⚠️ If Authorization ref reads NOT RECORDED, this report documents an",
        "> engagement without recorded mandate and must not be delivered to a client.",
        "",
    ]

    if findings:
        lines += ["## FINDINGS (severity-ranked)", ""]
        for f in findings:
            lines.append(f"- **[{f['severity']}]** `{f['evidence']}`\n  - context: `{f['context']}`")
        if suppressed:
            lines.append(f"- [+{suppressed} additional findings suppressed]")
        lines.append("")

    if ledger:
        lines += ["## ARSENAL LEDGER", ""]
        lines += [f"- `{name}` ×{n}" for name, n in ledger]
        lines.append("")

    # ── Living Graph section: the engagement's actual knowledge state ──
    if board is not None:
        try:
            st = board.stats()
            lines += [f"## LIVING GRAPH — {st['assets']} assets / {st['edges']} links "
                      f"/ {st['tested']} tested observations", ""]
            cov = board.coverage()
            if cov:
                lines += ["| Surface | Tested | Total |", "|---|---|---|"]
                for kind, c in sorted(cov.items()):
                    lines.append(f"| {kind} | {c['tested']} | {c['total']} |")
                lines.append("")
            conns = board.unmade_connections(6)
            if conns:
                lines += ["### Unmade connections (next-mission lead list)", ""]
                for c in conns:
                    lines.append(f"- [{c['confidence']:.0%}] {c['suggestion']} — *{c['why']}*")
                lines.append("")
            top = sorted(board.assets.values(), key=lambda a: -a["confidence"])[:8]
            if top:
                lines += ["### Highest-confidence assets", ""]
                for a in top:
                    lines.append(f"- **[{a['kind']}]** `{a['value'][:90]}` ({a['confidence']})")
                lines.append("")
        except Exception as ex:
            lines += [f"_(living graph render failed: {type(ex).__name__})_", ""]

    lines += ["## FULL TRANSCRIPT (evidence)", ""]
    for kind, text in transcript:
        icon = "🧠" if kind == "agent" else "⚙"
        lines.append(f"\n### {icon} {kind.upper()}\n```\n{(text or '')[:8000]}\n```")

    # scrub opérateur : hostname/username/IPs locales/URLs d'egress ne
    # partent JAMAIS dans le livrable client (une passe, idempotent)
    try:
        from core.scrub import scrub as _scrub
        full = _scrub("\n".join(lines))
    except Exception:
        full = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(full)
    return path
