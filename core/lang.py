# -*- coding: utf-8 -*-
"""REDACTED :: lang — user-facing string table (EN default, FR by knob).

LAWS:
  - English is the DEFAULT product language (international sale).
  - French stays available via config: provider.yaml `language: fr`
    (or env REDACTED_LANGUAGE / VOIDFORGE_LANGUAGE).
  - L(key) resolves at CALL time (config may load after this module).
  - Keys are stable identifiers; both languages must define every key.
  - Comments in code stay French — that's the internal dialect, never
    shipped to the operator's screen.

Usage:
    from core.lang import L
    print(L("workspace_ready"))        # -> EN by default
    set_language("fr")                  # runtime switch (tests, operator)
"""

# ── language state ─────────────────────────────────────────────────
_LANG = "en"
_VALID = ("en", "fr")


def set_language(lang):
    """Runtime override (config loader + tests). Silently ignores junk."""
    global _LANG
    if str(lang).strip().lower() in _VALID:
        _LANG = str(lang).strip().lower()


def get_language():
    return _LANG


def _from_env():
    import os
    for var in ("REDACTED_LANGUAGE", "VOIDFORGE_LANGUAGE"):
        v = os.environ.get(var, "").strip().lower()
        if v in _VALID:
            return v
    return None


# ── string table ───────────────────────────────────────────────────
# keys -> (en, fr). Keep keys verb-stable: workspace_ready, wall_detected…
_TABLE = {
    # workspace notices
    "workspace_ready": (
        "Workspace: missions/{target}/ — ledger, extractions, findings, reports",
        "Espace de travail : missions/{target}/ — ledger, extractions, findings, rapports"),
    "skills_active": (
        "Active skills: {skills}",
        "Skills actives : {skills}"),
    "transport_posture": (
        "Transport posture loaded",
        "Posture de transport chargée"),
    "doctrine_loaded": (
        "Self-authored doctrine loaded",
        "Doctrine self-authored chargée"),
    "plays_loaded": (
        "Learned arsenal loaded — {n} proven play(s) recalled at round 0",
        "Arsenal appris chargé — {n} play(s) prouvé(s) rappelé(s) au round 0"),
    "mcts_plan": (
        "MCTS tactical plan: {n} steps ({sample}…)",
        "Plan tactique MCTS : {n} étapes ({sample}…)"),
    # wall + intel
    "wall_detected": (
        "wall detected — automatic intel drop (wall_breaker)",
        "mur détecté — sortie intel automatique (wall_breaker)"),
    "coverage_order": (
        "Coverage order issued — cold bench(es): {benches}",
        "Ordre de couverture émis — banc(s) froid(s): {benches}"),
    # truncation / archive notices (fed to the LLM, shown in console)
    "truncated_full_in_extractions": (
        "…[truncated — full copy in missions/<target>/extractions/]",
        " …[tronqué — complet dans missions/<cible>/extractions/]"),
    "batch_head": (
        "[batch: {n} sub-results, each below]",
        "[batch: {n} sous-résultats, chacun ci-dessous]"),
    "batch_truncated": (
        "\n[batch truncated globally — the rest is archived in extractions/]",
        "\n[batch tronqué au global — le reste est archivé dans extractions/]"),
    "value_truncated": (
        "…[full copy archived in extractions/]",
        "…[archivé complet dans extractions/]"),
    "data_archived": (
        "…[truncated — DATA tools archive into missions/<target>/extractions/]",
        "…[tronqué — les outils DATA archivent dans missions/<cible>/extractions/]"),
    # reports
    "power_report_written": (
        "POWER report written: {path} ({n} traced strikes)",
        "Rapport de puissance écrit : {path} ({n} coups tracés)"),
    "autopsy_minted": (
        "Autopsy: doctrine minted from this mission's skips + wins",
        "Autopsy: doctrine minted from les skips + wins de cette mission"),
    "final_report_written": (
        "Final report written: {path}",
        "Rapport final écrit : {path}"),
    "verifier_sealed": (
        "Verifier VERDICT sealed — {path}",
        "VERDICT verifier scellé — {path}"),
    "harvest_play": (
        "Arsenal harvest: +{n} play(s) minted from the campaign ledger",
        "Arsenal harvest : +{n} play(s) mintés depuis le ledger campagne"),
    "deterministic_check": (
        "DETERMINISTIC CLAIM VERIFICATION",
        "VÉRIFICATION DÉTERMINISTE DES CLAIMS"),
    "det_found": (
        "The mechanical verifier found {n} artifact reference(s) with no "
        "match in the mission archive ({archive}):",
        "Le vérificateur mécanique a trouvé {n} référence(s) d'artefact sans "
        "correspondance dans l'archive de la mission ({archive}) :"),
    "det_unverified": (
        "(These claims are marked UNVERIFIED — the deliverable stays honest "
        "even if the model hallucinated a plausible name.)",
        "(Ces claims sont marqués NON VÉRIFIÉS — le deliverable reste honnête "
        "même si le modèle a halluciné un nom plausible.)"),
    "evidence_archived": (
        "EVIDENCE ARCHIVED — {dir}",
        "PREUVES ARCHIVÉES — {dir}"),
    "findings": ("Findings ({n})", "Findings ({n})"),
    "findings_none": (
        "no exploitable verdict this campaign",
        "aucun verdict exploitable cette campagne"),
    "extracted_data": (
        "Extracted data ({n} files)",
        "Données extraites ({n} fichiers)"),
    "campaign_ledger": (
        "Campaign (ledger) — {n} executions, {f} failure(s)",
        "Campagne (ledger) — {n} exécutions, {f} échec(s)"),
    # gates / refusals / role blocks
    "blocked_in_role": (
        "{tool}: blocked in this role",
        "{tool} : bloqué dans ce rôle"),
    "chromium_absent": (
        "Chromium absent from role",
        "Chromium absent du rôle"),
    "never_recall_note": (
        "Never re-issue a call \"to see the full result\" — it is already "
        "archived; read the file instead.",
        "Ne relance JAMAIS un appel \"pour voir le résultat complet\" — il "
        "est déjà archivé; lisez le fichier."),
    # license gate (commercial edition)
    "license_required": (
        "license required",
        "licence requise"),
    "license_activate_hint": (
        "activate with:  python main.py --activate RC-XXXX-XXXX-XXXX-XXXX",
        "activez avec :  python main.py --activate RC-XXXX-XXXX-XXXX-XXXX"),
    "no_license_found": (
        "no license found — run: voidforge --activate RC-XXXX-XXXX-XXXX-XXXX",
        "aucune licence trouvée — lancez : voidforge --activate "
        "RC-XXXX-XXXX-XXXX-XXXX"),
    "license_bound_other": (
        "license bound to another machine",
        "licence liée à une autre machine"),
    "reactivate_hint": (
        "invalid license token (signature verification failed) — reactivate "
        "with your key",
        "token de licence invalide (échec de vérification de signature) — "
        "réactivez avec votre clé"),
    "grace_exceeded": (
        "license grace window exceeded — reactivate",
        "fenêtre de grâce de licence dépassée — réactivez"),
    "activated_msg": (
        "REDACTED activated — plan: {plan}. License bound to this machine.",
        "REDACTED activé — plan : {plan}. Licence liée à cette machine."),
    "license_valid": (
        "license valid — plan: {plan}",
        "licence valide — plan : {plan}"),
    # ── pro report (report_pro) ─────────────────────────────────────
    "pro_exec_summary": ("EXECUTIVE SUMMARY", "SYNTHÈSE EXÉCUTIVE"),
    "pro_tech_report": ("TECHNICAL REPORT", "RAPPORT TECHNIQUE"),
    "pro_findings": ("Findings", "Constats"),
    "pro_severity": ("Severity", "Sévérité"),
    "pro_remediation": ("Remediation", "Remédiation"),
    "pro_vector": ("Vector", "Vecteur"),
    "pro_reference": ("Reference", "Référence"),
    "pro_arsenal": ("Arsenal ledger", "Registre d'arsenal"),
    "pro_roe": ("Rules of engagement", "Règles d'engagement"),
    "pro_print": ("Print / Save as PDF", "Imprimer / Enregistrer en PDF"),
    "pro_scope": ("Scope", "Périmètre"),
    "pro_generated": ("Generated", "Généré"),
    "pro_findings_none": (
        "No exploitable finding was banked this engagement.",
        "Aucun constat exploitable n'a été consigné cet engagement."),
    "pro_exec_intros": (
        "This report documents an autonomous offensive engagement. Every "
        "claim is backed by archived wire evidence; findings without "
        "on-disk proof are marked UNVERIFIED and excluded from the "
        "deliverable counts.",
        "Ce rapport documente un engagement offensif autonome. Chaque "
        "affirmation est adossée à une preuve réseau archivée ; les constats "
        "sans preuve sur disque sont marqués NON VÉRIFIÉS et exclus des "
        "décomptes du livrable."),
    "pro_of": ("of", "sur"),
    "pro_critical": ("CRITICAL", "CRITIQUE"),
    "pro_high": ("HIGH", "ÉLEVÉ"),
    "pro_medium": ("MEDIUM", "MOYEN"),
    "pro_low": ("LOW", "FAIBLE"),
    "pro_unverified_tag": ("UNVERIFIED", "NON VÉRIFIÉ"),
    "pro_printed_by": (
        "Generated by REDACTED — autonomous offensive engagement platform",
        "Généré par REDACTED — plateforme d'engagement offensif autonome"),
}


def L(key, **fmt):
    """Resolve a user-facing string in the active language.

    Falls back to EN if the key is missing in FR (and vice versa),
    and to the raw key if unknown — never crashes a mission over text.
    """
    global _LANG
    lang = _LANG
    env = _from_env()
    if env and env != _LANG:
        lang = env  # env knob wins (operator override)
    entry = _TABLE.get(key)
    if entry is None:
        return key  # unknown key: surface it raw (dev signal, no crash)
    idx = 0 if lang != "fr" else 1
    text = entry[idx]
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError):
            return text
    return text
