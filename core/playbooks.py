"""VOIDFORGE :: Skills distillery — playbooks learned from every mission.

After each mission, `learn()` extracts which tool sequences actually produced
results, fingerprints the target stack, and stores a playbook. Future missions
whose text matches a stored stack get the playbook injected into the swarm's
specialist briefs — the monster compounds knowledge across engagements.

Storage: data/playbooks.json  (list of playbook dicts, newest first)
"""
import json, os, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYBOOKS_FILE = os.path.join(ROOT, "data", "playbooks.json")
_lock = threading.Lock()
MAX_PLAYBOOKS = 60


def _load():
    try:
        with open(PLAYBOOKS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(pbs):
    try:
        os.makedirs(os.path.dirname(PLAYBOOKS_FILE), exist_ok=True)
        tmp = PLAYBOOKS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pbs[:MAX_PLAYBOOKS], f, ensure_ascii=False, indent=1)
        # R2-4 : os.replace échoue sous Windows si un lecteur tient le fichier —
        # retry court (3× 0.2s) puis alerte visible ; plus jamais d'échec silencieux.
        for attempt in range(3):
            try:
                os.replace(tmp, PLAYBOOKS_FILE)
                return
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.2)
        print("[playbooks] WARN: playbook non persisté — "
              "playbooks.json tenu par un lecteur concurrent")
    except Exception as e:
        print(f"[playbooks] WARN: échec de sauvegarde des playbooks: {e}")


STACK_KEYWORDS = {
    "supabase": ["supabase", "anon_key", "postgrest"],
    "spa": ["spa", "bundle", "js"],
    "graphql": ["graphql"],
    "telegram": ["telegram", "tg"],
    "wordpress": ["wp-admin", "wordpress", "xmlrpc"],
    "cloudflare": ["cloudflare", "waf"],
    "jwt_auth": ["jwt", "auth", "token"],
}


def _fingerprint(mission, board=None):
    """Cheap stack fingerprint: which keyword families appear in mission/intel."""
    text = (mission or "").lower()
    if board is not None:
        try:
            text += json.dumps(board.stats()).lower() + \
                " ".join(a["value"].lower()[:60] for a in board.assets.values())[:2000]
        except Exception:
            pass
    return sorted({name for name, kws in STACK_KEYWORDS.items()
                   if any(k in text for k in kws)})


def learn(mission, transcripts, board):
    """Extract a playbook from a finished mission (transcripts = {role: transcript})."""
    seq = []
    for role, tr in (transcripts or {}).items():
        for kind, text in tr:
            if kind.endswith("tool") or kind == "tool":
                name = text.split(":", 1)[0].strip()
                if name and (not seq or seq[-1] != name):
                    seq.append(name)
    if len(seq) < 3:
        return None
    pb = {
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "target": board.target,
        "stacks": _fingerprint(mission, board),
        "sequence": seq[:14],
        "assets_found": board.stats()["assets"],
    }
    with _lock:
        pbs = _load()
        # dedupe: same target+sequence shape -> refresh timestamp only
        sig = (pb["target"], tuple(pb["sequence"][:10]))
        pbs = [p for p in pbs if (p.get("target"), tuple(p.get("sequence", [])[:10])) != sig]
        pbs.insert(0, pb)
        _save(pbs)
    return pb


def prompt_block(mission, board=None, limit=2):
    """Relevant playbooks rendered for prompt injection (may be empty)."""
    pbs = _load()
    if not pbs:
        return ""
    fp = set(_fingerprint(mission, board))
    # fall back to mission-text-only fingerprint when no board given
    scored = []
    for p in pbs:
        overlap = len(fp & set(p.get("stacks", [])))
        scored.append((overlap, p))
    scored = [s for s in scored if s[0] > 0][:limit]
    if not scored:
        return ""
    lines = ["PLAYBOOKS FROM PAST MISSIONS (tool sequences that produced results on similar stacks):"]
    for score, p in scored:
        lines.append(f"- [{p['ts']} on {p['target']}] {' → '.join(p['sequence'][:10])}")
    return "\n".join(lines)
