# 01 — ARCHITECTURE: the organism, its data flow, its boundaries

## Process boundary
- `web/backend/server.py` (FastAPI+WebSocket, LO's other session OWNS this
  file — never touch): UI bridge, launches missions in background tasks.
- Console entry (`main.py`/launcher paths): same Agent class, different
  surface.
- ONE python process per mission run in practice (single-mission console
  default; swarm specialists share the process via threads — see caveats
  in 07_agent_loop).

## The core cycle (money path)
```
operator brief (mission text)
  → Agent.run(mission, ...)                    core/agent.py
     ├─ system prompt (DOCTRINE const + persona flag)
     ├─ user injections (round 0): skills block, DREAM PLAYS,
     │  DOCTRINE block (Ω4), learned plays recall
     └─ ROUND LOOP (see 07_agent_loop):
          LLM stream → tool_calls → for each tc:
            tools.execute(name, args)         tools/__init__.py
              ├─ registry lookup (UNKNOWN_TOOL → skip_ledger)
              ├─ unmask tokens (_tokenize)
              ├─ arsenal gate (SCOPE_TOOL → skip_ledger)
              ├─ ROE gate (roe_blocked → skip_ledger)
              ├─ scope guard G13 (SCOPE_BLOCKED → skip_ledger)
              ├─ _coerce_args (LLM type coercion)
              ├─ datastore cascade fill (present-but-empty only)
              ├─ Ω1 predict extraction (slot-DEFER path)
              ├─ self-heal loop ≤3 (healer)
              │    └─ tool run → output
              ├─ Ω1 measure (verdict + note appended)
              ├─ rails observe → RAIL note
              ├─ Ω2 twin blind-cap (BEFORE all archive consumers)
              ├─ Ω3 step bump (provenance)
              ├─ Ω4 doctrine self-verify (armed entries)
              ├─ blackboard.from_tool_result (graph)
              ├─ workspace save (extraction/finding)
              ├─ trajectory record
              └─ msgs.append(tool result + pacing + notes)
          → next round until final report or budget
  → teardown: board flush, Ω4 autopsy (skips → doctrine), save doctrine
```

## Where intelligence lives (state stores)
| Store | File | Lifetime | Reset per |
|---|---|---|---|
| Blackboard (graph) | core/blackboard.py | on disk intel/<target>.json | never (per-target archive) |
| Trajectory | core/trajectory.jsonl | append-only JSONL | never (30MB rotation) |
| World model | core/world_model.py | in-memory _STORE, TTL'd | every mission (agent init) |
| Twin cache | core/twin.py | in-memory, hourly budget | cache per mission; ranks cross-mission |
| Dream plays | intel/plays.json | on disk | never (bounded ring via load+save) |
| Doctrine | intel/doctrine.json | on disk (live + graveyard) | never (self-verifying) |
| Skip ledger | core/skip_ledger.py | in-memory 512 | every mission |
| Datastore | core/datastore.py | mission + session layers | mission layer per mission |
| Stop rails | core/stop_rails.py | in-memory window 400 | every mission |
| Transport state | tools/_transport.py | in-memory (cache, breaker, inflight) | process |

## The Ω feedback loop (why this is an organism, not a tool)
```
mission runs → predictions measured (Ω1 surprise map)
             → confirmed verdicts challenged (Ω2 twin)
             → skips categorized (Phase 0.5 ledger)
mission ends → autopsy: skips → doctrine rules (Ω4.3)
             → dream: untaken branches → plays (Ω3.2)
next mission → round 0 loads doctrine + plays
             → follows rules → outcomes reported (Ω4.4)
             → rules that stopped working RETIRE (Bayesian)
```
The system writes its own behavior law from its own failures. The
Ultimate Test (plan exit): two consecutive missions where the majority
of effective behavior was self-authored in prior missions.

## What the organism does NOT have (honesty)
- No LLM inside world_model/dream/doctrine arithmetic — determinism by
  law #3. The ONLY LLM twin call (core/twin.py) is budgeted, cached,
  optional, and never gates a verdict alone.
- No multi-process state sharing (single-process, thread-swarm only —
  documented caveat: a concurrent _doc.load() swaps live entries and
  armed refs go stale; verdicts drop as honest no-ops).
- No cross-target doctrine transfer YET (post-ultimate Ω+ territory).
