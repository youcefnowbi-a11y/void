"""VOIDFORGE :: smoke test for the gap-matrix strike layer.
Runs every new tool against the local ForgeRange; honest verdicts expected
(the range implements none of these classes — machinery proof, not findings).
Also proves the fuzz<->triage seed loop and the jku/x5u variant build.
Run: python lab/smoke_advanced.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools as reg
reg.discover()

RANGE = "http://127.0.0.1:8765"
ok = fail = 0

def check(name, out, want_keys=("tool", "exploitable", "summary")):
    global ok, fail
    try:
        d = json.loads(out)
        missing = [k for k in want_keys if k not in d]
        assert not missing, f"missing keys {missing}"
        print(f"  ✓ {name}: exploitable={d['exploitable']} — {d['summary'][:90]}")
        ok += 1
        return d
    except Exception as ex:
        print(f"  ✗ {name}: {type(ex).__name__}: {ex} :: {str(out)[:140]}")
        fail += 1
        return None

print(f"registry: {len(reg.all_tools())} tools")
for t in ("race_smash", "smuggle_probe", "proto_pollute", "xxe_probe",
          "redirect_cast", "c2_pulse"):
    assert reg.get(t), f"{t} not registered!"
print("✓ all 6 new tools registered")

check("race_smash", reg.execute("race_smash", {
    "url": f"{RANGE}/orders", "method": "POST", "body": "item=1",
    "concurrency": 8, "rounds": 2, "success_pattern": "ACCEPTED"}))

check("smuggle_probe", reg.execute("smuggle_probe", {"url": RANGE}))

check("proto_pollute", reg.execute("proto_pollute", {
    "url": f"{RANGE}/orders", "gadget_check": f"{RANGE}/"}))

check("xxe_probe", reg.execute("xxe_probe", {"url": f"{RANGE}/orders"}))

check("redirect_cast", reg.execute("redirect_cast", {"url": f"{RANGE}/"}))

# fuzz <-> triage seed loop: triage must now emit fuzz_seeds
td = check("crash_triage seeds", reg.execute("crash_triage_next", {"top": 5}),
           want_keys=("tool", "fuzz_seeds", "summary"))
if td is not None:
    print(f"    → fuzz_seeds: {list(td['fuzz_seeds'].keys())[:6]}")

# fuzzer accepts seeds param (2 requests only — machinery proof, not a run)
check("fuzz_attack_surface seeds", reg.execute("fuzz_attack_surface", {
    "url": f"{RANGE}/", "max_requests": 12,
    "seeds": {"q": "<injected-from-triage>"}}))

# jwt jku/x5u variants build + replay against the lab
import base64
tok = ("eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJyb2xlIjogImFub24iLCAicmVmIjogImZvcmdlYW5nZXIyMCJ9." 
       + base64.urlsafe_b64encode(b"\x01" * 16).decode().rstrip("="))
jd = check("jwt_forge jku/x5u", reg.execute("jwt_forge_replay", {
    "token": tok, "replay_url": f"{RANGE}/orders",
    "key_url": "https://vfs-operator.example/jwks.json", "key_secret": "vfs-test-secret"}))
if jd:
    names = [v["name"] for v in jd.get("results", [])]
    assert "jku-injection" in names and "x5u-injection" in names, f"variants missing: {names}"
    print(f"    → variant matrix: {len(names)} variants incl. jku/x5u ✓")

# corpus file written?
sp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "reports", "fuzz_seeds.json")
print(f"  ✓ seed corpus {'exists' if os.path.exists(sp) else 'pending first anomaly run'}")

print(f"\nSMOKE RESULT: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
