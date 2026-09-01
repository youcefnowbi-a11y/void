import os, sys, shutil, hashlib
sys.path.insert(0, r"C:\Users\youcef cheriet\D\VOIDFORGE")
import voidforge_native as vn
d = r"C:\Users\youcef cheriet\D\VOIDFORGE\lab\tmp_tri"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
cfg = vn.triage.TriageConfig(); cfg.crash_dir = d; cfg.top_frames = 3
body = "ERROR: AddressSanitizer: SEGV on address 0x41414141\nWRITE of size 4\n    #0 0x7f0 in fA (a.c:0)\n    #1 0x7f1 in fB (a.c:1)\n    #2 0x7f2 in fC (a.c:2)\n"
open(os.path.join(d, "c1"), "w").write(body)
open(os.path.join(d, "c1_dup"), "w").write(body)
r = vn.triage.triage_crashes(cfg)
print("(a) 1 unique + 1 dupe ->", len(r), "uniques · dupes:", r[0].duplicate_count)
print("    type:", r[0].fault_type, "· rank:", r[0].exploitability, "(attendu 6: addr 0x41414141 + WRITE)")
print("    frames:", r[0].stack_frames)
print("    hash:", r[0].hash[:16], "· match hashlib:", r[0].hash == hashlib.sha256(("fA|fB|fC|").encode()).hexdigest())
open(os.path.join(d, "c2"), "w").write(body.replace("fA", "fZ"))
r2 = vn.triage.triage_crashes(cfg)
print("(b) 2 uniques ->", len(r2), "· ordre decroissant:", [c.exploitability for c in r2])
