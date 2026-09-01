"""Bridge: the auth_state_engine (research/) becomes an ARSENAL tool.
Once registered, the LLM sees it in her schemas — the campaign's engine
stops being a lab artifact and becomes a strike she can call by name.
"""
import os
import subprocess
import sys

from tools import register

_ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "research", "auth_state_engine.py")


@register(
    name="auth_state_audit",
    desc="AUTH 0DAY ENGINE: session-aware state-machine audit of an OAuth2/OIDC/magic-link/MFA "
         "flow — infers the flow machine from live HTTP traces, runs the 4 LTL runtime monitors "
         "(no-skip, no-replay, binding-preservation, entropy-floor), token algebra (JWT alg-confusion/"
         "kid/jku surfaces), and an executed 16-thread race harness on single-use endpoints. "
         "Returns the verdict() contract with per-flaw CAUGHT/MISSED and exact HTTP PoCs. "
         "v1.0.0 — lab-proven 7/7.",
    params={
        "type": "object",
        "properties": {
            "target": {"type": "string",
                       "description": "base URL of the auth flow (e.g. https://target.tld — must expose "
                                      "the flow endpoints and /health is NOT required)"},
            "report": {"type": "string",
                       "description": "optional path for the markdown acceptance report"},
            "json_out": {"type": "string",
                         "description": "optional path for the full verdict() JSON"},
        },
        "required": ["target"],
    },
    danger="strike",
)
def auth_state_audit(target: str, report: str = "", json_out: str = "") -> str:
    cmd = [sys.executable, _ENGINE, "--live", "--target", target]
    if report:
        cmd += ["--report", report]
    if json_out:
        cmd += ["--json", json_out]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        return "TOOL ERROR [TIMEOUT] auth_state_audit exceeded 600s — try a narrower flow"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    lines = out.splitlines()
    # the stdout tail carries the flaws JSON block — keep it readable
    tail = "\n".join(lines[-30:]) if len(lines) > 30 else out
    head = err.splitlines()[-3:] if err else []
    return (f"exit={r.returncode}\n{tail}"
            + ("\n[stderr] " + " | ".join(head) if head else ""))[:20000]
