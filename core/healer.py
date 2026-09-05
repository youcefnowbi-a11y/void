"""VOIDFORGE :: SELF-HEALING EXECUTOR
Classifies tool failures, applies learned fixes, persists new fixes forever.
The organism never blocks twice on the same wound."""
import json, os, re, time, threading

HERE = os.path.dirname(os.path.abspath(__file__))
FIXES_FILE = os.path.join(HERE, "learned_fixes.json")
# wave-2-A deadlock fix: _rmw holds the lock across _save_fixes which
# re-acquires it — Lock is non-reentrant, RLock is the contract.
_FIXES_LOCK = threading.RLock()  # swarm threads share this file — no lost updates

def _load_fixes():
    try:
        d = json.load(open(FIXES_FILE, encoding="utf-8"))
        # learned_fixes.json édité à la main → on ne fait jamais confiance à la shape
        return d if isinstance(d, dict) else {"error_signatures": {},
                                              "tool_flag_migrations": {}}
    except Exception:
        return {"error_signatures": {}, "tool_flag_migrations": {}}

def _save_fixes(data):
    # final-audit fix #7: tmp + os.replace (atomic) — a crash mid-write
    # left a corrupt file that _load_fixes swallowed as an EMPTY
    # skeleton, so the next learn_* rewrote the file with ONLY the new
    # entry (silent permanent wipe of every learned fix).
    with _FIXES_LOCK:
        _tmp = FIXES_FILE + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(_tmp, FIXES_FILE)

def _rmw(fn):
    """final-audit fix #7 (cont.): the whole read-modify-write under the
    lock — learn_* read OUTSIDE it, so concurrent swarm threads lost
    each other's updates."""
    with _FIXES_LOCK:
        data = _load_fixes()
        out = fn(data)
        _save_fixes(data)
        return out

def classify(error_text):
    """Returns (category, details)."""
    e = str(error_text).lower()
    if "flag provided but not defined" in e or "unknown flag" in e or "no help topic" in e:
        bad = re.search(r'flag provided but not defined:\s*(-?[\w\-]+)', e)
        return ("FLAG_RENAMED", {"bad_flag": bad.group(1) if bad else None})
    if "modulenotfounderror" in e or "not installed" in e or ("pip install" in e and "import" in e):
        mod = re.search(r"[Mm]odule[Nn]ot[Ff]ound[Ee]rror:\s*(?:No module named\s+)?'?([A-Za-z0-9_]+)'?", str(error_text))
        return ("DEP_MISSING", {"module": mod.group(1) if mod else None})
    if "timeout" in e or "timed out" in e:
        return ("TIMEOUT", {})
    if any(k in e for k in ("getaddrinfo", "connection reset", "err 11001", "unreachable", "10054")):
        return ("NETWORK", {})
    if "expired" in e and "jwt" in e or "invalid or expired token" in e:
        return ("AUTH_EXPIRED", {})
    if re.search(r"\b401\b", e) or "missing authorization" in e or "unauthorized" in e:
        return ("AUTH_REQUIRED", {})
    if "no such file" in e or "filenotfounderror" in e or "not a file" in e or "isfile" in e:
        return ("FILE_EXPECTED", {})
    if "playwright" in e or "chromium" in e or "executable doesn't exist" in e or "browser type" in e:
        return ("BROWSER_MISSING", {})
    return ("UNKNOWN", {})

def get_learned_fix(tool_name, category):
    data = _load_fixes()
    return (data.get("tool_flag_migrations") or {}).get(tool_name), \
           (data.get("error_signatures") or {}).get(f"{tool_name}:{category}")

def learn_flag_migration(tool_name, old_flag, new_flag):
    def _apply(data):
        data.setdefault("tool_flag_migrations", {})[tool_name] = {
            "from": old_flag, "to": new_flag,
            "learned_at": time.strftime("%Y-%m-%d %H:%M")}
    _rmw(_apply)

def learn_generic(tool_name, category, fix_description):
    # final-audit fix #8: write-only memory gated — only NOVEL
    # signatures churn the file; a re-observed deterministic wound no
    # longer re-timestamps its entry every mission.
    def _apply(data):
        sigs = data.setdefault("error_signatures", {})
        key = f"{tool_name}:{category}"
        if sigs.get(key, {}).get("fix") != fix_description:
            sigs[key] = {
                "fix": fix_description,
                "learned_at": time.strftime("%Y-%m-%d %H:%M")}
    _rmw(_apply)

def heal_attempt(tool_name, category, details, original_args):
    """Returns patched args if a healing strategy exists, else None."""
    # final-audit fix #8: consult the learned error_signatures FIRST —
    # the store was write-only memory (nothing read it), so the "never
    # blocks twice on the same wound" contract was unimplemented.
    try:
        sig = get_learned_fix(tool_name, category)[1]
        if isinstance(sig, dict) and sig.get("fix"):
            # a stored fix exists for this exact wound — surface it to
            # the caller (the heal notes ride the tool result) even when
            # no category strategy below applies
            _sig_note = f"learned fix on record: {str(sig['fix'])[:200]}"
        else:
            _sig_note = None
    except Exception:
        _sig_note = None
    if category == "FLAG_RENAMED":
        # try learned migration first
        mig = (_load_fixes().get("tool_flag_migrations") or {}).get(tool_name)
        if mig and isinstance(original_args, dict):
            fixed = False
            new_args = {}
            for k, v in original_args.items():
                kk = k
                if k == mig.get("from","").lstrip("-"):
                    kk = mig.get("to","").lstrip("-"); fixed = True
                # final-audit fix #10: a rename collision used to
                # silently clobber a pre-existing arg of the same name.
                if kk != k and kk in new_args:
                    return None, f"rename collision: {kk} already present"
                new_args[kk] = v
            if fixed:
                return new_args, f"applied learned migration {mig['from']} -> {mig['to']}"
            # generic: drop the offending boolean-style flag key entirely is wrong for args-dict;
            # instead signal caller to mutate command construction.
        return None, "flag rename without learned mapping"
    if category == "TIMEOUT":
        a = dict(original_args or {})
        # Ne muter QUE si l'outil accepte déjà ce paramètre, sinon on
        # provoquerait un TypeError worse que la panne initiale.
        if "timeout_min" in a:
            a["timeout_min"] = int(a["timeout_min"]) * 2
            return a, "doubled timeout"
        return dict(a), "plain retry (no timeout knob)"
    if category == "NETWORK":
        # WF1 (audit-2 F1): a 4s sleep froze the whole specialist thread
        # × 3 attempts = 12s dead per blip in swarm mode. 1.2s is still a
        # real backoff for a transient reset without the paralysis.
        time.sleep(1.2)
        return original_args, "retry after backoff"
    if category == "FILE_EXPECTED":
        # L'agent a passé une URL là où l'outil veut un fichier local :
        # télécharger la ressource et réessayer avec le chemin local.
        a = dict(original_args or {})
        target = next((v for k, v in a.items() if isinstance(v, str) and v.lower().startswith(("http://", "https://"))), None)
        if target is not None:
            try:
                from tools.fetch_local import ensure_local
                local, note = ensure_local(target, suffix=".js")
                if local != target:
                    for k in a:
                        if a[k] == target:
                            a[k] = local
                    return a, f"URL->local ({note})"
                else:
                    return None, f"URL->local failed ({note})"
            except Exception as ex:
                return None, f"URL->local error ({type(ex).__name__})"
        return None, "no http(s) URL in args to fetch"
    if category == "BROWSER_MISSING":
        return None, "browser engine unavailable — advise agent to use request-based tool"
    return None, (_sig_note or "")
