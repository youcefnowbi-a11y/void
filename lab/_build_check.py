# Build DEV + vérif des fixes audit dans le bundle
import os, re, subprocess, sys

FE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "web", "frontend")
r = subprocess.run(["cmd", "/c", "npm", "run", "build"], cwd=FE,
                   capture_output=True, text=True)
tail = (r.stdout or "").strip().splitlines()[-3:]
print("\n".join(tail))
if r.returncode != 0:
    print((r.stderr or "")[-400:]); sys.exit(1)

js = None
for fn in os.listdir(os.path.join(FE, "dist", "assets")):
    if fn.startswith("index-") and fn.endswith(".js"):
        js = open(os.path.join(FE, "dist", "assets", fn), encoding="utf-8").read()
        name = fn
print(f"\nbundle: {name} ({len(js)/1e3:.0f} KB)")
checks = {
    "VOIDFORGE residue": "VOIDFORGE" in js,
    "voidforge- asset refs": "voidforge-" in js,
    "mission_aborted case": "mission_aborted" in js,
    "graph colon join": "n.k + ':' + n.v" in js,
    "severity normalize (critical)": "verdict === true ? 'critical'" in js,
    "M1 provider full POST": "max_tool_rounds: provider" in js,
    "M2 elapsed recompute": "d.elapsed" in js,
    "M5 strike error toast": "strike_blocked" in js,
    "chat origin guard": "ev.origin !== 'chat'" in js,
}
bad = 0
for label, present in checks.items():
    want = label.startswith(("VOIDFORGE", "voidforge"))
    ok = (not present) if want else present
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: {'present' if present else 'absent'}")
    if not ok:
        bad += 1
sys.exit(1 if bad else 0)
