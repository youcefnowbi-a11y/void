# skill: binary_lane
title: Binary Lane — static recon, crash hunting, foothold escalation
when: binary,executable,pe,elf,disassembly,disasm,fuzz,crash,triage,privesc,escalation,root,system,webshell,foothold,packed,shellcode

## OPERATING PRINCIPLE
Every web foothold is a door into a machine; every binary you can pull is a
script that lies. The lane is a LADDER, never a leap: triage tells you WHAT
it is, strings tell you what it TOUCHES, disassembly tells you what it DOES,
fuzzing finds where it BREAKS, privesc tells you WHERE the machine lets you
climb. Never skip a rung because a hunch feels expensive — the hunch costs
minutes, the blind leap costs the campaign.

## THE LADDER
1. **bin_triage** — format/arch/sections/entropy/imports. High entropy on an
   executable section = packed: note it, do NOT disassemble the blob, the
   real code only exists after unpacking (run it in a disposable VM, dump
   memory, re-triage the dump).
2. **bin_strings** — URLs, paths, registry keys, base64 blobs. This is the
   fastest map of the binary's world. Chasing a URL found here often jumps
   you straight back to the web lane with a NEW target.
3. **bin_disasm** — read the entry point, then every function your strings
   hinted at. You are looking for: input parsing loops, size assumptions
   (memcpy with attacker-controlled length), format-string sinks
   (printf of user-controlled data), command construction
   (system/sprintf chains).
4. **Crash hunting** — binary_fuzz_run (Unicorn emulation: logic bugs in
   mapped code, fast, no loader) AND bin_fuzz_live (real process: real
   imports/CRT/relocations — crashes emulation cannot see). One crash is a
   rumor: reproduce it, then crash_triage_rank.
5. **privesc_enum** — you have a webshell, the machine is below you:
   whoami/priv (SeImpersonate = potato family), AlwaysInstallElevated,
   unquoted service paths, sudo -l NOPASSWD, SUID list, writable
   /etc/passwd. Every finding names the technique — execute it, PROVE it
   (whoami = SYSTEM / root id), seal with evidence_pack.

## PROOF DISCIPLINE
A crash without a saved crashing input is an anecdote. A privesc without a
`whoami` screenshot-equivalent in the extraction index is an opinion. The
binary lane obeys the same law as the web lane: demonstrated end-state or
honest POTENTIAL marking.

## CHAIN RULES
- privesc_windows + privesc_linux skills hold the per-technique details —
  skill_load them the moment privesc_enum returns a finding.
- A binary that phones home (strings) may be a better target THROUGH its
  server than through its code — re-enter the web lane.
- Malware samples you did not create get analyzed in the disposable
  context only; never execute a third-party sample on the operator box.
