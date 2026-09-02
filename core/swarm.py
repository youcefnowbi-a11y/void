"""VOIDFORGE :: Swarm — coordinator + specialists + adversarial verifier.

One LLM burning its window on 77 calls forgets round 12 by round 40.
The swarm divides perception: four specialists (each with a role-restricted
arsenal, focused prompt, and their own context) do the legwork while the
coordinator distills, decides, and executes the synthesis moves. An
adversarial verifier then attacks OUR OWN work — contradictions, coverage
gaps, and especially UNMADE CONNECTIONS from the Living Graph.

Usage:
    swarm = SwarmCoordinator(cfg, target_domain)
    transcript = swarm.run(mission, on_event=...)
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from core.agent import Agent
from core.blackboard import Blackboard
from core import playbooks

SPECIALIST_ROLES = {
    "recon": {
        "tools": ["web_fingerprint", "subdomain_enum", "waf_detect", "dir_brute",
                  "wayback_urls", "nuclei_scan", "port_scan_sync", "spa_crawl",
                  "ip_intel", "fuzz_attack_surface", "batch_execute"],
        "brief": ("You are the RECON SPECIALIST. Map the target's surface: technologies, "
                  "hosts, open directories, WAF, CDN, ports, archived URLs. Close the pass "
                  "with fuzz_attack_surface to surface anomalies no template knows. "
                  "SKILL: skill_load recon_deep at mission start — your seven-layer manual. "
                  "Report every discovered endpoint, service and technology with confidence. "
                  "Finish with a distilled FACTS list."),
    },
    "web": {
        "tools": ["spa_crawl", "js_mine_site", "js_mine_url", "deobfuscate_js",
                  "vm_string_dump", "jwt_analyst", "jwt_forge_replay", "ssti_detect_rce",
                  "lfi_file_read", "proto_pollute", "redirect_cast", "replay_mutate",
                  "batch_execute"],
        "brief": ("You are the WEB/JS SPECIALIST. Walk the frontend: crawl SPAs with "
                  "request capture, mine every bundle (including source maps and chunks), "
                  "decode JWTs found — then STRIKE: forge them with jwt_forge_replay and "
                  "replay to prove acceptance; where input is reflected, ssti_detect_rce "
                  "climbs the RCE ladder; lfi_file_read confirms traversal with real file "
                  "contents; on JSON-merging endpoints proto_pollute tests "
                  "prototype pollution; redirect_cast probes auth callbacks for open "
                  "redirects. SKILL: skill_load web_access_master for the full decision "
                  "matrix; auth flows -> skill_load auth_bypass_master. "
                  "Finish with a distilled FACTS list (endpoints, keys, verdicts)."),
    },
    "api": {
        "tools": ["data_extract", "api_sweep", "endpoint_oracle", "graphql_introspect",
                  "sqli_probe_param", "sqli_union_dump", "sqli_blind_extract",
                  "cmd_exec_probe", "shell_exec", "upload_webshell", "shell_session",
                  "c2_pulse", "jwt_forge_replay", "idor_enum", "idor_b64_walk",
                  "race_smash", "smuggle_probe", "proto_pollute", "xxe_probe",
                  "param_brute", "ssrf_probe", "supabase_exfil",
                  "supabase_full_assault", "auth_signup_probe", "auth_metadata_poison",
                  "jwt_analyst", "replay_mutate", "batch_execute",
                  "h2_race_attack", "crypto_hash"],
        "brief": ("You are the API/STRIKE SPECIALIST. Probe the server surface, then "
                  "EXPLOIT what you confirm: sqli_probe_param finding -> sqli_union_dump "
                  "(auto engine+table+rows) -> sqli_blind_extract if UNION renders nothing; "
                  "injectable params -> cmd_exec_probe -> shell_exec; sequential or b64 "
                  "object ids -> idor_enum / idor_b64_walk; upload endpoints -> "
                  "upload_webshell -> shell_session -> c2_pulse for beacon liveness; "
                  "one-shot-only actions (votes, coupons, withdrawals, resets) -> "
                  "race_smash (HTTP/1.1) or h2_race_attack (HTTP/2 single-packet, STRICTLY "
                  "better timing when the target speaks h2); proxy-stack targets -> "
                  "smuggle_probe; XML-accepting endpoints -> xxe_probe; JSON merges -> "
                  "proto_pollute. SKILL: skill_load web_access_master (decision matrix), "
                  "auth_bypass_master (identity attacks), ssrf_master (metadata chains), "
                  "payload_grammar when anything is filtered. "
                  "Detection is scouting; a confirmed vulnerability you did not exploit "
                  "is an unfinished job. Respect rate limits. Finish with a distilled "
                  "FACTS list (verdicts, data extracted, working primitives)."),
    },
    "osint": {
        "tools": ["secret_scan", "tg_history_harvest", "tg_messages_dump", "tg_members_scrape",
                  "tg_market_scan", "tg_probe", "wayback_urls", "har_tokens", "cisa_kev",
                  "nvd_search", "nday_exploit", "batch_execute", "file_grep"],
        "brief": ("You are the OSINT SPECIALIST. Harvest public intelligence: Telegram "
                  "channels tied to the target, leaked secrets in public artifacts, known "
                  "CVEs for the discovered stack — then hand the CVEs to nday_exploit "
                  "(cve_id + verify_url) to stage and run public PoCs against the target. "
                  "SKILL: skill_load zeroday_hunter when findings look novel — a CVE "
                  "with no public PoC is YOUR zero-day to build. "
                  "Finish with a distilled FACTS list."),
    },
}

VERIFIER_PROMPT = """You are the ADVERSARIAL VERIFIER. Another team just ran an
engagement. Your job is to attack THEIR WORK, not the target:

