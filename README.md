# ⚒️ VOIDFORGE

**The Wave-3 autonomous offensive-security platform.** Not a chatbot with
tools — a full mission architecture: MCTS tactical planning, parallel attack
swarms with fresh context windows, adversarial verification of every claim,
and a war library that compounds across missions.

```
PLAN  ──►  recon-only planner seals an attack plan with machine-readable chains
SWARM ──►  N parallel specialists, each a fresh context, one shared Living Graph
VERIFY──►  adversarial verifier re-tests the fleet's own verdicts with live probes
```

## WHY IT'S DIFFERENT

- **MCTS opening book at round 0** — a model-predictive planner (UCT search
  over a 65-action world model with preconditions and yields) hands every
  mission its tactical chain before the LLM spends a single token. The lane
  the 2024-2026 research literature calls "unclaimed": claimed here.
- **Interpretation-differential doctrine** — the GRIMOIRE ships 141
  techniques across 12 domains, including a dedicated DIFF domain: 84
  techniques that test what two components *disagree* about, not what a
  request does. Scanners test requests; the new era tests disagreement.
- **Adversarial verification** — every confirmed verdict passes a challenger
  agent armed with a read-only probe lane; final reports pass a
  deterministic claim-vs-archive check. Hallucinated findings get annotated
  in the sealed deliverable, not shipped.
- **Memory that compounds** — 142 learned plays (proven call grammars),
  self-authored doctrine minted from mission autopsies, a Living Graph of
  300+ assets shared across parallel lanes, dream plays minted from dead
  branches, and an episodic digest that survives context compaction.
- **Resilient to a fault** — provider fleet with live failover, refusal
  wipe-restart, transport circuit breakers with per-host pacing, tool
  deadline watchdogs, crash-safe incremental event logs. Missions survive
  DNS outages, provider storms, and their own bugs.

## ARSENAL (100+ modules)

recon: web_fingerprint · endpoint_oracle · js_mine_url/site · spa_crawl · subdomain_enum
forensics: har_dissect · har_tokens
auth: auth_signup_probe · auth_metadata_poison · otp_brute
injection: sqli_probe_param · sqli_union_dump · sqli_blind_extract · sqli_tamper
rce: cmd_exec_probe · shell_exec · ssti_detect_rce · upload_webshell · shell_session
advanced: race_smash · smuggle_probe · proto_pollute · xxe_probe · redirect_cast
c2: c2_pulse (beacon discipline: jitter · UA rotation · backoff)
files: lfi_file_read
identity: jwt_analyst · jwt_forge_replay (alg:none · RS→HS · kid · jku/x5u) · idor_enum · idor_b64_walk
zeroday: fuzz_attack_surface (learned seed corpus) · crash_triage_next · nday_exploit
telegram: tg_probe · tg_history_harvest · tg_market_scan
cloud: supabase_full_assault · obs/s3 bucket sweeps
intel: nvd_search · cisa_kev · grimoire_query (141 techniques)
reverse: deobfuscate_js · vm_string_dump
forge: forge_tool (mid-mission weapon forging — the arsenal grows while you hunt)
workspace: report_write · evidence_pack · workspace_status · operator_message

## QUICKSTART

```yaml
# config/provider.yaml
provider:
  base_url: https://api.deepseek.com/v1   # any OpenAI-compatible
  api_key: YOUR_KEY
  model: deepseek-chat
```

**Solo mission** (unlimited rounds, full doctrine):
```powershell
python lab/ops/_calib_mission.py <run_id> "brief"
```

**Premium campaign** (PLAN → SWARM → VERIFY):
```powershell
python lab/ops/_calib_campaign.py <RUN_ID> "brief"
```

**One-liner recon:**
```powershell
python main.py "Full recon of example.com: fingerprint, JS secrets, API map"
```

Events stream live to `lab/camp_<ID>/events.jsonl` — tail them and watch
the swarm hunt in real time.

## ARCHITECTURE

```
core/            agent loop · MCTS attack graph · swarm · doctrine · learned
                 plays · capability vault · world model · framing/refusals ·
                 blackboard · dream · stop rails · mission workspaces
tools/           100+ registered weapons · transport (pacing/breaker/ROE)
                 · batch · forge · grimoire
data/            grimoire.feed.json (141 techniques) · doctrine · plays
missions/        per-target evidence: ledger · extractions · findings · reports
SYSTEM_MAP/      the platform's own brain: graft log (15 sessions), research
                 dossiers, threat-intel catalog, era architecture
lab/ops/         mission runners · campaign runner · graft tools · smoke tests
lab/archive/     historical probes and calibration runs
web/             operator console (FastAPI + PWA)
```

## DOCTRINE SOURCES

knowledge/ · intel/ · SYSTEM_MAP/13_ai_hacking_research_2024-2026.md ·
SYSTEM_MAP/14_threat_intel_catalog_2024-2026.md — the platform reads its own
research and writes its own rules. Doctrine entries cite wire evidence and
get demoted when the wire disagrees.

## PROVEN IN THE FIELD

Ten-plus live campaigns. The goal target fell via a lane the wall itself
opened: the vendor's own sales channel leaked a fully-verified product
account, found by a chain that pivoted planes three times in one mission.
Every HELD gate produced a NEXT-LEAK-AXIS. The missions don't stop at walls;
they go around them, over them, or through the wall's other side.
