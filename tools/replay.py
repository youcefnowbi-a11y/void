"""TOOL: replay_mutate — the app-as-oracle engine.

spa_crawl v2 captures the requests the app itself makes (correct headers,
correct encoding, correct auth). This tool re-fires those captured requests
through the hardened transport with surgical mutations — URL substitutions,
dotted-path body patches, header overrides — and reports deltas.

The app is the protocol oracle: we never hand-craft wire formats, we steer
its own traffic. This is the end of format-guessing.
"""
import json, os, time
from tools import register
from tools._transport import fetch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURES_DIR = os.path.join(ROOT, "data", "captures")


def _patch(body_obj, patches):
    """Apply dotted-path patches: {"data.slug": "x", "items[0].id": 9}"""
    for path, val in (patches or {}).items():
        parts = path.replace("[", ".").replace("]", "").split(".")
        cur = body_obj
        for i, p in enumerate(parts):
            last = i == len(parts) - 1
            if isinstance(cur, list):
                try:
                    idx = int(p)
                except ValueError:
                    break
                if last:
                    cur[idx] = val
                else:
                    cur = cur[idx]
            elif isinstance(cur, dict):
                if last:
                    cur[p] = val
                else:
                    cur = cur.setdefault(p, {})
            else:
                break


@register(name="replay_mutate",
          desc="Re-fire requests the app itself made (from spa_crawl capture files) with surgical mutations: url_replace, dotted-path body_patch, header overrides. Reports status deltas vs original. The app is the protocol oracle.",
          params={"type": "object", "properties": {
              "capture_file": {"type": "string", "description": "path from spa_crawl's capture_file; omit for latest"},
              "url_filter": {"type": "string", "description": "substring filter on request url"},
              "url_replace": {"type": "array", "items": {"type": "string"},
                              "description": "[from, to] substring substitution on the url"},
              "body_patch": {"type": "object", "description": "dotted-path patches, e.g. {\"data.slug\": \"x\"}"},
              "headers": {"type": "object", "description": "extra/override headers"},
              "max": {"type": "integer"}},
              "required": []})
def replay_mutate(capture_file=None, url_filter="", url_replace=None,
                  body_patch=None, headers=None, max=10):
    # Ω3.2 (audit-6): Resolve capture_file from mission workspace captures/ or data/captures/
    resolved = None
    if capture_file:
        if os.path.isabs(capture_file) and os.path.exists(capture_file):
            resolved = capture_file
        else:
            try:
                from core.mission_workspace import get_active
                ws = get_active()
                if ws and os.path.exists(os.path.join(ws.dir, "captures", capture_file)):
                    resolved = os.path.join(ws.dir, "captures", capture_file)
                elif ws and os.path.exists(os.path.join(ws.dir, capture_file)):
                    resolved = os.path.join(ws.dir, capture_file)
            except Exception:
                pass
            if not resolved and os.path.exists(os.path.join(CAPTURES_DIR, capture_file)):
                resolved = os.path.join(CAPTURES_DIR, capture_file)
    else:
        # Latest capture from workspace or data/captures
        candidates = []
        try:
            from core.mission_workspace import get_active
            ws = get_active()
            cd = os.path.join(ws.dir, "captures") if ws else None
            if cd and os.path.isdir(cd):
                for f in os.listdir(cd):
                    if f.endswith(".json"):
                        p = os.path.join(cd, f)
                        candidates.append((os.path.getmtime(p), p))
        except Exception:
            pass
        if os.path.isdir(CAPTURES_DIR):
            for f in os.listdir(CAPTURES_DIR):
                if f.endswith(".json"):
                    p = os.path.join(CAPTURES_DIR, f)
                    candidates.append((os.path.getmtime(p), p))
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            resolved = candidates[0][1]

    if not resolved or not os.path.exists(resolved):
        return json.dumps({"error": f"capture file not found: {capture_file or 'latest'}"})
    capture_file = resolved

    with open(capture_file, encoding="utf-8") as f:
        cap = json.load(f)
    reqs = [r for r in cap.get("requests", [])
            if url_filter in r.get("url", "")][:max] if url_filter \
        else cap.get("requests", [])[:max]
    if not reqs:
        return json.dumps({"error": f"no requests matched filter '{url_filter}'",
                           "capture": capture_file, "total": len(cap.get("requests", []))})

    results = []
    target_origin = cap.get("target", "")
    for r in reqs:
        url = r.get("url", "")
        if not url.startswith("http"):
            from urllib.parse import urlsplit, urljoin
            origin = f"{urlsplit(target_origin).scheme}://{urlsplit(target_origin).netloc}" \
                if target_origin.startswith("http") else ""
            url = urljoin(origin, url) if origin else url
        if url_replace and len(url_replace) == 2:
            url = url.replace(url_replace[0], url_replace[1])
        body = r.get("req_body")
        body_obj = None
        if body:
            try:
                body_obj = json.loads(body)
                _patch(body_obj, body_patch)
            except Exception:
                body_obj = body  # non-JSON body: pass through unpatched
        merged_headers = {}
        if r.get("req_headers"):
            merged_headers.update(r["req_headers"])
        if headers:
            merged_headers.update(headers)
        t0 = time.time()
        res = fetch(url, method=r.get("method", "GET"), headers=merged_headers or None,
                    body=body_obj if isinstance(body_obj, (dict, list)) else body_obj,
                    timeout=20, use_cache=False)
        results.append({
            "original": {"url": r["url"][:120], "method": r.get("method"), "status": r.get("status")},
            "replayed": {"url": url[:120], "status": res["status"], "size": res["size"],
                         "ms": int((time.time() - t0) * 1000),
                         "final_url": res.get("final_url", "")[:120]},
            "delta": (res["status"] - (r.get("status") or 0)) if r.get("status") else None,
            "body_preview": res["body"][:400],
        })

    return json.dumps({"capture": os.path.basename(capture_file),
                       "replayed": len(results),
                       "results": results}, ensure_ascii=False, indent=1)[:18000]
