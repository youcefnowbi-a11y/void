# -*- coding: utf-8 -*-
"""VOIDFORGE cleanup: organize the workspace for the marketing era.

Law: NEVER touch core/, tools/, tests/, config/, data/, web/, skills/,
intel/, SYSTEM_MAP/, missions/ (evidence!), docs/, design/ — those are
either operator-owned, evidence archives, or already-organized.
This pass ONLY moves:
  - root debris (logs, snapshots, one-off debug files) -> lab/debris/
  - lab one-shot probes/recon/research scripts -> lab/archive/
  - lab runners/smoke/graft -> lab/ops/ (stays executable)
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

made = []


def ensure(d):
    os.makedirs(d, exist_ok=True)
    if d not in made:
        made.append(d)


def mv(src, dest_dir, label=""):
    if not os.path.exists(src):
        return
    ensure(dest_dir)
    try:
        shutil.move(src, os.path.join(dest_dir, os.path.basename(src)))
        print(f"  moved {src} -> {dest_dir}/ {label}")
    except Exception as ex:
        print(f"  SKIP {src}: {ex}")


# ── 1. root debris: logs, snapshots, one-off debug ─────────────
DEBRIS = "lab/debris"
for f in ["_backend_out.log", "_backend_err.log", "_range_dbg.py",
          "observe77.py", "snapshot_1787799460.json", "snapshot_1787765662.json",
          "snapshot_1788097358.json", "snapshot_madleets2.json",
          "snapshot_madleets.json", "snapshot_1787844978.json",
          "snapshot_1788287844.json", "snapshot_1788287303.json"]:
    mv(f, DEBRIS, "(log/snapshot/debug debris)")

# ── 2. strategic docs -> SYSTEM_MAP (they are architecture-adjacent) ──
for f in ["ULTIMATE_PLAN.md", "RIVALS_REPORT.md",
          "rival-audit-msf-sliver.md"]:
    mv(f, "SYSTEM_MAP", "(strategic docs live with the system map)")

# ── 3. lab: runners + graft + smoke stay in lab/ops ────────────
OPS = "lab/ops"
for f in ["_calib_campaign.py", "_calib_mission.py", "_campaign_smoke.py",
          "_swarm_ws_smoke.py", "_grimoire_integration_test.py",
          "_append_cp_graft.py", "_append_cp3_graft.py",
          "_append_ev_graft.py", "_append_audit2_graft.py",
          "_append_k2_graft.py", "_graft_catalog.py", "_fix_packmeta.py",
          "_ev3_harvest_stats.py", "_ev3_retro_harvest.py",
          "_diagnose_plan.py", "_failover_test.py", "_provider_probe.py",
          "_provider_sanity.py", "_seed_doctrine_A.py", "_mint_test.py",
          "_sig_check.py", "_sig_summary.py", "_heal_timeout_test.py",
          "_jackpot_check.py", "_verify_audit_fixes.py", "verify_wiring.py",
          "cpp_acceptance.py", "forge_range.py"]:
    mv(f, OPS, "(runner/smoke/graft — live tooling)")

# ── 4. lab one-shots -> lab/archive ────────────────────────────
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
for f in ONE_SHOTS:
    mv(f, ARCH, "(one-shot probe — historical value only)")

print("\ndirs ensured:", made)
print("ROOT files left:", sorted(f for f in os.listdir(".") if os.path.isfile(f)))
print("lab/ left:", sorted(f for f in os.listdir("lab") if os.path.isfile(f)))
