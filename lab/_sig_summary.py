# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for run in ("A", "B"):
    p = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "lab", f"calib_{run}", "capture.json")
    d = json.load(open(p, encoding="utf-8"))
    print(f"=== MISSION {run} ===")
    print(" rounds:", d["rounds"], "| tool_calls:", d["tool_calls"],
          "| wall:", d["wall_clock_s"], "s")
    print(" skips:", json.dumps(d["skip_summary"])[:220])
    print(" doctrine:", d["doctrine_pre_entries"], "->",
          d["doctrine_post_entries"], "| plays at end:",
          d["plays_loaded_at_end"])
    types = {}
    for e in d["events"]:
        types[e["type"]] = types.get(e["type"], 0) + 1
    print(" event types:", types)
    for e in d["events"]:
        if e["type"] == "system":
            print(f"  [{e['_t']:7.1f}s] {e['text'][:105]}")
