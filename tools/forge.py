"""VOIDFORGE :: TOOL FORGE — the agent forges her own arsenal.

The strategist (or any agent phase) can write a new tool at runtime: the
code lands in tools/forged_<name>.py, is syntax-checked with py_compile,
hot-imported (which registers it into the live registry), and is then
available to every future mission AND re-discovered automatically on the
next backend boot.

Contract for the forged code — TWO accepted forms:
  1. BODY form: the run(**kwargs) body only (4-space indented or flat),
     must return a string:
         return json.dumps({"ok": True})
  2. FULL-MODULE form (detected automatically): your own module with a
     module-level `def run(...)` — leading imports ALLOWED and kept:
         import json
         def run(**kwargs):
             return json.dumps({"ok": True})

Standard imports available in both forms: json, re, time, urllib.request,
urllib.error. The forge registers the tool under `forged_<name>` — a
namespace that can never collide with the core arsenal.
"""
import importlib
import json
import os
import py_compile
import re
import sys
import traceback

from tools import all_tools, discover, register

FORGE_DIR = os.path.dirname(os.path.abspath(__file__))

MODULE_HEADER = '''"""VOIDFORGE :: forged tool — @@NAME@@
@@DESC@@
Forged by the strategist on @@DATE@@. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error

'''
MODULE_FOOTER = '''

from tools import register as _vf_register
_vf_register(@@NAME_LIT@@, @@DESC_LIT@@, @@PARAMS_LIT@@, @@DANGER_LIT@@)(run)
'''
MODULE_WRAP = "def run(@@SIG@@):\n@@CODE@@\n"


def _list_forged():
    return sorted(f[7:-3] for f in os.listdir(FORGE_DIR)
                  if f.startswith("forged_") and f.endswith(".py"))


@register(name="forge_tool",
          desc="Forge a NEW tool into the live arsenal: write its Python code, syntax-check it, hot-register it as forged_<name>. Also lists existing forged tools with mode='list'. The agent's self-extension mechanism. "
               "SESSION LAW: forged tools live ONLY in the session that armed them — a tool forged in a PAST mission is listed but NOT callable; re-forge it (code + overwrite=true) instead of calling it. ",
          params={"type": "object", "properties": {
              "name": {"type": "string", "description": "Tool name (snake_case, 3-40 chars) — 'list' to list forged tools"},
              "desc": {"type": "string", "description": "One-line tool description for the LLM"},
              "code": {"type": "string", "description": "FORM 1: run(**kwargs) body, 4-space indented, returns a string. FORM 2 (auto-detected): full module with leading imports + module-level def run(**kwargs) — imports are kept at column 0, no double-def, returns a string"},
              "params": {"type": "object", "description": "JSON schema: {\"type\":\"object\",\"properties\":{...},\"required\":[...]}"},
              "danger": {"type": "string", "description": "safe | active | loud | strike (default active)"},
              "overwrite": {"type": "boolean", "description": "W17: replace an existing forged tool of the same name (fix + redeploy in one round)"},
          },
          "required": ["name"]})
