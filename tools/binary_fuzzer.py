"""TOOL: binary_fuzzer — coverage-guided fuzzing with native C++ hot cores.

Strategies: unicorn (emulation), native (AFL++/libFuzzer via WSL), network
(stateful protocol fuzzing). Python handles seed scheduling; C++ handles
the mutation-and-execute loops (engine_batch = one FFI crossing, GIL free).

Requires: voidforge_native.pyd in VOIDFORGE root (see cpp/README.md).
"""
import json, math, os, random, time
from tools import register
from tools._exploit_lib import verdict

try:
    from voidforge_native import emu, triage, net, h2race
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False

SEED_MAX_BYTES = 4096
SEEDS_MAX = 256
BATCH = 512          # inputs per FFI crossing
ROUND_BUDGET_S = 20  # max seconds per mutation round


def _ucb1_select(arms: list, t: int) -> int:
    """UCB1 bandit: select the arm with highest upper confidence bound."""
    best_i, best_score = 0, -1.0
    for i, arm in enumerate(arms):
        if arm["pulls"] == 0:
            return i  # explore unpulled arms first
        exploit = arm["reward"] / arm["pulls"]
        explore = math.sqrt(2.0 * math.log(t) / arm["pulls"])
        score = exploit + explore
        if score > best_score:
            best_i, best_score = i, score
    return best_i


def _mutate(data: bytes, rng: random.Random) -> bytes:
    """One Python-side mutation (cheap; the C++ core does the heavy loop)."""
    if not data:
        return bytes([rng.randint(0, 255)])
    b = bytearray(data)
    op = rng.randint(0, 5)
    if op == 0 and len(b) > 1:                       # bit flip
        i = rng.randrange(len(b))
        b[i] ^= 1 << rng.randint(0, 7)
    elif op == 1 and len(b) > 1:                     # byte randomize
        i = rng.randrange(len(b))
        b[i] = rng.randint(0, 255)
    elif op == 2 and len(b) >= 4:                    # interesting int32 LE
        i = rng.randrange(len(b) - 3)
        v = rng.choice([0, 1, -1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF,
                        0x41414141, 0x61616161])
        b[i:i + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")
    elif op == 3 and len(b) >= 2:                    # interesting int16 LE
        i = rng.randrange(len(b) - 1)
        v = rng.choice([0, 1, -1, 0x7FFF, 0x8000, 0xFFFF])
        b[i:i + 2] = (v & 0xFFFF).to_bytes(2, "little")
    elif op == 4:                                    # splice self
        if len(b) > 8:
            a, c = rng.randrange(len(b)), rng.randrange(len(b))
            a, c = min(a, c), max(a, c)
            b = b[:a] + b[c:]
    else:                                            # extend
        b += bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 16)))
    return bytes(b[:SEED_MAX_BYTES])


