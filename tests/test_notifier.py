# -*- coding: utf-8 -*-
"""notifier battery: config-gated dispatch, dry-run capture, silent-fail.

LAWS under test: never crash a mission, disabled by default, dry_run
captures payloads for inspection, telegram/slack/discord URL build."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import core.notifier as N

CFG = N.CONFIG_PATH

def _write_cfg(**kw):
    import yaml
    with open(CFG, "w", encoding="utf-8") as f:
        yaml.safe_dump(kw, f)

# 1. disabled by default (config absent = OFF)
if os.path.exists(CFG):
    os.remove(CFG)
assert N.notify.critical_finding("target.com", "sk_live_admin_key") is False
assert N.notify.mission_complete("target.com", 5, 40) is False

# 2. enabled + dry_run: payload captured, nothing sent
_write_cfg(enabled=True, dry_run=True)
assert N.notify.critical_finding("target.com", "postgres://leak", "ctx") is True
p = N.notify.last_payload
assert p and "CRITICAL" in p["text"] and "target.com" in p["text"]
assert "postgres://leak" in p["text"]
assert N.notify.mission_complete("target.com", 7, 52, findings=3) is True
p2 = N.notify.last_payload
assert "mission complete" in p2["text"] and "3" in p2["text"]

# 3. real channel build (dry_run off, no network expected in test —
#    dispatch spawns the thread, URL construction must not raise)
_write_cfg(enabled=True, dry_run=False,
           telegram={"bot_token": "123:ABC", "chat_id": "42"},
           slack={"webhook_url": "https://hooks.slack.com/x"},
           discord={"webhook_url": "https://discord.com/api/webhooks/1/x"})
ok = N.notify.critical_finding("t.com", "evidence")
assert ok is True
assert N.notify.last_payload["channels"], "channels not built"
assert any("telegram" in u for u in N.notify.last_payload["channels"])
assert any("slack" in u for u in N.notify.last_payload["channels"])
assert any("discord" in u for u in N.notify.last_payload["channels"])

# 4. enabled but empty channels: no crash, returns False
_write_cfg(enabled=True, dry_run=True, telegram={})
assert N.notify.critical_finding("t", "e") is True  # dry-run still captures
N.notify.last_payload = None
_write_cfg(enabled=True, dry_run=False)  # enabled, no channels, not dry
assert N.notify.critical_finding("t", "e") is False

# 5. corrupt yaml: silent OFF, never a traceback
with open(CFG, "w", encoding="utf-8") as f:
    f.write("::: not yaml at all [[")
assert N.notify.mission_complete("t", 1, 1) is False

# cleanup: restore example-only state
if os.path.exists(CFG):
    os.remove(CFG)

print("[PASS] notifier: disabled-by-default, dry-run capture, channel "
      "build, empty-channel, corrupt-config silent")
