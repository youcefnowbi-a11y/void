"""VOIDFORGE :: Tool registry - auto-discovers tool modules in this package.
A tool module defines: TOOL = {name, desc, params(json-schema), danger}
and an async or sync run(args) -> str result."""
import importlib, ipaddress, pkgutil, re, traceback, sys, os, json, threading

_CURRENT_EVENT = None  # event emitter visible to nested dispatch (batch inner tools)
_thread_state = threading.local()
# A2 : périmètre d'outils hérité — posé par execute() sur le thread appelant,
# lu par batch_execute pour ses appels internes. Sans ça, batch bypass tous
# les filtres (plan-mode recon-only, arsenaux de rôles) : la clôture était
# prompt-enforced seulement.
allowed = threading.local()


def current_allowed():
    return getattr(allowed, 'names', None)

def get_current_event():
    return getattr(_thread_state, 'current_event', None)

_REGISTRY = {}
_DISCOVERED = False  # tracks that discovery RAN, separate from registry size —
                     # partial imports (e.g. `from tools.js_mine import ...`)
                     # must never block full discovery of the other modules.

# Schema-healing: the LLM's call accuracy is a direct function of parameter
# descriptions. Any tool property registered without one gets a synthesized
# doc here — every tool, present and future, ships LLM-ready schemas.
_DEFAULT_PARAM_DOCS = {
    "url": "Target URL", "url_template": "URL with {INJ} placeholder where the payload is injected",
    "base": "Base URL of the target service", "base_url": "Provider base URL (OpenAI-compatible)",
    "url_template_cmd": "URL with {INJ} where the command is injected",
    "domain": "Target domain (no scheme)", "site": "Target site URL", "path": "File or folder path",
    "har_path": "Path to a .har capture file", "js_path": "Path to the JS bundle",
    "target": "Target URL or domain", "keyword": "Search keyword",
    "token": "Auth token (JWT/Bearer)", "anon_key": "Anon/public API key",
    "handles": "List of @handles to probe", "handle": "One @handle",
    "channel": "Telegram channel name", "timeout": "Timeout in seconds",
    "timeout_min": "Timeout in minutes", "limit": "Max items to process",
    "max_rows": "Max rows to extract", "max_chars": "Max characters to extract",
    "max_requests": "Max requests to send (budget)", "delay_ms": "Delay between requests (ms)",
    "codes": "Candidate codes to try", "code_regex": "Regex to extract codes",
    "cmd": "Command to execute on the target", "commands": "Commands to run through the shell",
    "separator": "OS command separator that worked in cmd_exec_probe",
    "os_flavor": "Target OS: auto/unix/win", "blind": "Timing-oracle only, skip output capture",
    "start": "First id of the enumeration range", "stop": "Last id of the enumeration range",
    "step": "Step between ids", "pad": "Zero-pad width for ids",
    "variant": "Identifier encoding variant", "subquery": "Scalar SQL subquery to extract",
    "dbms": "Database engine (auto-detected when omitted)", "table": "Table to dump",
    "columns": "Columns to extract", "payload": "Payload value", "paths": "Endpoint paths to probe",
    "fields": "Form fields dict", "file_field": "Multipart file field name",
    "upload_url": "Multipart upload endpoint", "base_uploads_url": "URL where uploads are served",
    "shell_url": "Confirmed webshell URL", "param": "Parameter carrying the command",
    "shell_source": "Custom shell code", "candidates": "Filenames to restrict attempts to",
    "claims_override": "JWT claims to overwrite (e.g. role)", "public_key_pem": "Server RSA public key (PEM)",
    "hmac_secret": "Known HMAC secret for signing", "replay_url": "Endpoint where the forged token is tested",
    "auth_header": "Header carrying the token", "cve_id": "CVE identifier (CVE-YYYY-NNNNN)",
    "verify_url": "Target URL to test the PoC against", "execute": "Run the downloaded PoC (operator decision)",
    "headers": "HTTP headers dict", "params": "Seed parameters dict", "target_param": "Fuzz only this parameter",
    "email_domain": "Domain for the disposable email", "email": "Email address",
    "password": "Password", "pages": "Pages to scrape", "group": "Telegram group",
    "session_path": "Telethon .session file path", "api_id": "Telegram API id",
    "api_hash": "Telegram API hash", "top": "How many results to return",
    "results": "Max results", "collapse": "Collapse wayback variants",
    "action": "Snapshot action", "snapshot_file": "Snapshot file to compare",
    "out_dir": "Output directory", "max_index": "Max string-table index",
    "keyword_filter": "Only keep strings matching", "mode": "Scan mode",
    "ports": "Ports to scan", "host": "Target host", "ip_or_host": "IP or hostname",
    "wordlist": "Path to a wordlist", "method": "HTTP method",
    "extra_params": "Extra request parameters", "bearer": "Bearer token",
    "duration_s": "Capture duration in seconds", "tables": "Tables to watch",
    "tables_probe": "Candidate table names", "wait_s": "Wait before capture (s)",
    "max_file_mb": "Max file size (MB)", "identity_only": "Return identities only",
    "calls": "List of {tool, args} calls to run in parallel", "max": "Max items",
    "brand_queries": "Brand-related search queries", "success_pattern": "Success marker in the response",
    "baseline_value": "Neutral baseline parameter value", "note": "Free-form note",
}