def _load_corpus(corpus_dir: str) -> list:
    seeds = []
    try:
        for name in sorted(os.listdir(corpus_dir))[:SEEDS_MAX]:
            p = os.path.join(corpus_dir, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    d = f.read(SEED_MAX_BYTES)
                if d:
                    seeds.append(d)
    except OSError:
        pass
    if not seeds:
        seeds = [b"\x00" * 16, b"A" * 16, b"\xff" * 16,
                 b"GET / HTTP/1.1\r\n\r\n"]
    return seeds


def _arch_constants(arch: str):
    m = {"x86": (emu.ARCH_X86, emu.MODE_32),
         "x64": (emu.ARCH_X86, emu.MODE_64),
         "arm": (emu.ARCH_ARM, emu.MODE_32),
         "arm64": (emu.ARCH_ARM64, emu.MODE_64)}
    return m.get(arch, (emu.ARCH_X86, emu.MODE_64))


@register(
    name="binary_fuzz_run",
    desc="EXPLOIT: Coverage-guided binary fuzzing via Unicorn emulation "
         "(native C++ hot core). Finds memory corruption bugs in parsers, "
         "decoders, and protocol handlers. Returns crashes ranked by "
         "exploitability.",
    params={"type": "object", "properties": {
        "target_path": {"type": "string",
                        "description": "Path to binary / raw code to fuzz"},
        "corpus_dir": {"type": "string",
                        "description": "Optional seed dir; omitted/null = synthetic seeds from the target itself"},
        "mode": {"type": "string", "enum": ["auto", "unicorn", "native", "network"],
                 "default": "auto"},
        "minutes": {"type": "integer", "default": 10},
        "arch": {"type": "string", "enum": ["x86", "x64", "arm", "arm64"],
                 "default": "x64"},
    }, "required": ["target_path"]},
    danger="loud"
)
def binary_fuzz_run(target_path, corpus_dir=None, mode="auto", minutes=10, arch="x64"):
    if not NATIVE_AVAILABLE:
        return verdict("binary_fuzz_run", False,
                       "voidforge_native C++ module not built — run: "
                       "cd cpp && cmake -B build && cmake --build build")

    if not os.path.isfile(target_path):
        return verdict("binary_fuzz_run", False,
                       f"target introuvable : {target_path}")

    with open(target_path, "rb") as f:
        code = f.read(1 << 20)          # 1MB code cap

    if corpus_dir:
        crash_dir = os.path.join(os.path.dirname(os.path.abspath(corpus_dir)),
                                 "crashes")
    else:
        crash_dir = os.path.join(os.path.dirname(os.path.abspath(target_path)),
                                 "crashes")
    os.makedirs(crash_dir, exist_ok=True)

    arch_c, mode_c = _arch_constants(arch)
    stack_base = 0x20000000
    cfg = emu.EmuConfig()
    cfg.arch, cfg.mode = arch_c, mode_c
    cfg.code_base = 0x400000
    cfg.stack_base = stack_base
    cfg.stack_size = 0x200000
    cfg.entry = cfg.code_base
    cfg.exit_addr = 0                    # stop on max_insns / timeout
    cfg.max_insns = 100000
    cfg.timeout_us = 5000000
    INPUT_ADDR = stack_base              # input mapped at stack bottom

    engine = emu.engine_create(cfg, code)
    if engine < 0:
        return verdict("binary_fuzz_run", False,
                       "engine_create failed — code/stack mapping rejected")

    corpus = _load_corpus(corpus_dir) if corpus_dir else [code[i:i + 256]
                                                          for i in range(0, min(len(code), 2048), 256)] or [code[:256]]
    cumulative = bytearray(65536)
    rng = random.Random(0x0D15EA5E)
    arms = [{"kind": "flip", "pulls": 0, "reward": 0.0},
            {"kind": "int32", "pulls": 0, "reward": 0.0},
            {"kind": "splice", "pulls": 0, "reward": 0.0},
            {"kind": "extend", "pulls": 0, "reward": 0.0}]

    t_end = time.time() + max(1, int(minutes)) * 60
    total_execs = 0
    crashes = []          # (filename, fault_type, fault_addr, coverage_pct)
    new_coverage_inputs = 0
    timeout = False

    try:
        while time.time() < t_end and not timeout:
            # UCB1 picks this round's mutation flavor
            t_round = sum(a["pulls"] for a in arms) + 1
            arm_i = _ucb1_select(arms, t_round)
            kind = arms[arm_i]["kind"]

            inputs, metas = [], []
            while len(inputs) < BATCH and time.time() < t_end:
                parent = rng.choice(corpus)
                inputs.append(_mutate(parent, rng) if kind != "extend"
                              else parent + bytes(rng.randint(0, 255)
                                                  for _ in range(rng.randint(1, 32))))
                metas.append(kind)
            if not inputs:
                break

            t0 = time.time()
            results = emu.engine_batch(engine, inputs, INPUT_ADDR)
            dt = max(time.time() - t0, 1e-9)
            got_new = 0.0

            for inp, res, kind_i in zip(inputs, results, metas):
                total_execs += 1
                cov = res.coverage_bytes()
                newly = any(c and not cumulative[i]
                            for i, c in enumerate(cov))
                if newly:
                    got_new += 1.0
                    new_coverage_inputs += 1
                    cumulative = bytes(a | b for a, b in zip(cumulative, cov))
                    corpus.append(inp)
                    if len(corpus) > 4096:
                        corpus.pop(rng.randrange(len(corpus)))
                if res.fault_type and res.fault_type not in (
                        "NATIVE_UNAVAILABLE", "BAD_ENGINE_ID"):
                    fn = f"crash_{total_execs:08d}_{res.fault_type}"
                    with open(os.path.join(crash_dir, fn), "wb") as f:
                        f.write(inp)
                    crashes.append((fn, res.fault_type,
                                    hex(res.fault_addr), res.insns_executed))
                if res.timeout:
                    timeout = True

            arms[arm_i]["pulls"] += 1
            arms[arm_i]["reward"] += got_new

        # ---- triage the crash dir via the C++ core ----
        tri_cfg = triage.TriageConfig()
        tri_cfg.crash_dir = crash_dir
        tri_cfg.top_frames = 3
        tri_cfg.symbolize = False
        ranked = triage.triage_crashes(tri_cfg)
        ranked_out = [{"hash": c.hash, "exploitability": c.exploitability,
                       "fault_type": c.fault_type, "fault_addr": hex(c.fault_addr),
                       "dupes": c.duplicate_count, "file": c.representative}
                      for c in ranked[:10]]
        exploitable = any(c["exploitability"] >= 4 for c in ranked_out)

        return verdict("binary_fuzz_run",
                       bool(ranked_out) or new_coverage_inputs > 0,
                       f"{total_execs} execs · {len(corpus)} seeds évolutifs · "
                       f"{len(ranked)} crashes uniques "
                       f"({sum(1 for c in ranked_out if c['exploitability'] >= 4)} "
                       f"exploitables ≥4)",
                       evidence={"crashes": ranked_out, "execs": total_execs,
                                 "coverage_inputs": new_coverage_inputs,
                                 "crash_dir": crash_dir})
    finally:
        emu.engine_destroy(engine)


@register(
    name="crash_triage_rank",
    desc="Deduplicate and rank crashes by exploitability. Stack-hash dedup, "
         "7-level severity ranking (RIP control → DoS).",
    params={"type": "object", "properties": {
        "crash_dir": {"type": "string"},
        "binary_path": {"type": "string"},
    }, "required": ["crash_dir"]},
    danger="safe"
)
def crash_triage_rank(crash_dir, binary_path=""):
    if not NATIVE_AVAILABLE:
        return verdict("crash_triage_rank", False,
                       "voidforge_native not available")
    cfg = triage.TriageConfig()
    cfg.crash_dir = crash_dir
    cfg.binary_path = binary_path
    cfg.top_frames = 3
    cfg.symbolize = bool(binary_path)
    results = triage.triage_crashes(cfg)
    crashes = [{"hash": c.hash, "exploitability": c.exploitability,
                "fault_type": c.fault_type, "fault_addr": hex(c.fault_addr),
                "frames": c.stack_frames, "dupes": c.duplicate_count,
                "file": c.representative} for c in results]
    exploitable = any(c["exploitability"] >= 4 for c in crashes)
    return verdict("crash_triage_rank", exploitable or bool(crashes),
                   f"{len(crashes)} unique crashes, "
                   f"{sum(1 for c in crashes if c['exploitability'] >= 4)} "
                   f"likely exploitable",
                   evidence=crashes[:10])


@register(
    name="h2_race_attack",
    desc="EXPLOIT: HTTP/2 single-packet race — N requests in one TCP segment. "
         "Tests single-use guards (OTP, auth codes, coupons).",
    params={"type": "object", "properties": {
        "host": {"type": "string"},
        "port": {"type": "integer", "default": 443},
        "method": {"type": "string", "default": "POST"},
        "path": {"type": "string"},
        "headers": {"type": "object"},
        "body": {"type": "string", "default": ""},
        "n_streams": {"type": "integer", "default": 20},
    }, "required": ["host", "path"]},
    danger="loud"
)
def h2_race_attack(host, path, port=443, method="POST", headers=None,
                   body="", n_streams=20):
    if not NATIVE_AVAILABLE:
        return verdict("h2_race_attack", False,
                       "voidforge_native not available")
    cfg = h2race.RaceConfig()
    cfg.host = host
    cfg.port = port
    cfg.use_tls = (port == 443)
    cfg.warmup_streams = 1
    cfg.response_timeout_us = 5_000_000
    cfg.requests = []
    for _ in range(max(1, min(int(n_streams), 200))):
        req = h2race.RaceRequest()
        req.method = method
        req.path = path
        req.headers = list((headers or {}).items())
        req.body = body
        cfg.requests.append(req)
    result = h2race.execute(cfg)
    return verdict("h2_race_attack",
                   result.successful_2xx > 1,
                   f"{result.successful_2xx}/{n_streams} succeeded in "
                   f"{result.send_wall_us}µs — {result.interpretation}",
                   evidence={"responses": len(result.responses),
                             "distinct_bodies": result.distinct_bodies,
                             "wall_us": result.send_wall_us})
