# -*- coding: utf-8 -*-
"""Fix pack_meta counts + manifest after DIFF graft."""
import io, json

FEED = "data/grimoire.feed.json"
MAN = "data/grimoire_manifest.json"

feed = json.load(io.open(FEED, encoding="utf-8"))
techs = feed["techniques"]
pm = feed.get("pack_meta") or {}
pm["technique_count"] = len(techs)
pm["domain_count"] = len({t.get("_domain_code", "?") for t in techs})
feed["pack_meta"] = pm

# bump indexes if they carry counts
ix = feed.get("indexes")
if isinstance(ix, dict):
    for k in ("techniques", "technique_count"):
        if k in ix:
            ix[k] = len(techs)

json.dump(feed, io.open(FEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

man = json.load(io.open(MAN, encoding="utf-8"))
man["_meta"]["version"] = "1.5.0"
json.dump(man, io.open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("pack_meta counts fixed:", pm["technique_count"], "techniques /",
      pm["domain_count"], "domains")
