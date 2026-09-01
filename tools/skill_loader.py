"""TOOL: skill loader - lets the agent pull composed expertise mid-mission.

Skills are the difference between a tool and a doctrine: when to strike,
what order, which payload variant, what to do when the wall pushes back.
The agent auto-receives matched skills at mission start; these two tools
let her browse and load the full library on demand.
"""
import json, re

from tools import register
from core.skills import list_skills, load_skill

_SKILL_ID = re.compile(r"^[a-z0-9_]{2,40}$")


@register(name="skill_list",
          desc="List every available skill (composed operational expertise: attack chains, payload grammars, tradecraft). Load one with skill_load when the mission enters its domain.",
          params={"type": "object", "properties": {}},
          danger="safe")
def skill_list():
    skills = list_skills()
    return json.dumps({
        "count": len(skills),
        "skills": [{"id": s["id"], "title": s["title"],
                    "triggers": s["when"][:12]} for s in skills],
    }, ensure_ascii=False, indent=1)


@register(name="skill_load",
          desc="Load a skill's full playbook into your context: attack chain, technique matrix, payload grammar, pivots, failure modes. Call when the mission enters the skill's domain.",
          params={"type": "object", "properties": {
              "skill_id": {"description": "skill id from skill_list (e.g. privesc_linux)"}},
              "required": ["skill_id"]},
          danger="safe")
def skill_load(skill_id):
    # R3-8: id validé avant load_skill — pas d'arbitraire au loader
    if not skill_id or not _SKILL_ID.match(str(skill_id)):
        return f"TOOL ERROR [ARGS]: skill_id invalide (attendu ^[a-z0-9_]{{2,40}}$): {skill_id!r}"
    text = load_skill(skill_id)
    if text is None:
        known = ", ".join(s["id"] for s in list_skills()) or "none"
        return json.dumps({"error": f"unknown skill '{skill_id}'",
                           "known_skills": known}, ensure_ascii=False)
    text = str(text)
    # fichier vide qui ressemble à un succès = erreur, pas du silence
    if not text.strip():
        return f"TOOL ERROR [EMPTY]: skill '{skill_id}' existe mais est vide"
    # cap de taille — contraste avec cn_fingerprint [:6000] : 20k + marqueur
    if len(text) > 20000:
        text = text[:20000] + "\n...[truncated]"
    return text
