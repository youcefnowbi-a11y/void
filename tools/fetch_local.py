"""TOOL I/O : ensure_local() — rend un chemin local à partir d'une valeur qui peut être une URL.
Un outil qui attend un FICHIER reçoit parfois une URL (l'agent lit mal la signature).
Plutôt que d'échouer en silence, on télécharge la ressource vers un fichier temporaire."""
import os, tempfile, urllib.request, hashlib

def is_url(v):
    return isinstance(v, str) and v.lower().startswith(("http://", "https://"))

def ensure_local(value, suffix=".bin", timeout=60):
    """value: chemin local (renvoyé tel quel) OU url (téléchargée vers un temp file).
    Renvoie (local_path, note)."""
    if not is_url(value):
        return value, "local"
    h = hashlib.md5(value.encode("utf-8")).hexdigest()[:10]
    path = os.path.join(tempfile.gettempdir(), f"vf_dl_{h}{suffix}")
    # cache : ne re-télécharge pas si déjà présent
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path, f"cached->{path}"
    try:
        req = urllib.request.Request(value, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/151.0.0.0"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        # R5-20: lecture par chunks avec cap dur — un stream multi-Go ne doit
        # jamais slurper la RAM de l'hôte
        _MAX = 64 * 1024 * 1024
        chunks, total = [], 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX:
                return value, "TOOL ERROR [TOO_LARGE]: ressource > 64 Mo, téléchargement abandonné"
            chunks.append(chunk)
        data = b"".join(chunks)
    except Exception:
        return value, "download-failed"
    if not data:
        return value, "download-empty"
    with open(path, "wb") as f:
        f.write(data)
    return path, f"downloaded->{path}"