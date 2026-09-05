# 02 — THE NERVOUS SYSTEM (Phase 0): rails, breaker, coalescer, ledger, datastore, OOB

## 0.1 OOB proof lane — tools/oob_channel.py + config/oob.yaml
- `oob_url(tag, host)` — deterministic token
  `sha1("vf-oob-v1:{tag}:{host}")[:12]`; offline mode returns
  `<tok>.oob.internal` (honest: never a fake URL).
- `register(tag, host, predicate, context)` — freezes the predicate
  PRE-SEND (nuclei fidelity: the predicate is evaluated against the
  LATER interaction, so it must be captured before the request flies).
- `process_interaction(token, protocol, details)` — callback lands →
  re-fire predicate; PASSING mints proof object
  `{proof:"oob_callback", protocol, ts, details, token, tag, host}`;
  FAILING does NOT consume the pending correlation (a WAF health-check
  http hit doesn't eat the slot; the real DNS exfil can still fire).
- Bounded: LRU 2048 pending, expiry 3600s, receipts keyed (tag, host).
- Grafts: tools/ssrf_test.py (oob dict + proof_object + verdict ladder),
  tools/advanced_web.py xxe_probe (blind XXE: pure-callback declaration
  `%remote;` — NO dangling %file;/&xxe; which strict parsers reject
  BEFORE fetching; inert body; `responded` counts only int status > 0).

## 0.2 Mission stop rails — core/stop_rails.py
- Window: deque maxlen 400 of per-payload statuses (ffuf semantics: a
  403 on payload #7 counts once, not per-request).
- Arming: ≥95% share of 403 (wall_403) or ≥20% of 429 (rate_429) over
  ≥50 observed statuses. Constants: read `_WALL_SHARE`, `_RATE_SHARE`,
  `_MIN_N` before writing test fixtures — fixture math broke twice.
- Delivery: ONCE per arming; re-arms only on WORSENING share or
  collapse below half-threshold (anti-nagging).
- pending() returns RAW float shares — rounding to 3 decimals BROKE
  re-arm math (0.983 < 0.98333 → rail re-armed instantly after
  delivery). NEVER round shares.
- Noise-tool exemption regex `_NOISE_TOOLS` — idor/auth/oracle/brute
  tools EXPECT 40x as data. MUST stay in sync with agent.py's own
  `_NOISE_TOOLS` (two copies exist by design; verify both on change).
- Reset per mission in agent init.

## 0.3 Per-host circuit breaker — tools/_transport.py
- `_TRANSPORT_FAILS` counts consecutive status -1 (TRANSPORT DEATH
  only). -2 never existed (phantom, removed). -3 is the SYNTHETIC
  quarantine-skip status: it does NOT re-mark the breaker (no
  self-perpetuation).
- 3 consecutive deaths → quarantine(host, cause), cooldown 300s,
  host table bounded 4096 (LRU evict).
- ANY success = FULL removal of the host's failure state.
- `host_quarantined(host, refresh=False)` — refresh=True reaps expired
  quarantine and returns False (ready again).
- fetch fast-path returns `{"status": -3, ...quarantine detail}` when
  the host is dark → skip_ledger category "quarantined".
- Tests hit real dark hosts (10.255.255.1) — they take ~seconds, by
  design (transport death proof).

## 0.4 In-flight coalescer — tools/_transport.py
- `_INFLIGHT` dict cache_key → (Event, box), cap 64.
- ONLY cacheable GETs coalesce. Strikes/POSTs NEVER (side effects must
  hit the wire — every live request is real harm/real proof).
- Flyer: creates entry, flies, finally pops + publishes result in box +
  set(). Exception path: out=None initialized BEFORE try; corpse-wake
  (set without box) when make() raises; joiner timeout 180s → solo.
- Inner re-entry (redirects, proxy rotation): `_nocoalesce=True` +
  `_coalesce_key` PASSED THROUGH — the sub-calls `return res` EARLY,
  bypassing the epilogue publish; the key must be threaded manually.
  THIS BROKE ONCE: redirect/proxy paths silently missed the cache.
- Joiner gets a COPY of the box (dict(box)) — never the shared ref.

## 0.5 Skip ledger — core/skip_ledger.py
- Closed taxonomy: unknown_tool, scope_tool, roe_blocked,
  scope_blocked, quarantined, rail_pivot, budget, prereq_missing,
  other (unknown reasons map to other, raw detail kept).
- Bounded 512, append-only, per-mission isolation via start_mission().
- summary() shape: `{total, by_reason:{cat:count}, example:{cat:"tool: detail"}, mission}` —
  doctrine.skip_taught() DEPENDS on this exact shape.
- Six refusal points grafted in tools/__init__.py + agent rail pivot +
  breaker -3 + Ω1 slot-defer (prereq_missing).

## 0.6 Datastore cascade — core/datastore.py + tools/mission_globals.py
- Two layers: mission > session. Values capped 4096 chars (a cookie
  fits; a dump doesn't — by design).
- `_CASCADE_KEYS` in tools/__init__.py — CLOSED curated map
  (token→auth_token, anon_key→supabase_anon_key, api_key→api_key,
  headers→default_headers, cookies→cookies, proxy→proxy_url).
- Fills PRESENT-but-EMPTY params only; explicit args ALWAYS win.
- Fill happens AFTER _coerce_args → filled strings re-coerced via
  `_coerce_one` (str→dict for headers etc. — the str-dict gap bug).
- mission_globals tool: action set/get/list/unset; masked listing for
  auth_token/api_key/cookies.

## A3 message discipline (CRITICAL — providers 400)
NEVER mid-conversation `system` role messages, NEVER `user` between
assistant(tool_calls) and tool(results). Everything the loop wants to
say rides TOOL-RESULT CONTENT: `_rail_note` (rails + twin), `pacing`
(round budget + Ω1 surprise map), appended post-run notes. The
wall-breaker intel injection waits for a `user` slot AFTER all tool
results of the round (_wall_pending pattern).
