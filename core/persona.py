"""VOIDFORGE :: agent personality system.

Define WHO the agent is before it starts. Three layers of control:

  1. config/persona.yaml   — the operator's persona file (auto-loaded by the
                             Agent when present; --persona PATH overrides).
  2. DEFAULTS below        — everything the yaml may omit.
  3. persona_prompt()      — renders the persona as a prompt block appended
                             to the base doctrine in core/agent.py.

mission_focus maps to concrete behavioral doctrine:
  speed        -> fast high-yield chains, stop when marginal gain < threshold
  thoroughness -> exhaust every viable vector before reporting
  stealth      -> minimize request volume, prefer passive/archive sources
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT, "config", "persona.yaml")

DEFAULTS = {
    "name": "VOIDFORGE",
    "archetype": "elite autonomous offensive-security operator",
    "tone": "surgical and decisive",
    "verbosity": "medium",           # terse | medium | detailed
    "language": "en",                # en | fr | mixed
    "mission_focus": "thoroughness", # speed | thoroughness | stealth
    "catchphrases": [],
    "extra_directives": "",
}

_FOCUS_DOCTRINE = {
    "speed": (
        "SPEED DOCTRINE: Prefer fast, high-yield tool chains. Skip marginal probes. "
        "Stop the mission as soon as marginal information gain per request drops below useful."),
    "thoroughness": (
        "THOROUGHNESS DOCTRINE: Exhaust every viable attack vector before reporting. "
        "Cross-verify each finding with a second tool. Never stop early."),
    "stealth": (
        "STEALTH DOCTRINE: Minimize request volume. Prefer passive sources (archives, "
        "certificate logs, HAR forensics) before active probing. Spread requests over time."),
}

_VERBOSITY = {
    "terse": "Answer in minimal bullet points. No prose.",
    "medium": "Balance concise bullets with short justifications.",
    "detailed": "Explain reasoning fully; include evidence chains and next-step options.",
}


def _merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if v not in (None, ""):
            out[k] = v
    return out


def load_persona(path=None):
    """Load persona from yaml. Falls back to config/persona.yaml, then pure
    DEFAULTS. Returns {} meaning 'no persona' only if file missing AND you
    call load_persona(required=False); normal calls always yield a dict."""
    import yaml
    candidates = [path] if path else [DEFAULT_PATH]
    data = {}
    for c in candidates:
        if c and os.path.exists(c):
            with open(c, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            data = raw.get("persona", raw)
            break
    return _merge(DEFAULTS, data)


def persona_prompt(p):
    """Render persona dict as a prompt block for the agent's system message."""
    if not p:
        return ""
    lines = [
        "═══ OPERATOR PERSONA OVERRIDE ═══",
        f"You are {p.get('name', 'VOIDFORGE')} — {p.get('archetype', DEFAULTS['archetype'])}.",
        f"Tone: {p.get('tone', DEFAULTS['tone'])}.",
        f"Response style: {_VERBOSITY.get(p.get('verbosity', 'medium'), '')}",
    ]
    lang = p.get("language", "en")
    if lang == "fr":
        lines.append("Language: write all narration and reports in French.")
    elif lang == "mixed":
        lines.append("Language: mix French narration with English technical terms.")
    focus = str(p.get("mission_focus", "thoroughness")).lower()
    lines.append(_FOCUS_DOCTRINE.get(focus, _FOCUS_DOCTRINE["thoroughness"]))
    catch = p.get("catchphrases") or []
    if catch:
        lines.append("Signature phrases (use sparingly, at plan start or mission completion): "
                     + " | ".join(f'"{c}"' for c in catch))
    extra = (p.get("extra_directives") or "").strip()
    if extra:
        lines.append("Extra directives from the operator:\n" + extra)
    lines.append("This persona supersedes stylistic defaults but NEVER operational doctrine.")
    return "\n".join(lines)
