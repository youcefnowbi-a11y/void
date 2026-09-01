# skill: c2_tradecraft
title: C2 Tradecraft — Beacon Discipline & Sustainable Access
when: shell,webshell,c2,beacon,persist,session,heartbeat,keep,access,sustainable

## OPERATING PRINCIPLE
A shell that answers once is an event; a shell that answers on schedule is
ACCESS. Real C2 tradecraft (Cobalt Strike malleable profiles, Sliver/Mythic
design): jitter, rotation, backoff, and patience. Loud C2 dies in hours;
disciplined C2 lives for weeks.

## CHAIN
1. webshell established via upload_webshell or cmd_exec_probe primitive.
2. shell_session(shell_url, commands=[id, pwd, cat /etc/passwd]) — verify
   output channel actually returns data (markers between echoes).
3. c2_pulse(shell_url, rounds=8, sleep_s=2) — liveness is a PERCENTAGE:
   - >=80% beats → sustainable channel, schedule real work through it
   - 50-80% → noisy channel: lengthen sleeps, reduce frequency
   - <50% → the shell is a rumor; find why before building on it
4. Work in small rounds: 2-3 commands per shell_session call, spaced out.
   Never batch 20 commands in one request — that is a signature.
5. Persistence diversity (one channel is one point of failure):
   - a second webshell path via upload_webshell (different filename/grammar)
   - cron/systemd/registry persistence via shell_exec once elevated
     (see privesc skills — persistence AFTER privilege, not before)

## BEACON DISCIPLINE (what c2_pulse does and why)
- Jitter ±40% on sleeps: fixed intervals are a detection signature (SIEM
  beaconing detectors look for regularity — irregularity is camouflage).
- UA rotation across real browser fingerprints: one UA for 100 requests
  stands out in access logs; five rotating real UAs look like traffic.
- Exponential backoff on 5xx/timeout: a beacon that hammers a dying shell
  writes its own incident report. Back away, then probe gently.
- Session id in every round: correlate rounds to one access chain in reports.

## OPSEC
- Commands that scream: `cat /etc/shadow` on round 1, mass `find /`.
  Stage reads: context first (`ls`), value second (`cat`), always small.
- Output size discipline: keep each command's stdout small; huge blobs in
  one request are anomalies in access logs. Chunk exfil.
- Never test exploits from the beacon host that you can test from outside.

## FAILURE MODES
- Beats fail but status 200: output channel blocked — try {CMD} template
  placement variant or different param name.
- Shell dies mid-chain: re-upload (bypass matrix), or re-establish via
  cmd_exec_probe primitive; keep both paths armed.
- WAF starts blocking the shell URL: change the param name and shell
  filename; rotate, do not fight the WAF head-on.
