import sys
sys.path.insert(0, r"C:\Users\youcef cheriet\D\VOIDFORGE")
print("A: pre-import", flush=True)
import voidforge_native as vn
print("B: imported", flush=True)
cfg = vn.emu.EmuConfig()
cfg.arch = 3; cfg.mode = 8
cfg.code_base = 0x400000
cfg.entry = 0x400000; cfg.exit_addr = 0x40000A
cfg.stack_base = 0x20000000; cfg.stack_size = 0x200000
cfg.timeout_us = 1000000; cfg.max_insns = 100
print("C: config ok", flush=True)
eid = vn.emu.engine_create(cfg, b"\x90" * 10)
print("D: created eid =", eid, flush=True)
r = vn.emu.engine_run(eid, b"", 0x20000000)
print("E: run ->", r.insns_executed, r.fault_type, r.elapsed_us, "us", flush=True)
