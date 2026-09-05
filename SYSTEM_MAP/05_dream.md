# 05 — Ω3 DREAM: dead time becomes training (core/dream.py + tools/dream_tool.py)

#79's dead ends become #80's shortcuts. Between missions the archive is
rehearsed: what NEVER ran, what WOULD have worked.

## 3.1 Provenance completion (caldera facts port)
- bind_mission(mission_id, target) at agent.run init (extract_target
  of the mission text — self.target does NOT exist on Agent, that was
  the bug); step_bump() once per tool result (graft in the tool loop).
- stamp_fact(fact): attaches {mission_id, target, step, ts} — grafted
  into blackboard.add_asset (core/blackboard.py) so every asset fact
  carries its birth certificate. ARCHIVED STAMPS ARE NEVER OVERWRITTEN
  (re-stamping would lie about birth) — stamp_fact keeps prov if
  prov.mission_id exists.
- "Which step told me this?" is answerable for all NEW facts. Old
  archives pre-Ω3 carry no prov (honest gap).

## 3.2 Replay lane
- untaken_branches(target, tools_available):
  - loads intel/<target>.json (ARCHIVED blackboard, read-only);
  - loads trajectory tail (LIMIT 2000 lines — 400 cut mid-campaign and
    minted phantom branches; the fix);
  - consumer map _CONSUMER_MAP (kind → tools): key→secret_scan/
    jwt_analyst/data_extract, endpoint→endpoint_oracle/data_extract/
    api_sweep/dir_brute/nuclei_scan, domain→subdomain_enum/wayback/
    nmap/web_fingerprint, js_bundle, bucket, service.
  - branch = asset × consumer-tool where the tool NEVER saw the asset
    value in its args digest. Branch carries: asset_key, kind, value,
    tool, confidence, PROPS (the missing-props bug — simulate_branch
    reads props for the would-work decision).
  - sorted by confidence desc, capped 64.
- simulate_branch(branch) — HONEST simulation, zero live traffic:
  - key + kind_of_key prop + confidence ≥ 0.8 → would-work (the
    corroborated key no consumer ever tested);
  - endpoint + confidence ≥ 0.75 → would-work;
  - js_bundle + sourcemap prop + conf ≥ 0.7 → would-work;
  - anything else → None (no archived evidence → NO play; the
    simulator never invents success).
- dream(target): branches → plays; every play STAMPED with target;
  fixpoint compounding (secret_scan play implies data_extract
  follow-on); report {target, plays≤32, ran_at}; save_plays appends
  (load + new, bounded 256).

## 3.3 Fixpoint simulation (amass: handlers re-trigger)
- fixpoint_simulate(target, max_passes=3): passes of
  untaken_branches → simulate → dedup (tool,value) pairs; a pass with
  zero NEW plays = saturation → break. The dream must END.

## 3.4 Dream → doctrine feed
- mint_doctrine_entry(play): status=="play" →
  {predicate, context, where=tool, expected, origin:"dream", evidence}.
- The minted entries go to Ω4's store (Phase 4 reads them; autopsy
  also persists).

## Plays persistence + round-0 feed
- intel/plays.json via _play_file() — a FUNCTION, not a module const
  (the const was frozen at import and ignored monkeypatched _INTEL).
- load_plays(limit, target=None): TARGET FILTER — plays minted for
  target A must NOT feed target B's round-0 brief (cross-target
  poisoning was the bug). Filter: play.target lower==target lower, or
  play has no target (legacy) rides anyway.
- agent.py round-0 graft: after skills block, DREAM PLAYS user-message
  (target = extract_target(mission)); ≤8 plays, try-early phrasing.

## Tool surface
- dream_rehearsal (tools/dream_tool.py, danger=safe): the operator or
  the agent can trigger a dream for an archived target between
  missions. MCTS_WHITELIST (arsenal integrity) — meta-tool, not a
  brain action. Doctrine line in the workspace section.
