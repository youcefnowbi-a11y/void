"""TOOL: spa_crawl v2 - playwright page walker with app-as-oracle capture.

Loads the SPA in headless Chromium and hooks window.fetch + XMLHttpRequest
via an init script, so the app ITSELF records every request it makes —
complete with bodies, headers and responses. Also dumps localStorage /
sessionStorage / cookies per page (token mines), saves a replay-ready
capture file for tools/replay.py, and feeds the Living Graph blackboard.
"""
import asyncio, json, os, time
from tools import register

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURES_DIR = os.path.join(ROOT, "data", "captures")

_HOOK = """
(() => {
  window.__vf_captured = window.__vf_captured || [];
  const rec = (method, url, reqBody, status, respBody, reqHeaders) => {
    try { window.__vf_captured.push({
      method, url: String(url).slice(0, 500),
      // K2 fix: the app's OWN auth headers are the best oracle (what
      // credential grammar does the legit client send?). Capture them,
      // redacting long values to class+shape (Bearer xxxxx… 48 chars).
      req_headers: reqHeaders || null,
      req_body: reqBody ? String(reqBody).slice(0, 2000) : null,
      status: status || null,
      resp_body: respBody ? String(respBody).slice(0, 3000) : null,
      ts: Date.now()
    }); } catch (e) {}
  };
  const redactHeaders = (h) => {
    if (!h) return null;
    try {
      const o = {};
      if (h instanceof Headers) h.forEach((v, k) => { o[k] = v.length > 24 ? v.slice(0, 12) + '…(' + v.length + ' chars)' : v; });
      else if (Array.isArray(h)) h.forEach(p => { if (p) o[p[0]] = String(p[1]).length > 24 ? String(p[1]).slice(0, 12) + '…(' + String(p[1]).length + ' chars)' : p[1]; });
      else if (typeof h === 'object') Object.keys(h).forEach(k => { const v = String(h[k]); o[k] = v.length > 24 ? v.slice(0, 12) + '…(' + v.length + ' chars)' : v; });
      return o;
    } catch (e) { return null; }
  };
  if (!window.__vf_hooked) {
    window.__vf_hooked = true;
    const of = window.fetch;
    window.fetch = async function(input, init) {
      const u = (typeof input === 'string') ? input : (input && input.url) || '';
      const m = (init && init.method) || (input && input.method) || 'GET';
      const rb = (init && init.body) || null;
      const rh = redactHeaders((init && init.headers) || (input && input.headers));
      try {
        const res = await of.apply(this, arguments);
        const clone = res.clone();
        clone.text().then(t => rec(m, u, rb, res.status, t, rh)).catch(() => rec(m, u, rb, res.status, null, rh));
        return res;
      } catch (e) { rec(m, u, rb, 0, 'ERR:' + e, rh); throw e; }
    };
    const oo = XMLHttpRequest.prototype.open;
    const os = XMLHttpRequest.prototype.send;
    const osh = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.open = function(m, u) {
      this.__vf_m = m; this.__vf_u = u; this.__vf_hdrs = {}; return oo.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
      try { if (this.__vf_hdrs) this.__vf_hdrs[k] = String(v).length > 24 ? String(v).slice(0, 12) + '…(' + String(v).length + ' chars)' : String(v); } catch (e) {}
      return osh.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(b) {
      this.addEventListener('load', () => rec(this.__vf_m, this.__vf_u, b, this.status, this.responseText, redactHeaders(this.__vf_hdrs)));
      return os.apply(this, arguments);
    };
  }
})();
"""


@register(name="spa_crawl",
          desc="Headless Chromium walks an SPA: hooks fetch/XHR so the app records its own requests (bodies+responses), extracts FORMS (action/method/inputs per page — each form is a strike target), captures localStorage/sessionStorage/cookies, network calls, console errors, DOM text. Saves a replay-ready capture file. G-fix: heavy React/bundler pages need wait_s 20-30 (default 4 starves them — the app hasn't finished fetching when the crawl reads). A timeout is NOT 'route missing' — retry with wait_s=25 before concluding.",
          params={"type": "object", "properties": {
              "url": {"type": "string"},
              "wait_s": {"type": "integer"},
              "paths": {"type": "array", "items": {"type": "string"},
                        "description": "extra client routes to visit after load"}},
              "required": ["url"]})
