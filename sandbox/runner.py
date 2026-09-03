"""VOIDFORGE :: sandboxed subprocess runner for heavy jobs."""
import subprocess, shlex, sys

# ── V1 (audit 1.1): the old `[-6000:]` tail kept only the LAST 6KB —
# nmap's XML root tag lives at the START of the stream, so any scan with
# more than ~6KB of output was amputated of <nmaprun>, and the parser
# returned [] (blind). Nuclei JSONL lost its first findings + the
# appended [stderr] block corrupted the last line. The runner now keeps
# head AND tail, separates stderr, and returns structured fields.
_HEAD = 24000     # keep the beginning (XML roots, first findings)
_TAIL = 16000     # keep the end (summaries, last lines)
_ERR = 4000


def run(cmd, cwd=None, timeout_minutes=30, shell=False):
    """Run arbitrary command isolated.
    Returns (exit, stdout_text) — stdout_text carries head+tail with a
    marker in between; stderr rides separately via stderr_tail so JSONL
    parsers never trip on it."""
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=shell,
                           capture_output=True, timeout=timeout_minutes * 60,
                           encoding="utf-8", errors="replace")
        out = r.stdout or ""
        err = (r.stderr or "")[-_ERR:]
        if len(out) > _HEAD + _TAIL:
            body = (out[:_HEAD] + "\n…[output truncated — middle elided]\n"
                    + out[-_TAIL:])
        else:
            body = out
        return r.returncode, body, (err if err.strip() else "")
    except subprocess.TimeoutExpired:
        return -9, f"TIMEOUT after {timeout_minutes}min", ""
    except Exception as ex:
        return -1, str(ex), ""


def python(script, args="", **kw):
    return run(f'"{sys.executable}" -u "{script}" {args}', **kw)


# ── backward compatibility shim: old 2-tuple callers ────────────────
def run2(cmd, **kw):
    """Legacy 2-field contract (exit, output) for callers that don't
    want stderr separately — stderr is appended, clearly delimited."""
    code, out, err = run(cmd, **kw)
    if err:
        out = out + (f"\n[stderr]\n{err}" if out else err)
    return code, out
