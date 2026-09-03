# -*- coding: utf-8 -*-
"""Guard tests — the binary lane (triage, strings, disasm, live fuzz, privesc)."""
import json
import os
import struct
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir))
from tools.binary_lane import (_entropy, _parse_pe, _parse_battery_win,
                               _parse_battery_lin, bin_triage, bin_disasm,
                               bin_fuzz_live)
from tools import all_tools, _REGISTRY
from tools._phases import phase_for


def _craft_pe(path):
    """Minimal PE64: .text (low entropy) + UPX0 (high entropy, big)."""
    data = bytearray(0x2800 + 8192)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIH", data, 0x84, 0x8664, 2, 0, 0, 0, 240)
    opt = 0x84 + 20  # coff(0x84) + 20 = 0x98 — the parser's own arithmetic
    struct.pack_into("<H", data, opt, 0x20B)          # PE64
    struct.pack_into("<I", data, opt + 16, 0x1000)    # entry rva
    struct.pack_into("<Q", data, opt + 24, 0x140000000)
    sec0 = opt + 240
    # .text — exec, low-entropy zeros, 1KB raw (no hint: below size gate)
    data[sec0:sec0 + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, sec0 + 8, 0x1000, 0x1000, 0x400, 0x400)
    struct.pack_into("<I", data, sec0 + 36, 0x60000020)
    # UPX0 — exec, 8KB of urandom → entropy hint
    data[sec0 + 40:sec0 + 44] = b"UPX0"
    struct.pack_into("<IIII", data, sec0 + 48, 0x2000, 0x2000, 0x2000, 0x800)
    struct.pack_into("<I", data, sec0 + 76, 0x60000020)
    data[0x800:0x800 + 8192] = os.urandom(8192)
    with open(path, "wb") as f:
        f.write(bytes(data))


def test_entropy_basics():
    assert _entropy(b"\x00" * 1024) == 0.0
    assert _entropy(os.urandom(4096)) > 7.5


def test_parse_pe_walks_headers_and_flags_packer(tmp_path):
    p = str(tmp_path / "sample.exe")
    _craft_pe(p)
    info = _parse_pe(open(p, "rb").read())
    assert info["format"] == "PE" and info["arch"] == "x64" and info["bits"] == 64
    assert info["entry_rva"] == 0x1000
    assert [s["name"] for s in info["sections"]] == [".text", "UPX0"]
    assert any("UPX0" in h for h in info["packer_hints"])


def test_triage_tool_end_to_end(tmp_path):
    p = str(tmp_path / "sample.exe")
    _craft_pe(p)
    out = json.loads(bin_triage(p))
    assert out["exploitable"] is True
    assert out["evidence"]["format"] == "PE"
    assert "packed-suspect" in out["summary"]


def test_disasm_reads_instructions(tmp_path):
    p = str(tmp_path / "code.bin")
    with open(p, "wb") as f:
        f.write(b"\x90\x90\x90\x90" + b"\x48\x89\xc8\xc3")  # nops; mov rax,rcx; ret
    out = json.loads(bin_disasm(p, offset=4, length=8, arch="x64"))
    asm = " ".join(out["evidence"]["asm"])
    assert "ret" in asm and "mov" in asm


def test_live_fuzz_finds_scripted_crash(tmp_path):
    # NB: os._exit(big_code) est TRONQUÉ par le runtime C Windows (exit→1);
    # le seul crash exit-code honnête depuis Python = ExitProcess direct.
    script = tmp_path / "target.py"
    script.write_text(
        "import ctypes, sys\n"
        "d = open(sys.argv[1], 'rb').read()\n"
        "if d != b'OK':\n"
        "    ctypes.windll.kernel32.ExitProcess(0xC0000005)\n"
        "ctypes.windll.kernel32.ExitProcess(0)\n")
    seed = tmp_path / "seed.bin"
    seed.write_bytes(b"OK")
    # template honnête : le script EST la cible appelée, l'input en argument
    # (shlex exige des guillemets : "youcef cheriet" a des espaces)
    tmpl = f'"{script}" {{INPUT}}'
    out = json.loads(bin_fuzz_live(sys.executable, seed=str(seed),
                                   iterations=8, max_total_s=60,
                                   per_run_timeout_s=5,
                                   args_template=tmpl))
    assert out["crashed"] is True and out["evidence"]["crashes"], \
        "scripted crasher went undetected"
    for c in out["evidence"]["crashes"]:
        assert os.path.isfile(c["input_file"])
        assert c["exit_code"] == 0xC0000005


def test_privesc_parsers_rank_real_signals():
    win_text = ("SeImpersonatePrivilege        Enabled\n"
                "AlwaysInstallElevated REG_DWORD 0x1\n"
                "C:\\My App\\server.exe    Auto   LocalSystem\n")
    f = _parse_battery_win(win_text)
    joined = " ".join(x["check"] for x in f)
    assert "potato" in " ".join(x["why"] for x in f).lower() or \
        "SeImpersonate" in joined
    assert any("AlwaysInstallElevated" in x["check"] for x in f)
    assert any("unquoted service path" in x["check"] for x in f)
    lin_text = ("root ALL=(ALL) NOPASSWD: /usr/bin/find\n"
                "-rw-rw-rw- 1 root root 2469 /etc/passwd\n")
    fl = _parse_battery_lin(lin_text)
    assert any("NOPASSWD" in x["check"] for x in fl)
    assert any("/etc/passwd world-writable" in x["check"] for x in fl)


def test_registry_and_phases_know_the_lane():
    all_tools()  # triggers discover()
    for name in ("bin_triage", "bin_strings", "bin_disasm",
                 "bin_fuzz_live", "privesc_enum"):
        assert name in _REGISTRY, f"{name} not registered"
    assert phase_for("privesc_enum") == "post-exploit"
    assert phase_for("bin_fuzz_live") == "exploit"
    assert phase_for("bin_triage") == "surface"
