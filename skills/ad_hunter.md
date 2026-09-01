# skill: ad_hunter
title: Active Directory Attack Primer (S1ckB0y1337 distillation)
when: active,directory,ad,domain,kerberos,ldap,kerberoast,ntlm,smb,dc

## OPERATING PRINCIPLE
AD is a graph of trust — attack the edges, not the core. Every domain user
you control is a new edge; every service account password you crack is a
shortcut. Recon is 80% of AD work; the exploits are the easy 20%.

## CHAIN (recon-first, through port_scan_sync + shell_exec on a joined host)
1. Locate DC: port_scan_sync(host) on 88 (kerberos), 389/636 (ldap), 445 (smb),
   135/49152+ (rpc), 53 (dns). The host with 88+389+445 is the DC — never
   bruteforce it, everything flows through it.
2. Enumerate without credentials: anonymous LDAP binds often walk object
   lists; `rpcclient -U "" -N <dc> srvinfo`; SMB null session file lists.
3. With any domain credential, enumerate users/shares/GPOs (rpcclient,
   smbclient -L, ldapsearch on named contexts). Users list → password
   reuse candidates for sprays (respect lockout: 1-2 attempts, long delays).
4. AS-REP Roast (no password needed): accounts with
   "Do not require Kerberos preauthentication" — request their hash, crack
   offline. `Get-DomainUser -PreauthNotRequired` concept via ldap filter.
5. Kerberoast (any domain user): every service account with an SPN hands
   you a crackable TGS. `GetUserSPNs` request → hashcat mode 13100.
   Service accounts are the #1 privesc path in real domains.
6. Password spray with lockout discipline: spring + password seasons, one
   password across all users, 30-60 min between sprays.
7. Delegation abuse: unconstrained (any DC auth leaks TGT to your host),
   constrained, RBCD — setspn/ldap attribute checks.
8. NTLM relay once you have a foothold: coerce (PetitPotam class) → relay
   to LDAPS/Certificate services → domain escalation.

## TOOL MAPPING (what VOIDFORGE executes natively)
- port_scan_sync — DC discovery and service reachability
- cmd_exec_probe/shell_exec (os_flavor=win) — run enumeration commands
  through a Windows foothold obtained elsewhere (web app on the domain)
- web_fingerprint + js_mine_site — internal web apps often leak LDAP
  usernames in error pages and comment metadata
- nvd_search/nday_exploit — DC CVEs (ZeroLogon, PrintNightmare, noPac):
  stack-match the windows server version first
- secret_scan on any dumped GPP files (cpassword is an instant win)

## LATERAL MOVEMENT MATRIX
- creds: psexec-style (admin), WMI (admin), WinRM 5985/5986 (admin/remote users)
- no creds: relay coercion → machine account → generic chain
- gpo/scrips shares: writable SYSVOL scripts = domain-wide persistence

## FAILURE MODES
- Kerberos port open but LDAP closed: fingerprint via user enumeration
  timing on 88 (AS-REQ responses differ: valid user vs unknown).
- Spray lockouts: STOP at first lockout event, switch vector, report it.
- Relay blocked (SMB signing): pivot to LDAPS relay or certificate abuse
  (ESC1-ESC8 template misconfigurations — certificate services is the
  modern goldmine).