1. CONTRADICTIONS — claims that conflict with each other or with the intel graph.
2. COVERAGE GAPS — surface the intel graph says exists but no transcript shows tested.
3. UNMADE CONNECTIONS — assets discovered but never paired (the graph's → TRY list
   is a starting point; find more: keys without endpoints, identities without gates).
4. OVERCLAIMS — conclusions stated without evidence in the transcripts.

Output a numbered list of concrete findings, each with the evidence and the exact
next action that would resolve it. Be ruthless but factual."""


def _target_from_mission(mission):
    m = re.search(r"https?://([a-zA-Z0-9.\-]+)", mission or "")
    if m:
        return m.group(1)
    m = re.search(r"\b([a-z0-9\-]+\.(?:com|tech|app|io|net|org|dev|co))\b", mission or "", re.I)
    raw = m.group(1).lower() if m else "unknown"
    # slugify: "http://.." must never become ".." (path traversal in missions/)
    from core.mission_workspace import _slug
    return _slug(raw) or "unknown"


class SwarmCoordinator:
    """Runs specialists in parallel on the shared Living Graph, then the
    verifier, then a final coordinator synthesis — one mission, one brain
    divided into senses."""

    def __init__(self, cfg, target=None, specialist_rounds=10):
        self.cfg = cfg
        self.specialist_rounds = specialist_rounds
        self.target = target or _target_from_mission("")
        self.board = Blackboard(self.target)
        self.transcripts = {}

    def run(self, mission, on_event=None, mission_id=None):
        self.target = self.target if self.target != "unknown" else _target_from_mission(mission)
        self.board = Blackboard(self.target)

        def emit(t, text):
            if on_event:
                on_event({"type": "system", "text": text})

        # ── Phase 1: specialists in parallel, sharing the Living Graph ──
        emit("swarm", f"🕸 SWARM déployé — 4 spécialistes sur {self.target}")
        plan = playbooks.prompt_block(mission)
        if plan:
            emit("swarm", "📚 Playbooks pertinents injectés")

        def run_specialist(role, spec):
            agent = Agent(self.cfg, tools_filter=spec["tools"],
                          extra_system=spec["brief"] + (f"\n\n{plan}" if plan else ""),
                          blackboard=self.board)
            # D-T2 : les spécialistes NE resetent pas le coffre — le reset
            # par-campagne vit dans le lanceur (server.py) ; 4 resets
            # concurrents effaceraient les jetons déjà émis par les autres
            # (args -> [HOST-7] littéraux -> unmask no-op -> frappe hors cible).
            agent._skip_vault_reset = True
            # specialists get a lighter loop
            agent.max_rounds = self.specialist_rounds
            sub_mission = (f"Main mission: {mission}\n\n"
                           f"Execute ONLY your role's portion on {self.target}. "
                           "Use your tools efficiently; batch independent calls.")
            return role, agent.run(sub_mission)

        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(run_specialist, role, spec)
                    for role, spec in SPECIALIST_ROLES.items()]
            for fut in futs:
                try:
                    role, tr = fut.result()
                    self.transcripts[role] = tr
                    emit("swarm", f"✓ Spécialiste {role} terminé — {len([t for t in tr if t[0]=='tool'])} outils")
                except Exception as ex:
                    emit("swarm", f"⚠ Spécialiste en échec: {type(ex).__name__}: {str(ex)[:100]}")

        # ── Phase 2: adversarial verifier over our own work ──
        emit("swarm", "🔍 Vérificateur adversarial engagé")
        distill = []
        for role, tr in self.transcripts.items():
            tool_bits = [t for k, t in tr if k == "tool"][:12]
            distill.append(f"### {role.upper()} used: " + " | ".join(
                b.split(":", 1)[0] for b in tool_bits))
        verifier = Agent(self.cfg, tools_filter=["__no_tools__"],
                         extra_system=VERIFIER_PROMPT, blackboard=self.board)
        verifier.max_rounds = 1
        verify_mission = (
            f"Target: {self.target}\nIntel graph:\n{self.board.to_prompt(40)}\n\n"
            "Specialists ran: " + ", ".join(self.transcripts.keys()) + "\n" +
            "\n".join(distill) +
            "\n\nProduce your verifier findings now (numbered, evidence-based).")
        try:
            vt = verifier.run(verify_mission)
            self.transcripts["verifier"] = vt
            emit("swarm", "✓ Vérification terminée")
        except Exception as ex:
            emit("swarm", f"⚠ Verifier failed: {str(ex)[:100]}")
            vt = []

        # ── Phase 3: coordinator synthesis with verifier findings ──
        emit("swarm", "🧠 Coordinateur — synthèse finale")
        coordinator = Agent(self.cfg, blackboard=self.board)
        synth = (
            f"Main mission: {mission}\n\n"
            f"Four specialists already executed {sum(1 for tr in self.transcripts.values() for k, _ in tr if k == 'tool')} "
            f"tool calls. The intel graph:\n{self.board.to_prompt(50)}\n\n"
            "Verifier findings:\n" + "\n".join(t for k, t in (vt or []))[:4000] +
            "\n\nNow execute ONLY the highest-value remaining actions the verifier and graph "
            "surface (connections, locked-but-promising endpoints, data extraction). Then "
            "write the RAPPORT DE MISSION FINAL covering the WHOLE swarm engagement.")
        final = coordinator.run(synth, on_event=on_event, mission_id=mission_id)
        self.board.save()
        playbooks.learn(mission, self.transcripts, self.board)

        transcript = [("system", f"[SWARM] specialists: {', '.join(self.transcripts.keys())}")]
        for role, tr in self.transcripts.items():
            transcript.extend((f"{role}:{k}", t) for k, t in tr[:60])
        transcript.extend(final)
        return transcript


# ═══════════════════════════════════════════════════════════════════
#  PLANNED SWARM — plan-driven subagents (CHAT → PLAN → STRIKE, phase 3)
#  The operator-approved plan's JSON block spawns the strike team: one
#  subagent per chain, scoped target, scoped tools, its own round budget,
#  all sharing the Living Graph. Coordinator + verifier unchanged.
# ═══════════════════════════════════════════════════════════════════

def parse_plan_json(plan_doc):
    """Extract the machine block from an approved plan — the ```json fence
    carrying {"chains": [...], "mode": "swarm", "max_subagents": N}."""
    m = re.search(r"```json\s*(\{.*?\})\s*```", plan_doc or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        return d if isinstance(d, dict) and isinstance(d.get("chains"), list) else None
    except Exception:
        return None


class PlannedSwarm(SwarmCoordinator):
    """Spawns N subagents from the approved plan's chains instead of the 4
    hardcoded roles. Each chain gets: its scoped target, the intersection of
    its 'tools' list with the registry (plus batch_execute + arsenal_selftest),
    the chain's own round budget, and the full chain text as its mission brief.
    Falls back to the classic 4-role swarm when the JSON block is absent."""

    def __init__(self, cfg, plan_doc, target=None, max_subagents=4):
        parsed = parse_plan_json(plan_doc) or {}
        self.plan_doc = plan_doc
        self.chains = parsed.get("chains") or []
        self.max_subagents = max(1, int(parsed.get("max_subagents") or max_subagents))
        self.recommended_mode = (parsed.get("mode") or "swarm").lower()
        super().__init__(cfg, target=target,
                         specialist_rounds=max(6, min(20, self._median_rounds())))

    def _median_rounds(self):
        rounds = [c.get("rounds") for c in self.chains if isinstance(c.get("rounds"), int)]
        if not rounds:
            return 10
        rounds.sort()
        return rounds[len(rounds) // 2]

    def run(self, mission, on_event=None, mission_id=None):
        # No machine-readable chains → classic swarm with the plan as context
        if not self.chains:
            if on_event:
                on_event({"type": "system",
                          "text": "🕸 plan sans bloc JSON exécutable — swarm classique plan-injecté"})
            return super().run(mission + "\n\nAPPROVED PLAN:\n" + self.plan_doc[:8000],
                               on_event=on_event, mission_id=mission_id)

        def emit(t, text):
            if on_event:
                on_event({"type": "system", "text": text})

        emit("planned", f"🗺 PLANNED SWARM — {min(len(self.chains), self.max_subagents)} "
                        f"subagent(s) depuis le plan approuvé sur {self.target}")
        board = self.board

        def run_chain(i, chain):
            name = str(chain.get("name") or f"chain-{i+1}")[:40]
            target = str(chain.get("target") or self.target)
            rounds = int(chain.get("rounds") or self.specialist_rounds)
            subagent = str(chain.get("subagent") or "api").lower()
            spec = SPECIALIST_ROLES.get(subagent) or SPECIALIST_ROLES["api"]
            # scoped arsenal: chain's tools ∩ registry, plus the meta pair
            from tools import all_tools as _at
            known = {t["name"] for t in _at()}
            requested = [t for t in (chain.get("tools") or []) if t in known]
            toolset = list(dict.fromkeys(requested + ["batch_execute", "arsenal_selftest"])) \
                or spec["tools"]
            chain_text = (
                f"CHAIN: {name} (priority: {chain.get('priority', 'MEDIUM')})\n"
                f"TARGET: {target}\n"
                f"STEPS: {chain.get('chain') or chain.get('steps') or 'au jugement, selon les outils'}\n"
                f"TOOLS ASSIGNED: {', '.join(toolset)}\n\n"
                f"{spec['brief']}")
            agent = Agent(self.cfg, tools_filter=toolset,
                          extra_system=chain_text + "\n\nAPPROVED PLAN CONTEXT:\n"
                          + self.plan_doc[:6000],
                          blackboard=board)
            # D-T2 : opt-out du reset par-run (voir run_specialist).
            agent._skip_vault_reset = True
            agent.max_rounds = max(4, min(rounds, 25))
            sub_mission = (f"Execute chain '{name}' on {target}. Stay in scope — "
                           f"other chains cover the rest. Batch independent calls.")
            return name, agent.run(sub_mission)

        with ThreadPoolExecutor(max_workers=min(self.max_subagents, len(self.chains))) as ex:
            futs = [ex.submit(run_chain, i, c) for i, c in enumerate(self.chains[:self.max_subagents])]
            for fut in futs:
                try:
                    name, tr = fut.result()
                    self.transcripts[name] = tr
                    emit("planned", f"✓ Chaîne {name} terminée — "
                                    f"{len([t for t in tr if t[0]=='tool'])} outils")
                except Exception as ex2:
                    emit("planned", f"⚠ Chaîne en échec: {type(ex2).__name__}: {str(ex2)[:100]}")

        # verifier + synthesis: same discipline as the classic swarm
        emit("planned", "🔍 Vérificateur adversarial engagé")
        distill = []
        for name, tr in self.transcripts.items():
            tool_bits = [t for k, t in tr if k == "tool"][:12]
            distill.append(f"### {name.upper()} used: " + " | ".join(
                b.split(":", 1)[0] for b in tool_bits))
        verifier = Agent(self.cfg, tools_filter=["__no_tools__"],
                         extra_system=VERIFIER_PROMPT, blackboard=board)
        verifier.max_rounds = 1
        verify_mission = (
            f"Target: {self.target}\nIntel graph:\n{board.to_prompt(40)}\n\n"
            "Chains ran: " + ", ".join(self.transcripts.keys()) + "\n" +
            "\n".join(distill) +
            "\n\nProduce your verifier findings now (numbered, evidence-based).")
        try:
            vt = verifier.run(verify_mission)
            self.transcripts["verifier"] = vt
            emit("planned", "✓ Vérification terminée")
        except Exception as ex2:
            emit("planned", f"⚠ Verifier failed: {str(ex2)[:100]}")
            vt = []

        emit("planned", "🧠 Coordinateur — synthèse finale plan-guidée")
        coordinator = Agent(self.cfg, blackboard=board)
        coordinator.run.__doc__  # noqa — keep parity with classic swarm
        synth = (
            f"Main mission: {mission}\n\nAPPROVED PLAN:\n{self.plan_doc[:6000]}\n\n"
            f"Chain subagents already executed "
            f"{sum(1 for tr in self.transcripts.values() for k, _ in tr if k == 'tool')} "
            f"tool calls. The intel graph:\n{board.to_prompt(50)}\n\n"
            "Verifier findings:\n" + "\n".join(t for k, t in (vt or []))[:4000] +
            "\n\nExecute ONLY the highest-value remaining actions from the plan's chains "
            "(connections, locked-but-promising endpoints, data extraction), then write "
            "the RAPPORT DE MISSION FINAL covering the WHOLE planned engagement.")
        final = coordinator.run(synth, on_event=on_event, mission_id=mission_id)
        board.save()
        playbooks.learn(mission, self.transcripts, board)

        transcript = [("system", f"[PLANNED SWARM] chains: {', '.join(self.transcripts.keys())}")]
        for name, tr in self.transcripts.items():
            transcript.extend((f"{name}:{k}", t) for k, t in tr[:60])
        transcript.extend(final)
        return transcript
