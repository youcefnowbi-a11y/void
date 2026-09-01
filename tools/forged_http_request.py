"""VOIDFORGE :: forged tool — http_request
Arbitrary HTTP request with full method support (PATCH/PUT/DELETE/POST/GET) — returns status + body. For RLS write-probes and tier escalation.
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(body=None, headers=None, method=None, url=None):
    import json, urllib.request, urllib.error
    def run(**kwargs):
        url = kwargs.get("url")
        method = (kwargs.get("method") or "GET").upper()
        headers = kwargs.get("headers") or {}
        body = kwargs.get("body")
        data = None
        if body is not None:
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.dumps({"status": r.status, "body": r.read().decode(errors="replace")[:5000]})
        except urllib.error.HTTPError as e:
            return json.dumps({"status": e.code, "body": e.read().decode(errors="replace")[:5000]})
        except Exception as e:
            return json.dumps({"error": str(e)})


from tools import register as _vf_register
_vf_register('forged_http_request', 'Arbitrary HTTP request with full method support (PATCH/PUT/DELETE/POST/GET) — returns status + body. For RLS write-probes and tier escalation.', {'properties': {'body': {'type': 'string'}, 'headers': {'type': 'object'}, 'method': {'type': 'string'}, 'url': {'type': 'string'}}, 'required': ['url'], 'type': 'object'}, 'active')(run)