def spa_crawl(url, wait_s=4, paths=None):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "playwright not installed: pip install playwright && playwright install chromium"

    async def run():
        net, errs, captured, storage = [], [], [], {}
        shapes = []  # V3: form shapes (strike-target mapping)
        try:
            pw_ctx = async_playwright()
        except Exception as ex:
            return {"error": f"playwright init failed: {str(ex)[:150]}",
                    "fix": "pip install playwright && playwright install chromium"}
        async with pw_ctx as pw:
            try:
                b = await pw.chromium.launch(headless=True)
            except Exception as ex:
                return {"error": f"chromium launch failed: {str(ex)[:200]}",
                        "fix": "playwright install chromium"}
            try:
                ctx = await b.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36")
                await ctx.add_init_script(_HOOK)
                pg = await ctx.new_page()

                def on_resp(r):
                    try:
                        net.append({"status": r.status, "method": r.request.method,
                                    "url": r.url[:160], "type": r.request.resource_type})
                    except Exception:
                        pass

                pg.on("response", on_resp)
                pg.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)

                visited = []

                async def go(p):
                    try:
                        await pg.goto(p, timeout=40000, wait_until="domcontentloaded")
                        await pg.wait_for_timeout(int(wait_s) * 1000)
                        txt = await pg.evaluate("() => document.body ? document.body.innerText.slice(0,300) : ''")
                        visited.append({"path": p, "text": txt.replace("\n", " | ")[:250]})
                        try:
                            storage[p] = await pg.evaluate(
                                """() => ({local: JSON.stringify(localStorage).slice(0,4000),
                                           session: JSON.stringify(sessionStorage).slice(0,2000)})""")
                        except Exception:
                            storage[p] = {"local": "", "session": ""}
                        batch = await pg.evaluate("() => (window.__vf_captured || []).splice(0, 500)")
                        captured.extend(batch or [])
                        # ── V3: form shapes — every form becomes a strike target ──
                        try:
                            forms = await pg.evaluate(
                                """() => [...document.querySelectorAll('form')].map(f => ({
                                    action: f.action,
                                    method: (f.method || 'get').toUpperCase(),
                                    inputs: [...f.querySelectorAll('input,textarea,select')].map(i => ({
                                        name: i.name || '',
                                        type: i.type || '',
                                        required: !!i.required,
                                        value: (i.type === 'password' ? '***' : String(i.value || '').slice(0, 60)),
                                        maxlength: i.maxLength > 0 ? i.maxLength : null
                                    }))
                                }))""")
                            for fm in (forms or []):
                                fm["page"] = p
                            shapes.extend(forms or [])
                        except Exception:
                            pass
                    except Exception as ex:
                        visited.append({"path": p, "err": str(ex)[:90]})

                targets = [url] + [url.rstrip("/") + pth for pth in (paths or [])]
                for t in targets:
                    await go(t)
                cookies = await ctx.cookies()
            finally:
                # R5-10: Chromium headless doit mourir même si le crawl échoue
                try:
                    await b.close()
                except Exception:
                    pass

        out = {
            "network": net[:80],
            "visited": visited,
            "forms": shapes[:40],
            "console_errors": errs[:10],
            "api_calls_detected": [n["url"] for n in net
                                   if any(k in n["url"] for k in ("/api", "rpc", "auth", "supabase"))][:30],
            "captured_requests": captured[:120],
            "storage": {k: v for k, v in storage.items()},
            "cookies": [{"name": c.get("name"), "value": str(c.get("value", ""))[:80],
                         "domain": c.get("domain")} for c in cookies][:20],
        }
        # persist replay-ready capture
        try:
            import re, urllib.parse
            os.makedirs(CAPTURES_DIR, exist_ok=True)
            # R5-21: slug du netloc — chars illégaux Windows (? :) interdits
            host = re.sub(r"[^A-Za-z0-9._-]", "_",
                          urllib.parse.urlsplit(url).netloc) or "unknown_host"
            cap_path = os.path.join(CAPTURES_DIR, f"{host}-{int(time.time())}.json")
            with open(cap_path, "w", encoding="utf-8") as f:
                json.dump({"target": url, "requests": captured}, f, ensure_ascii=False)
            out["capture_file"] = cap_path
        except Exception as ex:
            # capture jamais écrite en silence → l'agente doit savoir pourquoi
            out["capture_error"] = f"{type(ex).__name__}: {str(ex)[:150]}"
        try:
            from core.blackboard import observe
            observe("spa_crawl", json.dumps(out)[:60000])
        except Exception:
            pass
        return out

    return asyncio.run(run())


