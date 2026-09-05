# 08 — TRANSPORT: the fetch pipeline (tools/_transport.py ~1150 lines)

Every network touch in the fleet funnels through ONE fetch. This is
its pipeline in execution order.

## fetch(url, ..., use_cache, _nocoalesce, _coalesce_key) — ORDER
1. QUARANTINE FAST-SKIP: host dark → return {"status": -3,
   quarantine detail} — NO wire contact, NO breaker mark (synthetic
   status must not self-perpetuate), skip_ledger "quarantined" recorded
   by the CALLER-side grafts (tools that fetch dark hosts).
2. CACHE-HIT (if cacheable): bounded store (40KB compaction, 300
   entries) — hit returns the cached response dict.
3. COALESCER JOIN: cacheable GETs only. In-flight identical request →
   join (Event.wait 180s timeout → solo flight). Joiner gets a COPY.
   Flyer: entry created → fly → finally pop + box publish + set().
   Corpse path: make() raises → out=None (init BEFORE try!) → wake
   joiners WITHOUT a box (they fly solo).
4. THE FLIGHT (urllib/requests plumbing, headers, TLS, timeouts).
5. REDIRECT FOLLOW: sub-call passes _nocoalesce=True AND
   _coalesce_key=<same key> — the sub returns early, BYPASSING the
   epilogue publish; without threading the key the cache silently
   misses on every redirect (the bug that was).
6. PROXY ROTATION (both sub-calls): same threading of the key.
7. EPILOGUE:
   - _tb_observe(host, out): status -1 (transport death) → breaker
     mark; -3 → NO re-mark; stale-quarantine reap → skip_ledger.
     Any real HTTP status (even 404/403) = SUCCESS for the breaker →
     full failure-state removal. The breaker counts DEATH, not anger.
   - _cache_store_locked(cache_key, out) when cacheable (40KB compact,
     300 LRU) — shared helper, also used by sub-calls.
   - _coalesce_key publish: box gets the result, set() wakes joiners.

## Breaker state (module scope)
- _TRANSPORT_FAILS {host: count}, _TB_LOCK, threshold 3, cooldown
  300s, host table 4096 (LRU evict on bound).
- _tb_mark_locked(host, cause): consecutive count; at 3 → quarantine
  entry {cause, ts}; table-bound eviction.
- _tb_success(host): FULL removal (any success forgives).
- host_quarantined(host, refresh): refresh=True reaps expired → False.

## Coalescer state
- _INFLIGHT {key: (Event, box)} cap 64 — cap overflow → SOLO flight
  (never queue-blocked).
- Keys: cacheable GET url+params only. STRIKES NEVER COALESCE — a
  POST/side-effect must hit the wire every single time (real harm,
  real proof, no deduped attacks).

## Invariants (see also 10)
- A joiner NEVER flies when a flyer is live for the same key.
- An exception in make() wakes ALL joiners (corpse rule).
- -3 responses are never cached, never breakered.
- Cache stores only cacheable GETs; POST responses NEVER cached.
