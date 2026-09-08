# -*- coding: utf-8 -*-
"""Hunt the api() DEFINITION — where auth rides each request."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.data_exfil import data_extract

# walk the whole 458KB doc in 3 windows for 'async api(' or 'api =' or 'api('
for off, size in ((0, 200000), (140000, 200000), (330000, 150000)):
    r = json.loads(data_extract("https://duskyr.com/a316f209d2/",
                                truncate_at=2000, tail_bytes=size, offset_bytes=off))
    w = r.get("window", "")
    for pat in (r"api\s*=[^=]", r"async api", r"\bapi\(", r"X-Verify", r"X-Admin", r"Authorization"):
        for m in list(re.finditer(pat, w))[:2]:
            j = m.start()
            print(f"[off {off} + {j}] {pat[:14]}:")
            print(w[max(0, j-250):j+450].replace("\n", " ")[:650])
            print("=====")
