"""VOIDFORGE :: réversible data tokenization (wave3, pattern Dark-Moon).

Le provider ne voit jamais les identités réelles de la cible : hostnames,
IPs et credentials partent tokenisés ([HOST-7], [CRED-3]) dans les prompts ;
les valeurs réelles vivent dans un coffre local (_VAULT) qui ne quitte JAMAIS
la machine. `unmask()` restaure les valeurs au moment de l'exécution des
outils — la frappe reste 100 % réelle, le raisonnement reste structurel.

CE QUI EST masqué   : hostnames, IPs, credentials (mots de passe/tokens/keys),
                      cookies/valeurs de session sensibles.
CE QUI EST gardé    : paths, params, status codes, fingerprints tech, CVEs,
                      structures de payloads — le carburant du raisonnement.

Config: provider.yaml  provider.tokenize_secrets: true|false (défaut false).
"""
import json, os, re, threading

_LOCK = threading.Lock()
_VAULT = {}          # token -> valeur réelle
_REVERSE = {}        # valeur -> token
_COUNTER = [0]

# ── patterns d'identité ──
_IP_RX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# hostname/domaine: au moins un label + TLD; exclut localhost et les tokens
_DOMAIN_RX = re.compile(
    r"\b(?!(?:localhost|[\w\-]+\.local)\b)"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)+"
    r"(?:com|net|org|io|dev|app|co|fr|de|uk|eu|us|cn|ru|hk|tw|jp|kr|in|br|mx|au|ca|nl|se|ch|info|xyz|shop|bank|site|online|cloud|ai)\b")
# creds dans du JSON/YAML/k=v : les champs qui portent des secrets
_CRED_FIELD_RX = re.compile(
    r"(?i)((?:password|passwd|pwd|secret|token|api[_\-]?key|apikey|authorization|"
    r"cookie|session[_\-]?id|bearer)\s*[\"']?\s*[:=]\s*[\"']?)"
    r"([^\"',}&\n]{6,})")
_URL_CRED_RX = re.compile(
    r"(?i)(?<=://)([^\s/:@]{3,}):([^\s/@]{3,})(?=@)")
# D-T3: longueur min 3+3 sur user/secret — tue le bruit 1-2 chars (et le
# masquage partiel trompeur `p` dans user:p@ss@host). Limitation documentée:
# un secret multi-@ n'est pas parsé (le match s'arrête au premier @ avant un
# suffixe trop court → ligne laissée en clair plutôt que masquée à moitié).


def _classify(value):
    """HOST pour IP/domaine, CRED sinon."""
    return "CRED"


def _issue_token(value, kind):
    with _LOCK:
        if value in _REVERSE:
            return _REVERSE[value]
        _COUNTER[0] += 1
        tok = f"[{kind}-{_COUNTER[0]}]"
        _VAULT[tok] = value
        _REVERSE[value] = tok
        return tok


def mask(text):
    """Tokenize les identités dans un texte destiné au provider."""
    if not text or not isinstance(text, str):
        return text

    def _url_cred_sub(m):
        user, pwd = m.group(1), m.group(2)
        return f"{_issue_token(user, 'CRED')}:{_issue_token(pwd, 'CRED')}"

    def _cred_field_sub(m):
        # R1-2: le séparateur matché (guillemets, : ou =) est réémis tel quel —
        # on ne remplace QUE la valeur, le JSON/YAML reste bien formé.
        # D-T1: la valeur va jusqu'au quote/fin-de-ligne (le JWT après
        # « Bearer » part dans le coffre, pas vers le provider) — la valeur
        # vaultée est rstrippée, l'espace final est réémis tel quel pour un
        # roundtrip byte-exact ; rien à masquer → match réémis intact.
        val = m.group(2).rstrip()
        trail = m.group(2)[len(val):]
        if not val:
            return m.group(0)
        return f"{m.group(1)}{_issue_token(val, 'CRED')}{trail}"

    def _ip_sub(m):
        return _issue_token(m.group(0), "HOST")

    def _domain_sub(m):
        return _issue_token(m.group(0), "HOST")

    out = _URL_CRED_RX.sub(_url_cred_sub, text)
    out = _CRED_FIELD_RX.sub(_cred_field_sub, out)
    out = _IP_RX.sub(_ip_sub, out)
    out = _DOMAIN_RX.sub(_domain_sub, out)
    return out


def unmask(text):
    """Restaure les valeurs réelles — appelé sur les tool_args AVANT
    exécution et sur toute sortie qu'un outil doit consommer."""
    if not text or not isinstance(text, str):
        return text
    if "[" not in text:
        return text
    with _LOCK:
        hits = re.findall(r"\[(?:HOST|CRED)-\d+\]", text)
        if not hits:
            return text
        out = text
        for tok in set(hits):
            val = _VAULT.get(tok)
            if val is not None:
                out = out.replace(tok, val)
        return out


def unmask_obj(obj):
    """Unmask récursif sur dict/list (tool args JSON)."""
    if isinstance(obj, dict):
        return {k: unmask_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [unmask_obj(v) for v in obj]
    if isinstance(obj, str):
        return unmask(obj)
    return obj


def mask_obj(obj):
    """Mask récursif sur dict/list ( résultats d'outils structurés)."""
    if isinstance(obj, dict):
        return {k: mask_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_obj(v) for v in obj]
    if isinstance(obj, str):
        return mask(obj)
    return obj


def vault_size():
    with _LOCK:
        return len(_VAULT)


def reset_vault():
    """Nouvelle campagne → nouveau coffre (par process: les tokens ne
    survivent pas à un restart, c'est un choix de sécurité)."""
    with _LOCK:
        _VAULT.clear()
        _REVERSE.clear()
        _COUNTER[0] = 0


def enabled():
    """Config provider.yaml provider.tokenize_secrets (défaut false)."""
    try:
        import yaml
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "config", "provider.yaml")
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        return bool((d.get("provider") or {}).get("tokenize_secrets", False))
    except Exception:
        return False


def mask_msgs(msgs):
    """Mask une liste de messages LLM (copies! la mémoire de l'agent garde
    le RAW — le provider ne voit que des jetons). Couvre content + les
    arguments des tool_calls embeddés dans l'historique assistant."""
    out = []
    for m in msgs:
        if not isinstance(m, dict):
            out.append(m)
            continue
        m2 = dict(m)
        if m2.get("content"):
            m2["content"] = mask(m2["content"])
        if m2.get("tool_calls"):
            tcs = []
            for tc in m2["tool_calls"]:
                tc2 = dict(tc)
                fn = dict(tc2.get("function") or {})
                if fn.get("arguments"):
                    try:
                        a = json.loads(fn["arguments"])
                        fn["arguments"] = json.dumps(mask_obj(a), ensure_ascii=False)
                    except Exception:
                        fn["arguments"] = mask(fn["arguments"])
                tc2["function"] = fn
                tcs.append(tc2)
            m2["tool_calls"] = tcs
        out.append(m2)
    return out
