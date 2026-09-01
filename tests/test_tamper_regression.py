"""VOIDFORGE :: sqli_tamper regression — the garbled dict comprehension
referenced 'pair' out of scope: NameError on ANY url with a query string.
The fix parses the query with partition(). Regression: no NameError on
query-carrying URLs (dead port -> graceful verdict, never a crash)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import execute


def test_query_url_no_nameerror():
    # 127.0.0.1:1 = port mort -> l'outil doit rendre un verdict gracieux,
    # JAMAIS "NameError: name 'pair'" dans un TOOL ERROR
    out = execute("sqli_tamper_chain",
                  {"url": "http://127.0.0.1:1/product?id=1", "param": "id",
                   "max_requests": 5})
    assert isinstance(out, str) and out.strip()
    assert "NameError" not in out, out[:300]


def test_dead_port_graceful():
    out = execute("sqli_tamper_chain",
                  {"url": "http://127.0.0.1:1/product?id=1", "param": "id",
                   "max_requests": 5})
    # le tool rend son contrat (verdict/texte), pas une exception brute
    assert not out.startswith("TOOL ERROR [UNKNOWN]"), out[:300]
