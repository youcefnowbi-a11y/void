"""VOIDFORGE :: WALL BREAKER tests — offline-safe paths."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools as reg
reg.discover()


def test_breaker_registered_and_safe():
    t = reg.get("wall_breaker")
    assert t["name"] == "wall_breaker"
    assert t["danger"] == "safe"


def test_breaker_no_tech_error():
    out = reg.execute("wall_breaker", {"op": "break"})
    assert "NO_TECH" in out


def test_breaker_cache_roundtrip(tmp_path):
    from tools.wall_breaker import CACHE_PATH, _cache_store, breaker_cache
    _cache_store("apache 2.4.49", {"findings": [
        {"title": "[EDB-50383] Apache 2.4.49 path traversal",
         "url": "https://www.exploit-db.com/exploits/50383", "snip": "CVE-2021-41773"}]})
    out = breaker_cache("apache")
    assert "EDB-50383" in out and "CVE-2021-41773" in out
    # miss path
    out2 = breaker_cache("weblogic-nope")
    assert "CACHE MISS" in out2


def test_breaker_cache_empty():
    from tools.wall_breaker import breaker_cache
    # never crash on empty cache
    out = breaker_cache()
    assert isinstance(out, str) and len(out) > 0


def test_doctrine_names_wall_breaker():
    from core.agent import SYSTEM
    assert "wall_breaker" in SYSTEM