def _heal_schema(params):
    """Ensure an LLM-ready object schema: type=object, properties dict,
    required ⊆ properties, and a description on EVERY property (recursing
    into array-item object schemas too)."""
    if not isinstance(params, dict):
        params = {"type": "object", "properties": {}}
    params.setdefault("type", "object")
    props = params.setdefault("properties", {})
    for k, v in props.items():
        if not isinstance(v, dict):
            props[k] = v = {"type": "string"}
        if not v.get("description"):
            v["description"] = _DEFAULT_PARAM_DOCS.get(
                k, k.replace("_", " ") + " (see tool description)")
        items = v.get("items")
        if isinstance(items, dict) and items.get("type") == "object":
            _heal_schema(items)
    req = params.setdefault("required", [])
    params["required"] = [r for r in req if r in props]
    return params

def register(name, desc, params, danger="safe"):
    params = _heal_schema(params)
    def deco(fn):
        _REGISTRY[name] = {"name": name, "desc": desc, "params": params,
                           "danger": danger, "run": fn}
        return fn
    return deco

def discover():
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    global _LOAD_FAILURES
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_") or m.name == "__init__" or m.name.startswith("forged_"):
            continue
        try:
            importlib.import_module(f"tools.{m.name}")
        except Exception as e:
            _LOAD_FAILURES.append(f"{m.name}: {str(e)[:120]}")
            print(f"[registry] failed to load tools.{m.name}: {e}")


_LOAD_FAILURES: list = []  # R3-19: l'arsenal amputé doit être VISIBLE

def unavailable_modules():
    """Modules qui ont échoué à l'import au discover — diagnostics admin."""
    return list(_LOAD_FAILURES)

def all_tools():
    discover()
    return list(_REGISTRY.values())

def get(name):
    discover()
    t = _REGISTRY.get(name)
    if not t:
        raise KeyError(f"unknown tool: {name}")
    return t

def _coerce_args(schema_props, args):
    """LLM-argument type coercion — models stringify objects/numbers; the
    tools must not die for it. Coerces per the tool's own JSON schema."""
    if not isinstance(args, dict):
        return args
    for k, spec in (schema_props or {}).items():
        if k not in args:
            continue
        v = args[k]
        want = (spec or {}).get("type")
        if want == "boolean":
            # R3-32: coercions réversibles et explicites — l'ancien one-liner
            # transformait "confirm"/"enabled" en False SILENCIEUSEMENT (le
            # flag execute des PoC s'inversait sans erreur). Une string non
            # reconnue reste telle quelle: le LLM voit sa valeur et se corrige.
            if isinstance(v, str):
                lv = v.strip().lower()
                if lv in ("1", "true", "yes", "y", "on"):
                    args[k] = True
                elif lv in ("0", "false", "no", "n", "off"):
                    args[k] = False
            elif isinstance(v, (int, float)) and v in (0, 1):
                args[k] = bool(v)
        else:
            try:
                if want == "integer" and isinstance(v, str):
                    args[k] = int(v.strip())
                elif want == "number" and isinstance(v, str):
                    args[k] = float(v.strip())
                elif want in ("object", "array") and isinstance(v, str):
                    s = v.strip()
                    if s[:1] in "{[":
                        args[k] = json.loads(s)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
    return args


