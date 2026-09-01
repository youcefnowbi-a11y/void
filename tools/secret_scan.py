"""TOOL: secret_scan - gitleaks-class pattern library over files/folders."""
import os, re, json, math
from tools import register
from tools.fetch_local import ensure_local

RULES = {
    "aws_access_key":  re.compile(r"(AKIA|ASIA)[A-Z0-9]{16}"),
    "aws_secret":      re.compile(r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]"),
    "stripe_live":     re.compile(r"sk_live_[A-Za-z0-9]{16,}"),
    "stripe_webhook":  re.compile(r"whsec_[A-Za-z0-9]{16,}"),
    "slack_bot":       re.compile(r"xoxb-[A-Za-z0-9\-]{10,}"),
    "google_api":      re.compile(r"AIza[A-Za-z0-9_\-]{35}"),
    "github_pat":      re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{60,}"),
    "supabase_service":re.compile(r"eyJ[A-Za-z0-9_-]{40,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    "telegram_bot":    re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    "private_key":     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic_secret":  re.compile(r"(?i)(?:secret|passwd|password|api_?key|token)['\"]?\s*[:=]\s*['\"][A-Za-z0-9_\-/+=]{12,}['\"]"),
    "db_conn":         re.compile(r"(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^\s'\"]{8,120}"),
    "jwt":             re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\.?[A-Za-z0-9_-]*"),
}

def _entropy(s):
    """Shannon entropy of a string."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count/length) * math.log2(count/length) for count in freq.values())

ENTROPY_PATTERN = re.compile(r'["\']([A-Za-z0-9+/=_\-]{20,120})["\']')
ENTROPY_THRESHOLD = 4.5

@register(name="secret_scan",
          desc="Scan a file OR folder recursively for hardcoded secrets using a gitleaks-class pattern set: AWS/GCP/Stripe/TG-bot tokens/JWTs/DB connections/private keys.",
          params={"type":"object","properties":{
              "path":{"type":"string"},
              "max_file_mb":{"type":"integer"}},
              "required":["path"]})
def secret_scan(path, max_file_mb=8):
    # MUR : l'agent passe souvent une URL là où un fichier est attendu.
    # On télécharge au lieu d'échouer en silence.
    if ensure_local and path and str(path).lower().startswith(("http://", "https://")):
        path, _note = ensure_local(path, suffix=".js")
    findings = []
    if os.path.isfile(path):
        files = [path]
    else:
        files = []
        for root, _, fns in os.walk(path):
            if any(skip in root for skip in ("node_modules", ".git", "__pycache__")):
                continue
            for fn in fns:
                p = os.path.join(root, fn)
                try:
                    if os.path.getsize(p) <= max_file_mb * 1_000_000:
                        files.append(p)
                except Exception: pass
    scanned = 0
    for fp in files[:4000]:
        try:
            src = open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        scanned += 1
        for rule, pat in RULES.items():
            for m in pat.finditer(src):
                findings.append({"rule": rule,
                                 "file": os.path.basename(fp),
                                 "match": m.group(0)[:100]})
                if len(findings) > 200:
                    return json.dumps({"scanned_files": scanned, "findings": findings,
                                       "note": "hit cap"}, indent=1)
        # Entropy-based detection
        for m in ENTROPY_PATTERN.finditer(src):
            val = m.group(1)
            ent = _entropy(val)
            if ent > ENTROPY_THRESHOLD:
                # Skip if already caught by regex rules
                if not any(f["match"] == val[:100] for f in findings if f["file"] == os.path.basename(fp)):
                    findings.append({"rule": f"high_entropy ({ent:.1f})",
                                     "file": os.path.basename(fp),
                                     "match": val[:100]})
    return json.dumps({"scanned_files": scanned, "findings_count": len(findings),
                       "findings": findings[:120]}, ensure_ascii=False, indent=1)
