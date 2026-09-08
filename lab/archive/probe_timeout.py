import sys, time
sys.path.insert(0, r"C:\Users\youcef cheriet\D\VOIDFORGE")
import voidforge_native as vn
for to_us in (1000000, 0):
    cfg = vn.emu.EmuConfig()
    cfg.arch, cfg.mode = vn.emu.ARCH_X86, vn.emu.MODE_64
    cfg.code_base = 0x400000
    cfg.stack_base = 0x20000000; cfg.stack_size = 0x200000
    cfg.entry = 0x400000; cfg.exit_addr = 0x40000B
    cfg.max_insns = 100; cfg.timeout_us = to_us
    eid = vn.emu.engine_create(cfg, b"\x90" * 10)
    t0 = time.perf_counter()
    res = vn.emu.engine_batch(eid, [b""] * 500, 0x20000000)
    dt = time.perf_counter() - t0
    ok = sum(1 for x in res if x.insns_executed == 10 and not x.fault_type)
    print(f"timeout_us={to_us}: 500 runs en {dt:.2f}s = {500/dt:.0f} exec/s · propres={ok}", flush=True)
    vn.emu.engine_destroy(eid)
