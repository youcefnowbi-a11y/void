"""VOIDFORGE :: sandboxed subprocess runner for heavy jobs."""
import subprocess, shlex, sys

def run(cmd, cwd=None, timeout_minutes=30, shell=False):
    """Run arbitrary command isolated. Returns (exit, stdout_tail)."""
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=shell,
                           capture_output=True, timeout=timeout_minutes * 60,
                           encoding="utf-8", errors="replace")
        tail = (r.stdout or "")[-6000:]
        err = (r.stderr or "")[-2000:]
        return r.returncode, tail + (f"\n[stderr]\n{err}" if err.strip() else "")
    except subprocess.TimeoutExpired:
        return -9, f"TIMEOUT after {timeout_minutes}min"
    except Exception as ex:
        return -1, str(ex)

def python(script, args="", **kw):
    return run(f'"{sys.executable}" -u "{script}" {args}', **kw)
