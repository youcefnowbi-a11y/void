# -*- coding: utf-8 -*-
"""VOIDFORGE cleanup pass 2: lab scripts were referenced without the
lab/ prefix — this pass fixes it. Also archives screenshots, ground
files, and keeps the mission briefs + runner in a clean ops/ layout."""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def mv(src, dest_dir):
    if not os.path.exists(src):
        return
    os.makedirs(dest_dir, exist_ok=True)
    try:
        shutil.move(src, os.path.join(dest_dir, os.path.basename(src)))
        print(f"  {src} -> {dest_dir}/")
    except Exception as ex:
        print(f"  SKIP {src}: {ex}")


OPS = "lab/ops"
RUNNERS = ["_calib_campaign.py", "_calib_mission.py", "_campaign_smoke.py",
           "_grimoire_integration_test.py",
           "_append_cp_graft.py", "_append_cp3_graft.py", "_append_ev_graft.py",
           "_append_audit2_graft.py", "_append_k2_graft.py",
           "_graft_catalog.py", "_fix_packmeta.py",
           "_ev3_harvest_stats.py", "_ev3_retro_harvest.py",
           "_diagnose_plan.py", "_failover_test.py", "_provider_probe.py",
           "_provider_sanity.py", "_seed_doctrine_A.py", "_mint_test.py",
           "_sig_check.py", "_sig_summary.py", "_heal_timeout_test.py",
           "_jackpot_check.py", "_verify_audit_fixes.py", "verify_wiring.py",
           "cpp_acceptance.py", "forge_range.py"]
print("== runners/graft -> lab/ops ==")
for f in RUNNERS:
    mv("lab/" + f, OPS)

ARCH = "lab/archive"
ONE_SHOTS = [
    "cache_probe.py", "coercion_probe.py", "debug_skills.py",
    "interview_compact.py", "interview_model.py", "list_tools.py",
    "post_probe.py", "probe_emu.py", "probe_emu2.py", "probe_emu3.py",
    "probe_emu4.py", "probe_selftest.py", "probe_timeout.py",
    "probe_tri.py", "probe_tri2.py", "proof_probe.py",
    "reasoning_probe.py", "skill_research.py", "smoke_advanced.py",
    "test_chatplan.py", "test_forge.py", "test_strike_demo.py",
    "test_workspace.py", "timing_probe.py", "ttft_probe.py",
    "vision_audit.py", "vision_audit_v2.py", "ws_probe.py",
    "_dbg3.py", "_k2_api_oracle.py", "_k2_api_oracle2.py",
    "_k2_api_oracle3.py", "_k2_fix_verify.py", "_k2_tma_retest.py",
    "_playformto_recon.py", "_playformto_recon2.py", "_playformto_recon3.py",
    "_playformto_recon4.py", "_playformto_recon5.py", "_playformto_recon6.py",
    "_tail_verify.py", "_wire_body_test.py", "_wire_test.py",
]
print("== one-shots -> lab/archive ==")
for f in ONE_SHOTS:
    mv("lab/" + f, ARCH)

# screenshots + ground dumps + briefs of DONE missions -> archive
EXTRA = ["dom_ground.html", "shot_ground.png", "shot_v2.png", "shot_v3.png",
         "shot_v4.png", "shot_v5.png", "shot_v6.png",
         "mission_F_brief.md", "mission_F2_brief.md", "mission_G_brief.md",
         "mission_H_brief.md", "mission_H3_brief.md", "mission_I_brief.md",
         "mission_J_brief.md", "mission_K_brief.md", "mission_P1_brief.md",
         "mission_P2_brief.md", "mission_CP1_brief.md", "mission_CP3_brief.md",
         "_intel_exploitarium.md", "_intel_z4nzu_tools.md", "_insert_rule7.py"]
print("== evidence/briefs/screenshots -> lab/archive ==")
for f in EXTRA:
    mv("lab/" + f, ARCH)

# old calib dirs -> lab/archive/calib_runs (keep CP* live — recent proof)
print("== old calib dirs -> lab/archive/calib_runs ==")
for d in sorted(os.listdir("lab")):
    p = os.path.join("lab", d)
    if os.path.isdir(p) and (d.startswith("calib_") or d == "tmp_tri"):
        mv(p, "lab/archive/calib_runs")

print("\n== lab/ final state ==")
print(sorted(os.listdir("lab")))
print("\n== ops count:", len([f for f in os.listdir('lab/ops') if f.endswith('.py')]))
print("== archive count:", len(os.listdir('lab/archive')))
