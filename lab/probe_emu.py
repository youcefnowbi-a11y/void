import sys, time
sys.path.insert(0, r"C:\Users\youcef cheriet\D\VOIDFORGE")
import voidforge_native as vn
cfg = vn.emu.EmuConfig()
cfg.arch = 3; cfg.mode = 8
cfg.code_base = 0x400000
cfg.entry = 0x400000; cfg.exit_addr = 0x40000B
cfg.stack_base = 0x20000000; cfg.stack_size = 0x200000
cfg.timeout_us = 1000000; cfg.max_insns = 100
eid = vn.emu.engine_create(cfg, b"\x90" * 10)
r = vn.emu.engine_run(eid, b"", 0x20000000)
print("nop sled: insns =", r.insns_executed, "· fault =", r.fault_type or "aucun", "·", r.elapsed_us, "µs")
t0 = time.perf_counter()
res = vn.emu.engine_batch(eid, [b""] * 1000, 0x20000000)
dt = time.perf_counter() - t0
print(f"batch 1000: {dt:.2f}s → {1000/dt:.0f} exec/s")
vn.emu.engine_destroy(eid)
