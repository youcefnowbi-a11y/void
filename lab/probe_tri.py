import os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import voidforge_native as vn
d = r"C:\Users\youcef cheriet\D\VOIDFORGE\lab\tmp_tri"
shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
cfg = vn.triage.TriageConfig(); cfg.crash_dir = d; cfg.top_frames = 3
print("(a) dossier vide...")
r = vn.triage.triage_crashes(cfg); print("   OK ->", len(r), "crash(es)")
body = "ERROR: AddressSanitizer: SEGV on address 0x41414141\nWRITE of size 4\n    #0 0x7f0 in fA (a.c:0)\n"
open(os.path.join(d, "c1"), "w").write(body)
print("(b) 1 fichier...")
r = vn.triage.triage_crashes(cfg); print("   OK ->", len(r), "*", r[0].fault_type, r[0].exploitability)
open(os.path.join(d, "c2"), "w").write(body)
print("(c) 2 fichiers (1 dupe)...")
r = vn.triage.triage_crashes(cfg); print("   OK ->", len(r), "dupes:", r[0].duplicate_count)
