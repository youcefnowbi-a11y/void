# -*- coding: utf-8 -*-
"""REDACTED :: notifier — mission events to the operator's pocket.

LAWS:
  - NEVER crashes a mission. Every path is try/except-quiet: a dead
    webhook is a silent shame, not an aborted campaign.
  - Config in config/notifications.yaml; absent file = notifier OFF.
  - dry_run: True captures the payload instead of sending (tests,
    operator rehearsal) — exposes .last_payload for inspection.
  - Notifications fire on: CRITICAL verdict banked, mission complete.
  - Sends are POSTs with 8s timeout, one retry, then give up.
"""
import json
import os
import threading
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "notifications.yaml")


def _load_cfg():
    """Read notifications.yaml; missing/corrupt = disabled."""
    try:
        import yaml
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


class _Notifier:
    """Lazy singleton — config read once per call-site burst, not once
    per import (operator can edit the yaml mid-campaign)."""

    def __init__(self):
        self.last_payload = None

    # ── public entrypoints ───────────────────────────────────
    def critical_finding(self, target, evidence, context=""):
        """CRITICAL verdict banked — the operator's phone buzzes."""
        cfg = _load_cfg()
        if not cfg.get("enabled", False):
            return False
        text = (f"🚨 REDACTED — CRITICAL finding banked\n"
                f"target: {target or '?'}\n"
                f"evidence: {str(evidence)[:300]}")
        if context:
            text += f"\ncontext: {str(context)[:200]}"
        return self._dispatch(cfg, text)

    def mission_complete(self, target, rounds, tools_used, findings=0):
        """Mission closure — the summary line for the pocket."""
        cfg = _load_cfg()
        if not cfg.get("enabled", False):
            return False
        text = (f"✅ REDACTED — mission complete\n"
                f"target: {target or '?'}\n"
                f"rounds: {rounds} · tools: {tools_used} · "
                f"banked findings: {findings}")
        return self._dispatch(cfg, text)

    # ── dispatch: fan out to every configured channel ────────
    def _dispatch(self, cfg, text):
        """Fire all channels (telegram / slack / discord / webhook).
        dry_run captures instead of sending. One thread so the
        mission loop NEVER waits on a webhook."""
        payload = {"text": text, "channels": []}
        try:
            if cfg.get("dry_run"):
                payload["dry_run"] = True
                self.last_payload = payload
                return True
            urls = []
            tg = (cfg.get("telegram") or {})
            if tg.get("bot_token") and tg.get("chat_id"):
                urls.append((
                    f"https://api.telegram.org/bot{tg['bot_token']}"
                    f"/sendMessage",
                    json.dumps({"chat_id": tg["chat_id"],
                                "text": text}).encode()))
            sl = (cfg.get("slack") or {})
            if sl.get("webhook_url"):
                urls.append((sl["webhook_url"],
                             json.dumps({"text": text}).encode()))
            dc = (cfg.get("discord") or {})
            if dc.get("webhook_url"):
                urls.append((dc["webhook_url"],
                             json.dumps({"content": text}).encode()))
            wh = (cfg.get("webhook") or {})
            if wh.get("url"):
                urls.append((wh["url"],
                             json.dumps({"event": "redacted",
                                         "text": text}).encode()))
            if not urls:
                self.last_payload = payload
                return False
            t = threading.Thread(target=self._fire, args=(urls,),
                                 daemon=True)
            t.start()
            payload["channels"] = [u for u, _ in urls]
            self.last_payload = payload
            return True
        except Exception:
            self.last_payload = payload
            return False

    @staticmethod
    def _fire(urls):
        """POST each URL — 8s timeout, one retry, silent failure."""
        for url, body in urls:
            for attempt in (1, 2):
                try:
                    req = urllib.request.Request(
                        url, data=body,
                        headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=8).read()
                    break
                except Exception:
                    if attempt == 2:
                        pass  # silent: never wake the mission


# module-level handle — import cheap, config read at fire time
notify = _Notifier()
