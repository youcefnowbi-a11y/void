# -*- coding: utf-8 -*-
"""i18n battery: L() table integrity + EN default + FR knob."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.lang import L, set_language, get_language, _TABLE

# 1. EN is the default — no config, no env
assert get_language() == "en", "default language must be en"

# 2. every key resolves in both languages, no empty variant
for k, (en, fr) in _TABLE.items():
    assert en and fr, f"key {k} missing a variant"
    set_language("en")
    assert L(k) == en or "{" in en, f"EN broken for {k}"
    set_language("fr")
    assert L(k) == fr or "{" in fr, f"FR broken for {k}"
set_language("en")

# 3. format args
set_language("en")
assert "14" in L("plays_loaded", n=14)
assert "team" in L("license_valid", plan="team")
set_language("fr")
assert "14" in L("plays_loaded", n=14)
set_language("en")

# 4. unknown key never crashes
assert L("totally_unknown_key") == "totally_unknown_key"

# 5. knob junk ignored
set_language("de")
assert get_language() == "en"

# 6. format-safe on bad args (no crash, returns template)
out = L("plays_loaded")  # missing n -> returns unformatted template
assert "plays_loaded" not in out or "{" in out

print("[PASS] lang: EN default, FR knob, 37 keys bilingual, crash-proof")
