"""TOOL: workspace pens — the agent's own voice and memory.

The mission workspace (missions/<target>/) auto-archives every extraction,
every finding, every tool run. These tools give the MODEL her own pen:
she writes reports DURING the mission (phase recaps, strike reports,
extraction summaries), addresses the operator directly, and can consult
what is already archived so later rounds build on earlier evidence.
"""
import json

from tools import register
from core.mission_workspace import get_active


@register(name="report_write",
          desc="Write a report into the mission workspace (missions/<target>/reports/). Use after each phase: recon recap, strike report after a confirmed exploit, extraction summary after data pulls. This is YOUR dossier — write it as you fight.",
          params={"type": "object", "properties": {
              "title": {"description": "short report title (e.g. 'Recon phase — surface mapped')"},
              "content": {"description": "markdown body: what was done, what was found, verdicts, next intentions"},
              "kind": {"description": "report type: progress | strike | extraction | note"}},
              "required": ["title", "content"]},
          danger="safe")
def report_write(title, content, kind="progress"):
    ws = get_active()
    if ws is None:
        return json.dumps({"error": "no active mission workspace — only available inside a running mission"})
    path = ws.write_report(title, content, kind=kind)
    if path is None:
        return json.dumps({"error": "write failed"})
    return json.dumps({"tool": "report_write", "saved": path,
                       "summary": f"rapport '{title}' archivé ({kind})"})


@register(name="operator_message",
          desc="Send a direct message to the operator: status updates, a decision you need, a discovery worth announcing, or a warning. Appears in the live console. Keep it short and concrete.",
          params={"type": "object", "properties": {
              "text": {"description": "the message (1-3 sentences)"},
              "kind": {"description": "info | alert | question | victory"}},
              "required": ["text"]},
          danger="safe")
def operator_message(text, kind="info"):
    ws = get_active()
    if ws is not None:
        ws.log_comm(text, kind=kind)
    return json.dumps({"tool": "operator_message", "delivered": True,
                       "summary": f"[{kind}] {text[:120]}"})


@register(name="workspace_status",
          desc="List what is already archived in the mission workspace: extractions, findings, your own reports. Consult it to build on earlier evidence instead of re-running tools.",
          params={"type": "object", "properties": {}},
          danger="safe")
def workspace_status():
    ws = get_active()
    if ws is None:
        return json.dumps({"error": "no active mission workspace — only available inside a running mission"})
    return json.dumps({"tool": "workspace_status", **ws.status()})


@register(name="evidence_pack",
          desc="Return your complete evidence dossier: every finding verdict, every data extraction with previews, the discovered assets. CALL THIS IMMEDIATELY BEFORE WRITING YOUR FINAL REPORT — the report must cite this evidence, not recite it from memory.",
          params={"type": "object", "properties": {}},
          danger="safe")
def evidence_pack():
    ws = get_active()
    if ws is None:
        return json.dumps({"error": "no active mission workspace — only available inside a running mission"})
    pack = ws.proof_section(cap=5400)
    # blackboard assets: the map she built, as citable evidence
    try:
        from core.blackboard import get_active as get_board
        board = get_board()
        if board is not None and getattr(board, "assets", None):
            assets = sorted(board.assets.values(),
                            key=lambda a: -a.get("confidence", 0))[:24]
            lines = [f"- [{a['kind']}] {a['value'][:90]} (conf {round(a.get('confidence', 0.5), 2)}) "
                     f"via {', '.join(a.get('sources', [])[:3])}" for a in assets]
            pack += "\n\n### Assets découverts (le graphe)\n" + "\n".join(lines)
    except Exception:
        pass
    return pack