def _load_roe():
    """Rules of engagement from config/engagement.yaml — previously read by
    report.py only. Now they actually gate execution."""
    try:
        import yaml as _y
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "engagement.yaml")
        with open(p, encoding="utf-8") as f:
            d = _y.safe_load(f) or {}
        return (d.get("engagement") or {}).get("rules_of_engagement") or {}
    except Exception:
        return {}


# ── G13 (wave2): scope guard par ARGUMENT — le gouverneur ROE cadence le
# débit; celui-ci valide les DESTINATIONS. Un LLM qui hallucine un host hors
# périmètre est bloqué AVANT l'exécution. PentAGI scope_check_protocol, adapté.
_URL_RX = re.compile(r"https?://([^/\"'\s>]+)", re.I)
_HOST_KEYS = ("host", "hostname", "domain", "target", "base", "url", "base_url")


def _load_scope():
    try:
        import yaml as _y
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "engagement.yaml")
        with open(p, encoding="utf-8") as f:
            d = _y.safe_load(f) or {}
        return ((d.get("engagement") or {}).get("scope") or {})
    except Exception:
        return {}


# R3-11: dernier état bon du scope/ROE — si engagement.yaml devient corrompu
# ou disparaît EN COURS de mission, on sert le dernier contenu connu au lieu
# de repartir sans gouverneur (fail-open). Au boot sans fichier: {}, comme avant.
_LAST_GOOD_SCOPE = {}
_LAST_GOOD_ROE = {}


def _load_scope_cached():
    global _LAST_GOOD_SCOPE
    scope = _load_scope()
    if scope and (scope.get("in_scope") or []):
        _LAST_GOOD_SCOPE = scope
        return scope
    return _LAST_GOOD_SCOPE  # corrupted yaml → last known good governs


def _load_roe_cached():
    global _LAST_GOOD_ROE
    roe = _load_roe()
    if roe:
        _LAST_GOOD_ROE = roe
        return roe
    return _LAST_GOOD_ROE


def _host_allowed(host, scope):
    """Local/privé toujours permis; sinon suffix-match in_scope, refus si
    out_of_scope matche. pattern '*' = tout permis."""
    in_s = [str(p).lower() for p in (scope.get("in_scope") or [])]
    out_s = [str(p).lower() for p in (scope.get("out_of_scope") or [])]
    host = (host or "").lower().strip().rstrip(".")
    if not host:
        return True
    if host in ("localhost",) or host.endswith((".local", ".internal", ".test")):
        return True
    try:
        import ipaddress as _ip
        ip = _ip.ip_address(host.split(":")[0] if ":" in host else host)
        if ip.is_private or ip.is_loopback:
            return True
    except ValueError:
        pass
    for pat in out_s:
        if pat != "*" and (host == pat or host.endswith("." + pat.lstrip("*."))):
            return False
    if "*" in in_s:
        return True
    return any(host == p or host.endswith("." + p.lstrip("*.")) for p in in_s
               if p and p != "*")


def _scope_check(args, scope=None):
    """TOOL ERROR string si une destination d'args sort du périmètre — sinon None."""
    scope = scope if scope is not None else _load_scope()
    if not scope or not (scope.get("in_scope") or []):
        return None  # pas de périmètre défini → pas de garde (comportement actuel)
    hosts = set()
    blob = json.dumps(args or {}, default=str)
    for m in _URL_RX.finditer(blob):
        hosts.add(m.group(1).split(":")[0])
    for k, v in (args or {}).items():
        if any(kk in k.lower() for kk in _HOST_KEYS) and isinstance(v, str):
            v = v.strip()
            if v.startswith("http"):
                m = _URL_RX.search(v)
                if m:
                    hosts.add(m.group(1).split(":")[0])
            else:
                # R3-13: les IPs nues doivent traverser la garde — l'ancienne
                # regex exigeait un TLD alphabétique donc "8.8.8.8" n'était
                # JAMAIS extrait ni vérifié contre le périmètre.
                _cand = None
                for _try in (v.strip("[]"), v.split(":")[0].strip("[]")):
                    try:
                        ipaddress.ip_address(_try)
                        _cand = _try
                        break
                    except ValueError:
                        continue
                if _cand:
                    hosts.add(_cand)
                elif re.match(r"^[a-z0-9][a-z0-9.\-]*\.[a-z]{2,}$", v, re.I):
                    hosts.add(v.split(":")[0])
    for h in hosts:
        if not _host_allowed(h, scope):
            return (f"TOOL ERROR [SCOPE_BLOCKED]: la cible '{h}' est HORS PÉRIMÈTRE "
                    f"(in_scope={scope.get('in_scope')}, out_of_scope={scope.get('out_of_scope')}). "
                    "Ne teste que les cibles du périmètre — enregistre le host découvert "
                    "comme candidate-finding sans le sonder.")
    return None


