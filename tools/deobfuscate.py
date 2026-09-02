"""TOOL: deobfuscate - webcrack runner + nodeless fallbacks for obfuscated bundles.

Hierarchy of power:
  1. Node.js present  -> webcrack full deobfuscation / dynamic decoder harness.
     ATTENTION: l'exécution Node est LOCALE directe (aucun sandbox —
     sandbox/runner.py n'est qu'un subprocess.run nu). N'exécuter du JS
     hostile que si la source du bundle est vérifiée.
  2. Node.js absent   -> pure-Python static extraction: string tables pulled
     straight from the source, raw bundle saved + quick-mined. Still yields
     endpoints/keys/tables — just no executed decoders.
"""
import os, subprocess, sys, json, re, shutil
from tools import register
from tools.fetch_local import ensure_local
from sandbox.runner import run


def _node_ok():
    return shutil.which("node") is not None


def _npx_cmd():
    """Resolve npx explicitly — Windows .cmd shims aren't found by bare
    subprocess.run(['npx', ...]) (that's the classic [WinError 2])."""
    return shutil.which("npx") or shutil.which("npx.cmd")


def _load_src(js_path):
    """Accept URLs or local paths; returns (local_path, source)."""
    if js_path and str(js_path).lower().startswith(("http://", "https://")):
        js_path, _note = ensure_local(js_path, suffix=".js")
    with open(js_path, encoding="utf-8", errors="replace") as f:
        return js_path, f.read()


@register(name="deobfuscate_js",
          desc="Deobfuscate an obfuscator.io-protected JS bundle via webcrack (handles string arrays, RC4 decoders, rotation, self-defending). Nodeless fallback: saves raw bundle + static quick-mine.",
          params={"type":"object","properties":{
              "js_path":{"type":"string"},"out_dir":{"type":"string"}},
              "required":["js_path"]})
def deobfuscate_js(js_path, out_dir=None):
    js_path, src = _load_src(js_path)
    out_dir = out_dir or os.path.join(os.path.dirname(js_path), "deob")
    os.makedirs(out_dir, exist_ok=True)

    if not _node_ok() or not _npx_cmd():
        # Nodeless/npxless fallback: persist the bundle, statically quick-mine it.
        from tools.js_mine import _mine_text
        raw_out = os.path.join(out_dir, "raw_source.js")
        with open(raw_out, "w", encoding="utf-8", errors="replace") as f:
            f.write(src)
        m = _mine_text(src)
        return json.dumps({
            "exit": -2, "node": "not installed — webcrack unavailable",
            "fix": "install Node.js (nodejs.org) and retry for full webcrack deobfuscation",
            "fallback": "static quick-mine of raw bundle",
            "saved_raw": raw_out, "size": len(src),
            "quick_mine": {k: v[:15] for k, v in m.items() if v},
        }, ensure_ascii=False, indent=1)

    code, tail = run([_npx_cmd(), "--yes", "webcrack", js_path, "-o", out_dir],
                     cwd=out_dir, timeout_minutes=15)
    produced = []
    for root, _, files in os.walk(out_dir):
        for f in files:
            p = os.path.join(root, f)
            produced.append({"file": p, "size": os.path.getsize(p)})
    return json.dumps({"exit": code, "produced": produced,
                       "log_tail": tail[-600:] if code != 0 else "OK"}, indent=1)