def forge_tool(name, desc="", code="", params=None, danger="active",
               overwrite=False):
    name = (name or "").strip().lower()
    if name in ("list", "", "ls"):
        forged = _list_forged()
        if not forged:
            return json.dumps({"forged": [], "note": "l'arsenal forgé est vide — forge le premier outil"})
        entries = []
        for fn in forged:
            try:
                t = all_tools()  # forces discovery
                spec = next((x for x in t if x["name"] == f"forged_{fn}"), None)
                entries.append({"name": f"forged_{fn}",
                                "live": bool(spec),
                                "desc": (spec or {}).get("desc", "?")[:140]})
            except Exception:
                entries.append({"name": f"forged_{fn}", "live": False, "desc": "?"})
        # weakness #13 (mission D3): ~6 rounds burned calling PREVIOUS-
        # session forged tools that the list showed as names. Make the
        # session law impossible to miss.
        _live_names = [e["name"] for e in entries if e["live"]]
        return json.dumps({
            "forged": entries,
            "SESSION LAW": "live=false tools are from PAST sessions — NOT "
                           "callable now. Only live=true entries execute. "
                           "Re-forge with code (overwrite=true if same "
                           "name) to arm this session.",
            "live_now": _live_names}, ensure_ascii=False, indent=1)

    if not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", name):
        return json.dumps({"error": "nom invalide — snake_case, 3-40 chars, commence par une lettre"})
    core = all_tools()
    if f"forged_{name}" in {t["name"] for t in core} and not overwrite:
        # W17 (mission-79 autopsy): the collision was a DEAD END — no
        # overwrite, no delete path, so she burned a round inventing a
        # new name for the same tool. overwrite=true replaces in place.
        return json.dumps({
            "error": f"forged_{name} existe déjà — choisis un autre nom "
                     f"OU re-issue avec overwrite=true pour le remplacer"})
    if not code.strip():
        return json.dumps({"error": "code vide — le corps de run(**kwargs) est requis"})

    def _body_of(src):
        """Normalize whatever the LLM sent into an indented run() body.
        textwrap.dedent strips the common prefix (uniform indents vanish,
        relative nesting survives), then one level is added. A full
        `def run(...):` wrapper is stripped first."""
        import textwrap
        m = re.match(r"(?s)\s*def run\s*\([^)]*\)\s*:\s*\n(.*)$", src)
        if m:
            src = m.group(1)
        src = src.rstrip()
        d = textwrap.dedent(src)
        return "\n".join(("    " + ln) if ln.strip() else "" for ln in d.splitlines())

    def _flat_body(src):
        m = re.match(r"(?s)\s*def run\s*\([^)]*\)\s*:\s*\n(.*)$", src)
        if m:
            src = m.group(1)
        return "\n".join(("    " + ln.strip()) if ln.strip() else "" for ln in src.splitlines())

    def _full_module(src):
        """True when the LLM sent a FULL module: a `def run(` at any indent
        (R3-17: l'ancien ancrage column-0-only rateait le def indenté et
        tombait dans le salvage qui aplatissement le control flow). Forging
        that form as a run() BODY nests a second def and returns None —
        the historical 'diag_import returns null' bug."""
        return re.search(r"(?m)^\s*def run\s*\(", src) is not None

    import textwrap as _tw
    if _full_module(code):
        # full-module form: verbatim (dedented to column 0), imports included
        module_body = _tw.dedent(code).rstrip()
    else:
        code = _body_of(code)
        if not code.strip():
            return json.dumps({"error": "code vide — le corps de run(**kwargs) est requis"})
        module_body = None

    schema = params if isinstance(params, dict) else {"type": "object", "properties": {}}
    if schema.get("type") != "object":
        schema = {"type": "object", "properties": {}}
    props = schema.setdefault("properties", {})
    sig = ", ".join(f"{k}=None" for k in props) or "**kwargs"

    import datetime
    _final_desc = (desc or f"forged tool {name}").strip()
    # R3-15/R3-38: fail-closed — un label inconnu ou halluciné ne descend
    # JAMAIS vers "safe" (sinon la forge esquive do_not_exploit à vie via un
    # tool étiqueté safe). "danger" (valeur fantôme) remonte en "active".
    _final_danger = danger if danger in ("safe", "active", "loud", "strike") else "active"
    if module_body is not None:
        rendered = module_body
    else:
        rendered = MODULE_WRAP.replace("@@SIG@@", sig).replace("@@CODE@@", code)
    src = (MODULE_HEADER
           .replace("@@NAME@@", name)
           # R3-14/R3-29: le desc vit dans le DOCSTRING du header — un desc
           # contenant """ ou un backslash de fin pouvait TERMINER la chaîne
           # et exécuter du code au module-level à l'import, hors de tout
           # review du param code. json.dumps échappe tout ce qui compte.
           .replace("@@DESC@@", json.dumps(_final_desc, ensure_ascii=False)[1:-1])
           .replace("@@DATE@@", datetime.date.today().isoformat())
           + rendered
           + (MODULE_FOOTER
              .replace("@@NAME_LIT@@", repr(f"forged_{name}"))
              .replace("@@DESC_LIT@@", repr(_final_desc))
              .replace("@@PARAMS_LIT@@", repr(schema))
              .replace("@@DANGER_LIT@@", repr(_final_danger))))
    path = os.path.join(FORGE_DIR, f"forged_{name}.py")

    def _write_and_compile(source):
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
        py_compile.compile(path, doraise=True)

    try:
        try:
            _write_and_compile(src)
        except py_compile.PyCompileError:
            if module_body is not None:
                raise  # full-module form: pas de salvage (déjà column-0 verbatim)
            # R3-17: le salvage APLATIT le control flow (return hissé hors du
            # bloc) — si le corps contient des blocs, refuser au lieu de
            # livrer une sémantique silencieusement différente de l'écrit.
            if re.search(r"(?m)^\s*(if|for|while|try)\b", code):
                raise
            # mixed-paste salvage: flatten every statement to one level
            _write_and_compile(src.replace(code, _flat_body(code)))
    except Exception as ex:
        try:
            os.remove(path)
        except Exception:
            pass
        return json.dumps({"error": f"compile failed: {str(ex)[:300]}",
                           "hint": "corrige le code et re-forge"}, ensure_ascii=False)
    try:
        modname = f"tools.forged_{name}"
        if modname in sys.modules:
            del sys.modules[modname]
        # Windows: the FileFinder caches the directory listing — a file
        # written THIS run is not always visible to import_module (mtime
        # granularity races). Invalidate before every hot-load.
        importlib.invalidate_caches()
        importlib.import_module(modname)
        t = all_tools()
        spec = next((x for x in t if x["name"] == f"forged_{name}"), None)
        if not spec:
            raise RuntimeError("module importé mais register() non exécuté")
    except Exception:
        tb = traceback.format_exc()
        try:
            os.remove(path)
        except Exception:
            pass
        return json.dumps({"error": f"hot-load failed: {str(tb)[-400:]}",
                           "hint": "le fichier a été retiré — corrige et re-forge"}, ensure_ascii=False)
    return json.dumps({"ok": True, "tool": f"forged_{name}",
                       "desc": spec["desc"][:160],
                       "params": spec.get("params", {}),
                       "note": "outil ARMÉ et vivant — utilisable immédiatement par toutes les phases",
                       "file": f"tools/forged_{name}.py"}, ensure_ascii=False, indent=1)
