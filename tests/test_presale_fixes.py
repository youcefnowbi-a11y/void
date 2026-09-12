# Tests des fixes pré-vente (LO, 2026-09-10) :
# 1. XSS : DOMPurify sanitize dans MarkdownMessage (via marked custom renderer)
# 2. provider.yaml : réécriture chirurgicale préservant commentaires
# Ces tests valident la LOGIQUE pure — le rendu React demande un browser.
import os, sys, tempfile, shutil

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ═══ 1. provider.yaml : _rewrite_config_preserving_comments ═══
def _make_config(tmp, lines):
    p = os.path.join(tmp, "provider.yaml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(lines)
    return p


class TestProviderCommentPreservation:
    def test_comments_and_sections_survive(self, tmp_path):
        # simulate server module import (avoid full app import)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "srv_helpers", os.path.join(ROOT, "web", "backend", "server.py"))
        # extrait juste les deux helpers sans démarrer l'app FastAPI :
        # on les redéfinit depuis le source pour tester la logique isolée.
        src = open(os.path.join(ROOT, "web", "backend", "server.py"),
                   encoding="utf-8").read()
        import re as _re
        m = _re.search(r"def _rewrite_config_preserving_comments.*?(?=\ndef _yaml_inline)",
                       src, _re.S)
        m2 = _re.search(r"def _yaml_inline.*?(?=\n@app|\n\nclass|\Z)", src, _re.S)
        assert m and m2, "helpers introuvables dans server.py"
        ns = {"os": os, "re": _re}
        exec("import os, re\n" + m.group(0) + "\n" + m2.group(0), ns)
        rewrite = ns["_rewrite_config_preserving_comments"]

        original = """\
provider:
  language: en   # i18n knob — english default
  base_url: https://api.b.ai/v1
  api_key: sk-OLD
  model: glm-5.3-flash
operator:
  codename: LO
  agent_name: VOIDFORGE
framing:
  refusal_retry: true
"""
        p = str(tmp_path / "provider.yaml")
        with open(p, "w", encoding="utf-8") as f:
            f.write(original)
        import yaml
        cfg = yaml.safe_load(original)
        cfg["provider"]["model"] = "qwen3.8-flash"
        cfg["provider"]["api_key"] = "sk-NEW"
        rewrite(p, cfg)
        after = open(p, encoding="utf-8").read()
        assert "# i18n knob — english default" in after, "commentaire tué"
        assert "sk-NEW" in after and "sk-OLD" not in after
        assert "qwen3.8-flash" in after
        assert "codename: LO" in after, "section operator perdue"
        assert "refusal_retry: true" in after, "section framing perdue"
        # re-parse : le yaml reste VALIDE
        reparsed = yaml.safe_load(after)
        assert reparsed["provider"]["model"] == "qwen3.8-flash"
        assert reparsed["operator"]["codename"] == "LO"

    def test_new_keys_appended_not_lost(self, tmp_path):
        import re as _re, yaml
        src = open(os.path.join(ROOT, "web", "backend", "server.py"),
                   encoding="utf-8").read()
        m = _re.search(r"def _rewrite_config_preserving_comments.*?(?=\ndef _yaml_inline)",
                       src, _re.S)
        m2 = _re.search(r"def _yaml_inline.*?(?=\n@app|\n\nclass|\Z)", src, _re.S)
        ns = {"os": os, "re": _re}
        exec("import os, re\n" + m.group(0) + "\n" + m2.group(0), ns)
        rewrite = ns["_rewrite_config_preserving_comments"]

        original = "provider:\n  base_url: https://x/v1\noperator:\n  codename: LO\n"
        p = str(tmp_path / "provider.yaml")
        with open(p, "w", encoding="utf-8") as f:
            f.write(original)
        cfg = yaml.safe_load(original)
        cfg["provider"]["max_tool_rounds"] = 0        # clé absente du fichier
        cfg["provider"]["tokenize_secrets"] = False   # clé absente du fichier
        rewrite(p, cfg)
        after = yaml.safe_load(open(p, encoding="utf-8").read())
        assert after["provider"]["max_tool_rounds"] == 0
        assert after["provider"]["tokenize_secrets"] is False
        assert after["provider"]["base_url"] == "https://x/v1"
        assert after["operator"]["codename"] == "LO"


# ═══ 2. XSS : le HTML brut ne survit pas au parse ═══
class TestXssArmor:
    def test_dompurify_import_in_source(self):
        # le composant importe DOMPurify et sanitize avant dangerouslySetInnerHTML
        comp = open(os.path.join(ROOT, "web", "frontend", "src",
                                "components", "MarkdownMessage.jsx"),
                    encoding="utf-8").read()
        assert "DOMPurify" in comp, "import DOMPurify manquant"
        assert "DOMPurify.sanitize" in comp, "sanitize() non appelé"
        assert "FORBID_TAGS" in comp, "profil FORBID manquant"
        # le sanitize doit précéder l'injection
        i_sanitize = comp.index("DOMPurify.sanitize")
        i_inject = comp.index("dangerouslySetInnerHTML")
        assert i_sanitize < i_inject, "sanitize doit précéder l'injection HTML"

    def test_escape_fallback_path(self):
        # le catch de secours échappe le contenu au lieu de l'injecter cru
        comp = open(os.path.join(ROOT, "web", "frontend", "src",
                                "components", "MarkdownMessage.jsx"),
                    encoding="utf-8").read()
        assert "escapeHtml(content)" in comp
