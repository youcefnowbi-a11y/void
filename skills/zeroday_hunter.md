# skill: zeroday_hunter
title: Zero-Day Hunting Discipline (fuzz → triage → strike loop)
when: fuzz,zeroday,zero,day,unknown,anomaly,mutation,discover,creative

## OPERATING PRINCIPLE
Zero-days are not found by magic payloads — they are found by *statistical
listening*: send structured mutations, watch for the response to deviate
from its own baseline, then triage the deviation into a mapped strike.
VOIDFORGE's pipeline automates exactly this; your job is to aim it at the
richest surfaces and let the loop run.

## CHAIN (the loop)
1. Aim at RICH surfaces, not the homepage: parsers (import/export, file
   processing), auth boundaries (token/OTP/remember-me logic), search and
   filter endpoints, anything that accepts structured data (JSON/XML),
   and admin-side actions. A rich surface changes the server's state —
   state changes are where unknown bugs live.
2. fuzz_attack_surface(url, params, max_requests) — 5 oracles:
   status anomaly, z-score length deviation (learns the site's own noise
   floor), timing z-score, reflection leak, error-class fingerprint.
   Feed seeds from the URL query itself and from prior crash_triage_next
   output (the corpus learns between runs — reports/fuzz_seeds.json).
3. crash_triage_next — Wilson-lower-bound ranking (small sample flukes
   cannot outrank solid findings) + the mapped next_tool per family.
4. EXECUTE the mapped strike immediately: sqli_union_dump / ssti_detect_rce /
   lfi_file_read / cmd_exec_probe — triage says which.
5. Close the loop: new anomalies → new seeds → next fuzz round is smarter.
   Two or three loops beat one long blind run.

## READING THE ORACLES (what each anomaly family means)
- status_5xx → server code crashed: the payload reached a parser — error
  text will name the parser; that parser is your attack surface.
- length_zscore ±3σ → the server did something structural: template
  rendering, merge, query building — try that family's strike tool.
- timing_zscore → blind interaction (DB sleep, file stat, network call):
  request is reaching a backend you cannot see. Time-based blind SQLi first.
- reflection → input reaches output unsanitized: XSS/SSTI/class pollution
  depending on context — check the reflection position (attribute? body?
  header echo?).
- error_class fingerprints → library + version in the stack trace:
  nvd_search that library version, nday_exploit if the stack matches.

## DISCIPLINE
- Budget per surface: 300-500 requests per endpoint family, then move.
  The pacer keeps you under rate limits; the z-score floor (σ≥25) keeps
  noisy sites honest.
- Never fuzz the same param with the same family twice in one session —
  dedupe by signature is automatic; trust it and widen the surface instead.
- One confirmed anomaly = one strike = one verdict. Anomaly ≠ vulnerability
  until the mapped tool says exploitable=true.

## FAILURE MODES
- All anomalies are 5xx with the same signature: you found the global error
  handler, not a bug — diversify payload families, not volume.
- Timing oracle noisy on shared hosting: raise trigger threshold, trust
  structural oracles (length, error-class) more.
- Nothing deviates: your surface is thin — go find parsers and state
  changes (uploads, imports, webhooks); GET-only surfaces rarely bleed.
