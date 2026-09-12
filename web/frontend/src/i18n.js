/* REDACTED :: frontend i18n — EN default, FR knob.
   The product speaks English on every rendered surface; operators who
   set `language: fr` in provider.yaml get the French console. The
   language is fetched once at boot from GET /provider (single source
   of truth: the same knob the backend runtime reads). */

let LANG = 'en'

export function setLang(l) {
  LANG = (l === 'fr') ? 'fr' : 'en'
  // m5 FIX: expose for non-React helpers (console clock locale)
  try { if (typeof window !== 'undefined') window.__vf_lang = LANG } catch {}
}
export function getLang() { return LANG }

const S = {
  // ── App shell ──────────────────────────────────────────────
  app_idle_hint: { en: 'the core watches — an order will wake it', fr: 'le cœur veille — un ordre l’éveillera' },
  abort_campaign: { en: 'abort the campaign', fr: 'rompre la campagne' },
  new_session: { en: 'new session', fr: 'nouvelle session' },
  status_campaign: { en: 'campaign', fr: 'campagne' },
  status_complete: { en: 'complete', fr: 'terminée' },
  status_error: { en: 'failed', fr: 'rompue' },
  status_idle: { en: 'standby', fr: 'veille' },
  activity_live: { en: 'activity in progress', fr: 'activité en cours' },
  plan_edit_hint: { en: 'edit freely — your version goes to the strike', fr: 'corrige librement — ta version part à la frappe' },
  mode_swarm: { en: 'swarm: plan subagents', fr: 'swarm : subagents du plan' },
  mode_solo: { en: 'single plan-guided agent', fr: 'agent unique plan-guidé' },
  tab_console: { en: 'Console', fr: 'Console' },
  tab_surface: { en: 'Surface', fr: 'Surface' },
  tab_chain: { en: 'Chain', fr: 'Chaîne' },
  tab_dashboard: { en: 'Dashboard', fr: 'Tableau' },
  tab_findings: { en: 'Findings', fr: 'Failles' },
  console_clear: { en: 'clear', fr: 'vider' },
  console_open: { en: 'open the campaign console', fr: 'ouvrir la console de campagne' },
  console_close: { en: 'close the console', fr: 'fermer la console' },
  open_console: { en: 'console', fr: 'console' },

  // ── Workbench / socket feed ────────────────────────────────
  feed_engaged: { en: '▶ Order engaged — mode {mode}', fr: '▶ Ordre engagé — mode {mode}' },
  feed_fail_short: { en: 'failed', fr: 'échec' },
  feed_negative: { en: '○ {tool} — negative ({d}s)', fr: '○ {tool} — négatif ({d}s)' },
  feed_done: { en: '✓ {tool} — done ({d}s)', fr: '✓ {tool} — terminé ({d}s)' },
  feed_tool_error: { en: '✗ {tool} — {err}', fr: '✗ {tool} — {err}' },
  feed_plan_ready: { en: "■ ATTACK PLAN READY — operator approval required", fr: '■ PLAN D’ATTAQUE PRÊT — approbation de l’opérateur requise' },
  feed_round: { en: 'ROUND {r}/{t}', fr: 'ROUND {r}/{t}' },
  feed_thinking: { en: 'thinking', fr: 'réflexion' },
  feed_complete: { en: '✦ Mission complete — {r} rounds · {t} tool calls', fr: '✦ Mission terminée — {r} rounds · {t} frappes' },
  feed_rejected: { en: 'Rejected: {out}', fr: 'Refusé : {out}' },
  feed_send_fail: { en: 'Transmission failed: {err}', fr: 'Échec de transmission : {err}' },
  feed_chat_busy: { en: 'chat busy or empty', fr: 'chat occupé ou vide' },
  feed_channel_fail: { en: '⚠ channel failure: {d}', fr: '⚠ échec du canal : {d}' },

  // ── WarRoom ────────────────────────────────────────────────
  role_commander: { en: 'commander', fr: 'commandant' },
  role_strategist: { en: 'strategist', fr: 'stratège' },
  copied: { en: 'copied ✓', fr: 'copié ✓' },
  copy: { en: 'copy', fr: 'copier' },
  upload_too_big: { en: '⚠ {name} ({kb} KB) exceeds the 2 MB ceiling.', fr: '⚠️ {name} ({kb} Ko) dépasse le plafond de 2 Mo.' },
  upload_text_only: { en: '⚠ {name}: only text formats are accepted (.txt, .md, .json, .log, .csv, .yaml…)', fr: '⚠️ {name} : seuls les formats texte (.txt, .md, .json, .log, .csv, .yaml, etc.) sont acceptés' },
  upload_attached: { en: '✓ {name} ({kb} KB{trunc}) attached', fr: '✓ {name} ({kb} Ko{trunc}) attaché' },
  recon_desc: { en: 'Passive mapping of subdomains, exposed ports and technologies.', fr: 'Cartographie passive des sous-domaines, ports et technologies exposées.' },
  auth_desc: { en: 'Analysis of Clerk/JWT flows, session cookies and access control (IDOR).', fr: 'Analyse des flux Clerk/JWT, cookies de session et contrôle d’accès (IDOR).' },
  smash_desc: { en: 'Race condition tests on sensitive endpoints (coupons, double debits).', fr: 'Tests de race condition sur les endpoints sensibles (coupons, double débit).' },

  // ── FindingsVault ──────────────────────────────────────────
  vault_empty_title: { en: 'No Active Vulnerability', fr: 'Aucune Vulnérabilité Active' },
  vault_empty_body: { en: 'As soon as a breach, API leak or access-control flaw is proven, it appears here with its evidence.', fr: 'Dès qu’une brèche, une fuite d’API ou une faille de contrôle d’accès est prouvée par la forge, elle apparaîtra ici avec sa preuve.' },
  vault_empty_sub: { en: 'clean perimeter or audit pending', fr: 'périmètre sain ou audit en attente' },
  vault_title: { en: 'Confirmed Findings & Proof', fr: 'Failles Confirmées & Preuves' },
  vault_filter: { en: 'Filter by finding, tool or parameter…', fr: 'Filtrer par faille, outil ou paramètre...' },
  vault_copy_poc: { en: 'copy poc', fr: 'copier poc' },
  vault_poc_copied: { en: 'poc copied ✓', fr: 'poc copié ✓' },
  vault_unnamed: { en: 'Identified vulnerability', fr: 'Vulnérabilité identifiée' },

  // ── AttackGraph ────────────────────────────────────────────
  chain_empty_title: { en: 'Attack Chain Pending', fr: 'Chaîne d’Attaque en Attente' },
  chain_empty_body: { en: 'As the agent begins reconnaissance, the attack chain assembles step by step from the target to the demonstrated impact.', fr: 'Dès que l’agente entame sa reconnaissance, la chaîne d’attaque s’assemblera pas à pas depuis la cible jusqu’à l’impact prouvé.' },
  chain_empty_sub: { en: '0 vectors mapped · active listening', fr: '0 vecteur répertorié · écoute active' },
  chain_title: { en: 'Attack Chain', fr: 'Chaîne d’Attaque' },
  chain_tree_view: { en: 'Tree & Connected Links View', fr: 'Vue Arbre & Liaisons Connectées' },
  chain_zoom_out: { en: 'Zoom out', fr: 'Zoom arrière' },
  chain_zoom_reset: { en: 'Reset zoom', fr: 'Réinitialiser zoom' },
  chain_waiting: { en: 'Awaiting discovery…', fr: 'En attente de découverte...' },
  phase_recon: { en: '1. Recon', fr: '1. Reconnaissance' },
  phase_surface: { en: '2. Exposed Surface', fr: '2. Surface Exposée' },
  phase_identity: { en: '3. Identity & Tokens', fr: '3. Identités & Tokens' },
  phase_exploit: { en: '4. Exploitation', fr: '4. Exploitation' },
  node_domains: { en: 'Domains & Hosts', fr: 'Domaines & Hôtes' },
  node_identity: { en: 'Identities & Tokens', fr: 'Identités & Tokens' },
  vuln_confirmed: { en: 'Confirmed vulnerability', fr: 'Vulnérabilité confirmée' },
  keys_auth: { en: 'Keys & Auth', fr: 'Clés & Auth' },

  // ── SurfaceMap ─────────────────────────────────────────────
  surface_title: { en: 'Discovered Attack Surface', fr: 'Surface d’Attaque Découverte' },
  surface_empty: { en: 'Domains, API routes, ports and technologies discovered by the agent will order themselves here in real time.', fr: 'Les domaines, routes d’API, ports et technologies découverts par l’agente s’ordonneront ici en temps réel.' },
  surface_empty_sub: { en: '0 surface mapped · active listening', fr: '0 surface cartographiée · écoute active' },
  surface_vuln: { en: 'Vulnerability', fr: 'Vulnérabilité' },

  // ── SessionSidebar ─────────────────────────────────────────
  sidebar_title: { en: 'Operations History', fr: 'Historique des opérations' },
  sidebar_close: { en: 'Close (Esc)', fr: 'Fermer (Échap)' },
  sidebar_search: { en: 'Search a past mission…', fr: 'Rechercher une mission passée...' },
  sidebar_archived: { en: 'Archived mission', fr: 'Mission archivée' },
  final_report: { en: 'final report', fr: 'rapport final' },
  filter_all: { en: 'all', fr: 'tout' },
  filter_tools: { en: 'tools', fr: 'outils' },
  filter_findings: { en: 'findings', fr: 'alertes' },
  filter_ai: { en: 'ai', fr: 'ia' },
  filter_errors: { en: 'errors', fr: 'erreurs' },
  strike_blocked: { en: 'strike blocked — a campaign is already running', fr: 'frappe bloquée — une campagne est déjà en cours' },
  sidebar_settings: { en: 'Operational Settings', fr: 'Paramètres Opérationnels' },

  // ── LiveConsole ────────────────────────────────────────────
  console_expand: { en: '▲ expand', fr: '▲ déplier' },
  console_copy_log: { en: 'Copy the filtered log', fr: 'Copier le journal filtré' },
  console_restore: { en: 'Restore size', fr: 'Restaurer la taille' },
  console_fullscreen: { en: 'Full screen', fr: 'Plein écran' },
  console_open_idle: { en: '» the log is open — a strike order will bring it to life.', fr: '» le journal est ouvert — un ordre de frappe l’animera.' },
  console_no_entry: { en: 'no entry to display', fr: 'aucune entrée pour l’instant' },

  // ── DirectToolRunner ───────────────────────────────────────
  strike_title: { en: 'direct strike', fr: 'frappe directe' },
  strike_params: { en: 'strike parameters', fr: 'paramètres de frappe' },
  strike_json_error: { en: 'JSON error: cannot execute', fr: 'Erreur JSON : impossible d’exécuter' },
  strike_exec_error: { en: 'Tool execution error', fr: 'Erreur d’exécution de l’outil' },
  strike_no_params: { en: 'This tool requires no parameters.', fr: 'Cet outil ne requiert aucun paramètre.' },
  strike_csv_hint: { en: 'comma-separated', fr: 'séparer par virgules' },
  strike_ready: { en: 'Ready for targeted strike', fr: 'Prêt pour frappe ciblée' },
  strike_processing: { en: 'Processing…', fr: 'Traitement en cours...' },
  strike_running: { en: 'executing…', fr: 'exécution...' },
  strike_result_ok: { en: 'result obtained', fr: 'résultat obtenu' },
  strike_result_fail: { en: 'failure / alert', fr: 'échec / alerte' },

  // ── PersonaPanel ───────────────────────────────────────────
  persona_saved: { en: '✓ personality engraved', fr: '✓ personnalité gravée' },
  persona_restored: { en: '✓ default mask restored', fr: '✓ masque par défaut restauré' },
  persona_speed: { en: 'fast chains, stops at diminishing returns', fr: 'chaînes rapides, stop aux rendements décroissants' },
  persona_thorough: { en: 'exhausts every vector, cross-checks every finding', fr: 'épuise chaque vecteur, recoupe chaque finding' },
  persona_archetype: { en: 'archetype', fr: 'archétype' },
  persona_doctrine_ph: { en: 'Free doctrine — priorities, habits, rituals.\nex: Prioritize Supabase exposures. Always validate before striking.', fr: 'Doctrine libre — priorités, habitudes, rituels.\nex : Prioritize Supabase exposures. Always validate before striking.' },
  persona_chars: { en: '/ 2,000 characters', fr: '/ 2 000 caractères' },
  persona_over: { en: ' (over limit: truncated to 2,000 by the backend)', fr: ' (dépassement : sera tronqué à 2 000 par le backend)' },
  persona_preview: { en: 'preview of the injected prompt', fr: 'aperçu du prompt injecté' },
  persona_active: { en: 'active mask — applied to the next mission', fr: 'masque actif — appliqué à la prochaine mission' },
  persona_loading: { en: 'loading the mask…', fr: 'chargement du masque...' },
  persona_default: { en: 'default', fr: 'défaut' },

  // ── FreshSessionPanel ──────────────────────────────────────
  fresh_chat: { en: 'war room conversation', fr: 'conversation war room' },
  fresh_chat_hint: { en: 'the secure line starts fresh', fr: 'la ligne sécurisée repart de zéro' },
  fresh_pending: { en: 'pending plan', fr: 'plan en attente' },
  fresh_pending_hint: { en: 'verdict cancelled, panel emptied', fr: 'verdict annulé, panel vidé' },
  fresh_bandit: { en: 'learned reliability (bandit)', fr: 'fiabilité apprise (bandit)' },
  fresh_bandit_hint: { en: 'it will relearn from zero', fr: 'elle réapprendra de zéro' },
  fresh_healer: { en: 'learned fixes (healer)', fr: 'fixes appris (healer)' },
  fresh_healer_hint: { en: 'learned repairs are forgotten', fr: 'les réparations apprises sont oubliées' },
  fresh_confirm: { en: 'FRESH SESSION — permanent purge:\n{label}\n\nContinue?', fr: 'SESSION NEUVE — purge définitive :\n{label}\n\nContinuer ?' },
  fresh_purged: { en: '✓ purged: {list}', fr: '✓ purgé : {list}' },
  fresh_nothing: { en: 'nothing selected', fr: 'rien sélectionné' },
  fresh_never_touched: { en: 'never touched: forged tools, mission history (missions.db), reports', fr: 'jamais touché : outils forgés, historique des missions (missions.db), rapports' },

  // ── PayloadMessage ─────────────────────────────────────────
  payload_title: { en: 'Session Data / Payload', fr: 'Données de Session / Payload' },
  payload_decode: { en: 'Decode the URL or JSON payload', fr: 'Décoder le payload URL ou JSON' },
  payload_raw: { en: 'raw format', fr: 'format brut' },
  payload_decode_url: { en: 'decode url', fr: 'décoder url' },
  payload_collapse: { en: 'collapse', fr: 'replier' },
  payload_expand: { en: 'expand', fr: 'déplier' },
  payload_hint: { en: 'Payload compressed to keep the room clear · click expand to inspect', fr: 'Payload compressé pour garder la salle claire · clique sur déplier pour inspecter' },

  // ── FindingsLive ───────────────────────────────────────────
  sev_critical: { en: 'CRITICAL', fr: 'CRITIQUE' },
  sev_high: { en: 'HIGH', fr: 'ÉLEVÉ' },
  sev_medium: { en: 'MEDIUM', fr: 'MOYEN' },
  sev_low: { en: 'LOW', fr: 'FAIBLE' },
  sev_info: { en: 'INFO', fr: 'INFO' },
  intel_title: { en: 'extracted intelligence', fr: 'renseignement extrait' },
  verdicts: { en: 'verdict', fr: 'verdict' },
  verdicts_plural: { en: 'verdicts', fr: 'verdicts' },

  // ── MarkdownMessage ────────────────────────────────────────
  md_copied: { en: 'copied ✓', fr: 'copié ✓' },

  // ── Dashboard ───────────────────────────────────────────────
  dash_executions: { en: 'executions', fr: 'exécutions' },
  dash_tools: { en: 'distinct tools', fr: 'outils distincts' },
  dash_strikes: { en: 'strikes', fr: 'frappes' },
  dash_exploitable: { en: 'exploitable verdicts', fr: 'verdicts exploitables' },
  dash_banked: { en: 'banked findings', fr: 'constats consignés' },
  dash_failures: { en: 'failures', fr: 'échecs' },
  dash_timeline: { en: 'timeline — mission life', fr: 'timeline — vie de la mission' },
  dash_sev_title: { en: 'finding severity', fr: 'sévérité des constats' },
  dash_top_tools: { en: 'most productive tools', fr: 'outils les plus productifs' },
  dash_empty_ledger: { en: 'ledger empty', fr: 'ledger vide' },
  dash_unavailable: { en: 'dashboard unavailable — backend unreachable', fr: 'dashboard indisponible — backend injoignable' },
  dash_reading: { en: 'reading the ledger…', fr: 'lecture du ledger…' },
  dash_none_exploitable: { en: 'no exploitable verdict', fr: 'aucun verdict exploitable' },
  dash_legend_ok: { en: 'ok', fr: 'ok' },
  dash_legend_exploit: { en: 'exploitable', fr: 'exploitable' },
  dash_legend_fail: { en: 'failure', fr: 'échec' },
}

export function t(key, vars) {
  const e = S[key]
  if (!e) return key
  let out = e[LANG] || e.en
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.split(`{${k}}`).join(String(v))
    }
  }
  return out
}