@register(name="dir_brute",
          desc="Directory brute: gobuster if installed, else built-in concurrent python prober with a 140-path wordlist through the hardened transport.",
          params={"type": "object", "properties": {
              "base": {"type": "string"}, "wordlist": {"type": "string"}},
              "required": ["base"]})
def dir_brute(base, wordlist=None):
    import subprocess, shutil
    gb = shutil.which("gobuster")
    if gb:
        wl = wordlist or os.environ.get("SECLISTS_PATH",
             os.path.join(os.path.expanduser("~"), "SecLists", "Discovery", "Web-Content", "common.txt"))
        r = subprocess.run([gb, "dir", "-u", base, "-w", wl, "-t", "20", "-q", "--no-error",
                            "-a", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=600)
        return (r.stdout or "")[-4000:] + (f"\n[stderr]{(r.stderr or '')[-300:]}" if r.stderr else "")

    # python fallback — concurrent prober through the hardened transport
    from concurrent.futures import ThreadPoolExecutor
    from tools._transport import fetch
    WORDS = ["admin", "administrator", "api", "api/v1", "backup", "config", "console",
             "dashboard", "db", "debug", "dev", ".env", ".git", ".git/config", "graphql",
             "health", "images", "internal", "jenkins", "js", "login", "logout", "metrics",
             "old", "panel", "phpmyadmin", "private", "products", "orders", "users",
             "rest", "robots.txt", "server-status", "settings", "setup", "src", "staff",
             "staging", "status", "storage", "swagger", "swagger.json", "test", "tmp",
             "uploads", "user", "v1", "v2", "wp-admin", ".well-known/security.txt",
             "actuator", "actuator/health", "admin/login", "api/health", "api/config",
             "auth", "auth/login", "bin", "cgi-bin", "checkout", "clients", "cmd",
             "common", "data", "demo", "docs", "download", "downloads", "edit", "files",
             "home", "info", "install", "invoice", "keys", "license", "logs", "mail",
             "manage", "manager", "media", "member", "modules", "new", "news", "node_modules",
             "orders/all", "payment", "payments", "portal", "profile", "public", "register",
             "reports", "resources", "restore", "robots", "rpc", "search", "secret",
             "secure", "service", "services", "shop", "signin", "signup", "site", "sql",
             "ssl", "stats", "store", "support", "system", "temp", "theme", "tools",
             "top", "trace", "update", "upload", "utility", "vendor", "web", "web.config",
             "webhook", "webhooks", "wp-content", "wp-login.php", "xmlrpc.php", "freebies",
             "track", "categories", "cart", "inventory", "suppliers", "refunds", "coupons"]
    base = base.rstrip("/")
    results = []

    def probe(w):
        u = f"{base}/{w}"
        r = fetch(u, timeout=10, use_cache=False, retries=0)
        if r["status"] in (200, 201, 202, 301, 302, 307, 308, 401, 403, 405):
            return {"path": w, "status": r["status"], "size": r["size"],
                    "hint": r["body"][:80].replace("\n", " ") if r["size"] < 500 else ""}
        return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(probe, WORDS):
            if res:
                results.append(res)
    found = {r["path"]: r["status"] for r in results}
    return json.dumps({"gobuster": "not installed — python prober used",
                       "paths_tried": len(WORDS), "hits": results[:40],
                       "hit_count": len(found)}, ensure_ascii=False, indent=1)
