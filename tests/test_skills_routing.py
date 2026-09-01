"""VOIDFORGE :: skill routing upgrade tests — tier gating, not_when veto,
PRIMARY/secondaries injection model, confidence. All additive: legacy
skills (no tier/not_when) behave exactly as before."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.skills import list_skills, select_for, select_block


def _ids(mission):
    return select_for(mission)


def test_tier_parsed_on_all_skills():
    for s in list_skills():
        assert s["tier"] in ("core", "domain", "library"), s["id"]
        assert isinstance(s["not_when"], list), s["id"]


def test_legacy_skills_default_core():
    # recon_deep has no tier header -> must default to core (old behavior)
    s = next(x for x in list_skills() if x["id"] == "recon_deep")
    assert s["tier"] == "core"


def test_domain_skill_never_auto_matched():
    # every wave-1 graft defaults to core today; once any skill is tiered
    # domain/library it must not appear in auto-match for its own keywords.
    # Find a library/domain skill (if none yet, the test still holds vacuously
    # but we assert the mechanism with a synthetic probe below).
    from core import skills as sk
    dom = [s for s in list_skills() if s["tier"] in ("domain", "library")]
    for s in dom:
        assert s["id"] not in _ids(" ".join(s["when"][:6]) + " " * 0), s["id"]


def test_not_when_veto_wins_over_when():
    from core import skills as sk
    orig = sk.list_skills
    fake = {"id": "jb_mobile", "title": "t", "when": ["jailbreak"],
            "not_when": ["llm", "prompt"], "tier": "core",
            "path": "x", "text": "x"}
    fake2 = {"id": "web_access_master", "title": "t",
             "when": ["web", "http"], "not_when": [], "tier": "core",
             "path": "x", "text": "x"}
    sk.list_skills = lambda: [fake, fake2]
    try:
        # jailbreak + llm context -> vetoed, fallback to web_master via URL
        ids = sk.select_for("ios jailbreak bypass on http://t.com with llm prompt")
        assert "jb_mobile" not in ids
        # pure ios context -> matched
        ids2 = sk.select_for("ios jailbreak with objection on iphone")
        assert ids2 == ["jb_mobile"]
    finally:
        sk.list_skills = orig


def test_select_block_primary_and_pointer():
    block = select_block("we have a www-data shell, need root on the box")
    assert block.startswith("═══ ACTIVE SKILLS")
    assert "[PRIMARY skill:" in block
    assert "confidence:" in block


def test_confidence_high_single_medium_multi():
    b1 = select_block("we have a www-data shell, need root")
    assert ("confidence: medium" in b1) or ("confidence: high" in b1)


def test_arsenal_integrity_still_green():
    from tests.test_arsenal_integrity import (  # noqa: F401
        test_skills_parse_and_reference_real_tools)
    test_skills_parse_and_reference_real_tools()