def execute(name, args, on_event=None):
    t = _REGISTRY.get(name) if _DISCOVERED else None
    if t is None:
        discover()
        t = _REGISTRY.get(name)
    if t is None:
        # NEVER crash the mission on a hallucinated tool name — return a
        # corrective message the LLM reads as a tool result and self-corrects.
        import difflib
        all_names = sorted(_REGISTRY.keys())
        close = difflib.get_close_matches(name, all_names, n=3, cutoff=0.5)
        err = (f"TOOL ERROR [UNKNOWN_TOOL]: '{name}' does not exist in the arsenal. "
               f"Known tools: {', '.join(all_names[:60])}."
               + (f" Closest matches: {', '.join(close)} — did you mean one of those?" if close else "")
               + (f" Modules indisponibles (échec import): {', '.join(_LOAD_FAILURES)}." if _LOAD_FAILURES else ""))
        if on_event:
            on_event({"type": "tool_error", "tool": name, "error": err[:300],
                      "category": "UNKNOWN_TOOL", "duration": 0.0})
        return err
    # ── wave3 Dark-Moon: restaurer les identités réelles AVANT les gates —
    # les args peuvent arriver tokenisés ([HOST-7]) depuis le LLM; le coffre
    # local les remet. Un seul point de passage (agent + chat + batch), et le
    # scope guard G13 voit les vraies destinations, pas des jetons.
    try:
        from core import _tokenize as _tk
        if _tk.enabled():
            args = _tk.unmask_obj(args)
    except Exception:
        pass
    # A2 : un appel d'un agent à périmètre restreint (plan-mode, rôle swarm)
    # propage son arsenal — batch_execute le relira pour ses appels internes.
    # L'appel externe qui frappe hors périmètre reçoit le même refus que le
    # registre aurait donné au modèle.
    _allowed_here = current_allowed()
    if _allowed_here is not None and name not in _allowed_here:
        err = (f"TOOL ERROR [SCOPE_TOOL]: '{name}' n'est pas dans l'arsenal "
               f"autorisé de cet agent ({len(_allowed_here)} outils). "
               f"Reste dans ton rôle / ton plan.")
        if on_event:
            on_event({"type": "tool_error", "tool": name, "error": err[:300],
                      "category": "SCOPE_TOOL", "duration": 0.0})
        return err

    # ── Rules of Engagement, enforced for real (F10) ──
    roe = _load_roe_cached()
    # F-1/R3-27: fail-closed — TOUT sauf "safe" est bloqué (loud/active/
    # careful/strike + label manquant). L'ancienne blocklist ("loud","danger",
    # "strike") laissait passer 24 outils "active"/"careful" sous
    # do_not_exploit=true, et "danger" n'existe même pas au registre.
    if roe.get("do_not_exploit") and t.get("danger") != "safe":
        err = ("ROE: do_not_exploit=true — outil offensif (danger="
               f"{t.get('danger') or 'non classé'}) bloqué par les règles "
               "d'engagement. Recon only — enregistre le finding sans frapper.")
        if on_event:
            on_event({"type": "tool_error", "tool": name, "error": err[:300],
                      "category": "ROE_BLOCKED", "duration": 0.0})
        return err
    # ── G13: scope guard par argument (wave2) ──
    scope_err = _scope_check(args, scope=_load_scope_cached())
    if scope_err:
        if on_event:
            on_event({"type": "tool_error", "tool": name, "error": scope_err[:300],
                      "category": "SCOPE_BLOCKED", "duration": 0.0})
        return scope_err
    args = _coerce_args((t.get("params") or {}).get("properties"), args)
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:  # F-3/R3-33: dédup — plus de sys.path qui gonfle
        sys.path.insert(0, _root)  # à chaque appel d'outil
    from core import healer
    import time as _t
    # R3-24/R3-34: emitter = thread-local SEUL — le fallback global cross-mission
    # croisait les émetteurs de deux execute() sur threads différents (events
    # cross-mission). batch_execute capture le thread-local de son thread
    # d'origine et le repasse explicitement à chaque inner call.
    curr = getattr(_thread_state, 'current_event', None)
    nested = curr is not None
    emitter = on_event or (curr if nested else None)
    if not nested:
        _thread_state.current_event = on_event
    try:
        attempts = 0
        if emitter:
            emitter({"type": "tool_start", "tool": name, "args": args or {}})
        _start = _t.time()
        while attempts < 3:
            attempts += 1
            # R3-12: les args peuvent avoir été réécrits depuis le premier gate
            # (coercion, heal qui swappe un URL vers un path local) — re-valide
            # les DESTINATIONS avant CHAQUE exécution, jamais de run non-checké.
            scope_err = _scope_check(args, scope=_load_scope_cached())
            if scope_err:
                if emitter:
                    emitter({"type": "tool_error", "tool": name, "error": scope_err[:300],
                             "category": "SCOPE_BLOCKED", "duration": 0.0})
                return scope_err
            try:
                # A2 : le périmètre est visible pendant le run de l'outil —
                # batch_execute le capture et le ré-applique à ses workers ;
                # save/restore pour le nesting propre (outer garde le sien).
                _prev_allowed = current_allowed()
                allowed.names = _allowed_here
                try:
                    out = t["run"](**(args or {}))
                finally:
                    allowed.names = _prev_allowed
                if not isinstance(out, str):
                    out = json.dumps(out, ensure_ascii=False, default=str)
                # archive-grade cap: 20KB coupait les JSON en plein milieu
                # (batch_execute de 5 résultats, cartes d'arsenal) → le modèle
                # recevait du JSON cassé. 60KB laisse l'archive vivre; le
                # formatage fin pour le chat est le travail de _feed_result.
                out = out[:60000]
                # chain hints (self-guiding arsenal): producer output announces
                # its consumers — cost zero at prompt level, appended at runtime
                try:
                    from tools._hints import hint_for
                    _hint = hint_for(name, out)
                    if _hint and len(out) < 55000:  # hint survives the 60k cap
                        out = out + _hint
                except Exception:
                    pass
                # E2 vault: count the use (skills count at load, plays at
                # harvest; forged tools count HERE — best-effort, never
                # lets a metric fail a strike). session_keep: first mint
                # of a mission is the learnable gesture.
                if name.startswith("forged_") or name == "session_keep":
                    try:
                        from core.capability_vault import touch
                        touch("forged", name)
                    except Exception:
                        pass
                dur = round(_t.time() - _start, 2)
                if emitter:
                    emitter({"type": "tool_result", "tool": name, "result": out[:2000],
                             "duration": dur, "status": "ok"})
                return out
            except Exception:
                err = traceback.format_exc()
            # SELF-HEALING LAYER
            category, details = healer.classify(err)
            # V16 (audit 6.x): a heal that returns THE SAME args re-runs
            # the identical call and hits the identical crash — 3 attempts
            # burned on one deterministic wound (the mission-79
            # crash-loop). Same-args retry is only legitimate for
            # TRANSIENT categories (network blip, saturation timeout).
            _transient = category in ("NETWORK", "TIMEOUT")
            healed_args, note = healer.heal_attempt(name, category, details, args)
            if healed_args == args and not _transient:
                healed_args = None
                note = "sterile heal rejected (same args, deterministic error)"
            if healed_args is not None:
                print(f"  [healer] {category} -> {note} (attempt {attempts})")
                if emitter:
                    emitter({"type": "tool_heal", "tool": name, "category": category,
                             "note": note, "attempt": attempts})
                args = healed_args
                continue
            healer.learn_generic(name, category, f"unhealed {category}: {str(details)[:80]}")
            dur = round(_t.time() - _start, 2)
            err_msg = f"TOOL ERROR [{category}] after self-heal attempts ({attempts}):\n{err[-1200:]}"
            if emitter:
                emitter({"type": "tool_error", "tool": name, "error": err_msg[:500],
                         "category": category, "duration": dur})
            return err_msg
        return "TOOL ERROR: exhausted healing rounds"
    finally:
        if not nested:
            _thread_state.current_event = None

