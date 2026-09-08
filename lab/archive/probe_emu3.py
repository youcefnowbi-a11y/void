import sys
sys.path.insert(0, r"C:\Users\youcef cheriet\D\VOIDFORGE")
print("A", flush=True)
import voidforge_native as vn
print("B", flush=True)
cfg = vn.emu.EmuConfig()
cfg.arch, cfg.mode = vn.emu.ARCH_X86, vn.emu.MODE_64
cfg.code_base = 0x400000
cfg.stack_base = 0x20000000
cfg.stack_size = 0x200000
cfg.entry = 0x400000
cfg.exit_addr = 0x40000B
cfg.max_insns = 100
cfg.timeout_us = 1000000
print("C", flush=True)
eid = vn.emu.engine_create(cfg, b"\x90" * 10 + b"\xC3")
print("D eid =", eid, flush=True)
if eid >= 0:
    r = vn.emu.engine_run(eid, b"", 0x20000000)
    print("E run:", r.insns_executed, r.fault_type, r.elapsed_us, "us", flush=True)
    import time
    t0 = time.perf_counter()
    res = vn.emu.engine_batch(eid, [b""] * 1000, 0x20000000)
    dt = time.perf_counter() - t0
    print(f"F batch1000: {dt:.2f}s = {1000/dt:.0f} exec/s", flush=True)
    vn.emu.engine_destroy(eid)
