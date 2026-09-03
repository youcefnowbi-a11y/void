"""VOIDFORGE :: skill layer — composed expertise for the operator model.

Tools are verbs. Skills are the doctrine of ten campaigns: when to strike,
in what order, which payload variant, what to do when the wall pushes back.
Each skill is a markdown file in skills/ with a structured header:

    # skill: <id>
    title: <human title>
    when: comma,separated,lowercase,trigger,keywords
    not_when: comma,separated,exclusions          (optional)
    tier: core|domain|library                     (optional, default core)

The loader selects skills whose WHEN-keywords match the mission text and
injects the full playbooks into the model's context. The model can also
pull any skill mid-mission via the skill_load tool.

Routing model (reverse-skill inspired, kept 200x lighter):
- only `core` skills participate in auto-match at mission start; `domain`
  and `library` skills are reachable via skill_list/skill_load (no dilution
  as the library grows);
- `not_when:` is an absolute veto: a skill whose exclusion keyword hits the
  mission text is never injected, even when `when:` matches (their
  anti-collision pattern: "jailbreak" iOS vs "jailbreak" LLM);
- injection is PRIMARY (best match, full playbook) + secondaries as a
  one-line pointer list, with a confidence marker (hits count).
Legacy skills without tier/not_when keep the old routing model, except
that ASCII keywords now use R1-1 underscore-boundary lookarounds in _hits
(a mild narrowing vs the pre-R1-1 substring match).
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "skills")
SKILL_CAP = 14000  # max chars of skill text injected per mission
_PRIMARY_CAP = 6000

_HDR = re.compile(r"^# skill:\s*(\S+)\s*$", re.M)
_TITLE = re.compile(r"^title:\s*(.+)$", re.M)
_WHEN = re.compile(r"^when:\s*(.+)$", re.M)
_NOT_WHEN = re.compile(r"^not_when:\s*(.+)$", re.M)
_TIER = re.compile(r"^tier:\s*(\S+)\s*$", re.M)

_VALID_TIERS = ("core", "domain", "library")


def _parse(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None
    mid = _HDR.search(text)
    if not mid:
        return None
    mt = _TITLE.search(text)
    mw = _WHEN.search(text)
    when = [w.strip().lower() for w in (mw.group(1).split(",") if mw else []) if w.strip()]
    mnw = _NOT_WHEN.search(text)
    not_when = [w.strip().lower() for w in (mnw.group(1).split(",") if mnw else []) if w.strip()]
    mtier = _TIER.search(text)
    tier = (mtier.group(1).strip().lower() if mtier else "core")
    if tier not in _VALID_TIERS:
        tier = "core"
    return {"id": mid.group(1), "title": (mt.group(1).strip() if mt else mid.group(1)),
            "when": when, "not_when": not_when, "tier": tier,
            "path": path, "text": text}


def list_skills():
    out = []
    if not os.path.isdir(SKILLS_DIR):
        return out
    for fn in sorted(os.listdir(SKILLS_DIR)):
        if fn.endswith(".md"):
            s = _parse(os.path.join(SKILLS_DIR, fn))
            if s:
                out.append(s)
    return out


def load_skill(skill_id):
    for s in list_skills():
        if s["id"] == skill_id:
            # E2 vault: count the load (best-effort — a metric never
            # blocks the expertise it measures)
            try:
                from core.capability_vault import touch
                touch("skill", skill_id)
            except Exception:
                pass
            return s["text"][:SKILL_CAP]
    return None


def _hits(words, low):
    # R1-1: frontière underscore pour l'ASCII (le \b simple ne voit pas les _).
    # D-S1: en CJK les lookarounds ne marchent pas — les idéogrammes SONT \w
    # en Unicode Python, donc `越权` ne matchait jamais au milieu de texte CJK
    # (triggers zh morts, vetos not_when CJK contournés). Keyword non-ASCII →
    # substring brut ; keyword ASCII → lookarounds inchangés.
    def _kw_hit(w):
        if w.isascii():
            return re.search(rf"(?<![^\W_]){re.escape(w)}(?![^\W_])", low)
        return w in low
    return sum(1 for w in words if _kw_hit(w))


def select_for(mission_text, limit=3):
    """Rank CORE skills by WHEN-keyword hits against the mission text.
    Skills vetoed by not_when are excluded regardless of score.
    Falls back to web_access_master when the mission names a URL but
    nothing matched — a web target always deserves the access playbook."""
    low = (mission_text or "").lower()
    scored = []
    for s in list_skills():
        if s["tier"] != "core":
            continue
        if _hits(s["not_when"], low) > 0:
            continue
        hits = _hits(s["when"], low)
        if hits > 0:
            scored.append((hits, s["id"]))
    scored.sort(key=lambda t: (-t[0], t[1]))
    ids = [sid for _, sid in scored[:limit]]
    if not ids and re.search(r"https?://|\b[a-z0-9\-]+\.(com|net|org|io|me|dev)\b", low):
        for s in list_skills():
            if s["id"] == "web_access_master" and _hits(s["not_when"], low) == 0:
                ids = ["web_access_master"]
                break
    return ids


def select_block(mission_text, limit=3, cap=SKILL_CAP):
    """Formatted context block: PRIMARY playbook in full, then the other
    matches as a one-line pointer list (the model pulls them on demand via
    skill_load). Confidence is stated so the model knows how much to trust
    the match."""
    ids = select_for(mission_text, limit)
    if not ids:
        return ""
    skills = {s["id"]: s for s in list_skills()}
    primary = skills.get(ids[0])
    if not primary:
        return ""
    confidence = "high" if len(ids) == 1 else "medium"
    primary_txt = primary["text"][:min(_PRIMARY_CAP, cap)]
    related = [i for i in ids[1:] if i in skills]
    parts = [f"[PRIMARY skill: {primary['id']} — confidence: {confidence}]\n{primary_txt}"]
    total = len(parts[0])
    if related:
        pointer = ("[related skills available via skill_load: " + ", ".join(related) + "]")
        parts.append(pointer)
        total += len(pointer)
    if total >= cap:
        parts = [parts[0][:cap]]
    return ("═══ ACTIVE SKILLS (composed expertise — follow the CHAIN, adapt to what "
            "you observe; pull more via skill_load) ═══\n\n"
            + "\n\n═══════════════════════════\n\n".join(parts))
