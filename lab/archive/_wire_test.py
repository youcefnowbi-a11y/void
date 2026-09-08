# -*- coding: utf-8 -*-
"""Ground-truth test: does data_extract's JSON lane ship exact bytes?
D3 observed 'input: null' on duskyr with content_type=json — validate
against the LIVE endpoint that rejected it."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.data_exfil import data_extract

# 1) echo truth — what do the bytes look like on the wire?
r = data_extract("https://httpbin.org/post", body='{"probe": "wiretest"}',
                 content_type="json", truncate_at=2000)
print("=== httpbin echo (json string body) ===")
print(r[:800])

# 2) the failing shape: dict body via json lane
r2 = data_extract("https://httpbin.org/post", body={"probe": "dicttest"},
                  content_type="json", truncate_at=2000)
print("\n=== httpbin echo (dict body) ===")
print(r2[:800])