def _static_dump(src):
    """Pure-Python extraction of obfuscator.io string tables (no execution).
    Finds var _0xNAME=["...", ...] array literals and pulls their contents."""
    tables = {}
    for m in re.finditer(r'(?:var|const|let)?\s*(_0x[a-f0-9]{4,8})\s*=\s*\[([^\]]{50,})\]', src):
        name, body = m.group(1), m.group(2)
        pairs = re.findall(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', body)
        vals = [a or b for a, b in pairs]
        if len(vals) >= 5:
            tables[name] = vals[:500]
    return tables


@register(name="vm_string_dump",
          desc="Extract obfuscated string table by running array+decoder in Node — exécution LOCALE directe (aucun sandbox), n'appeler que si la source du bundle JS est vérifiée. Works when webcrack crashes. Nodeless fallback: static string-table extraction.",
          params={"type":"object","properties":{
              "js_path":{"type":"string"},"max_index":{"type":"integer","description":"nombre max d'indices décodés par fonction (défaut 300)"}},
              "required":["js_path"]})
def vm_string_dump(js_path, max_index=300):
    js_path, src = _load_src(js_path)

    if not _node_ok():
        tables = _static_dump(src)
        interesting = [v for vals in tables.values() for v in vals
                       if any(kw in v.lower() for kw in
                              ("http", "key", "token", "api", "bin", "pass",
                               "secret", "admin", "supabase", "eyJ"))][:60]
        return json.dumps({"mode": "static (node not installed)",
                           "tables_found": {k: len(v) for k, v in tables.items()},
                           "interesting": interesting,
                           "fix": "install Node.js to run the dynamic decoder harness for full decoding"},
                          ensure_ascii=False, indent=1)

    # find decoder function + array function names (obfuscator.io standard)
    dec = re.findall(r"function\s+(_0x[a-f0-9]+)\s*\(\s*_0x[a-f0-9]+\s*,\s*[A-Za-z_$][\w$]*\s*\)", src)
    harness = src[:src.find("function")] if "function" in src else ""
    # build node script: load original, then brute-decode
    node_script = f"""
const fs = require('fs');
let src = fs.readFileSync({json.dumps(os.path.abspath(js_path))}, 'utf8');
// neutralize debug protection & timers
src = src.replace(/setInterval[^;]+;/g, ';').replace(/debugger/g, '');
eval(src.slice(0, Math.min(src.length, 200000)));
const fnNames = {json.dumps(dec)};
let dumped = {{}};
for (const fn of fnNames) {{
  try {{
    const f = eval(fn);
    if (typeof f !== 'function') continue;
    for (let i = 0; i < {int(max_index)}; i++) {{
      try {{ dumped[i] = String(f(i)); }} catch(e) {{}}
    }}
  }} catch(e) {{}}
}}
fs.writeFileSync({json.dumps(os.path.join(os.path.dirname(js_path), 'strings_dump.json'))},
                 JSON.stringify(dumped, null, 1));
console.log('dumped', Object.keys(dumped).length);
"""
    dump_file = os.path.join(os.path.dirname(js_path), 'strings_dump.json')
    try:
        # C-D2: purge du dump périmé d'un bundle précédent — sinon un run
        # Node raté « réussit » en servant les strings de l'AUTRE bundle
        if os.path.exists(dump_file):
            os.unlink(dump_file)
    except Exception:
        pass
    tmp = js_path + ".vm.js"
    try:
        # try/finally: le harness ne doit jamais fuiter sur erreur (R5-6)
        open(tmp, "w", encoding="utf-8").write(node_script)
        code, tail = run(["node", tmp], timeout_minutes=5)
        data = json.load(open(dump_file)) if os.path.exists(dump_file) else {}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    interesting = {k: v for k, v in data.items() if isinstance(v, str) and
                   any(kw in v.lower() for kw in ("http","key","token","api","bin","pass","secret","admin"))}
    out = {"decoded_total": len(data),
           "interesting": list(interesting.values())[:60]}
    if len(src) > 200_000:
        # C-D1: le harness n'eval que les 200k premiers octets — sur un gros
        # bundle les décoders peuvent être hors slice (zéro décodage). Le
        # rendu doit l'EXPLIQUER au lieu d'un silence indistinguable d'un
        # bundle sans strings. (Pas d'eval full-source par design.)
        out["truncated_eval"] = True
        out["eval_bytes"] = 200_000
    return json.dumps(out, ensure_ascii=False, indent=1)
