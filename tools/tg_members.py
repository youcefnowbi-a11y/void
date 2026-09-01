"""TOOL: tg_members - Telethon-based group member scraper (requires .session file)."""
import json, os
from tools import register

@register(name="tg_members_scrape",
          desc="Scrape members of a Telegram group/channel via Telethon userbot session. Requires session_path to a valid .session file.",
          params={"type":"object","properties":{
              "session_path":{"type":"string"},
              "api_id":{"type":"integer"},
              "api_hash":{"type":"string"},
              "group":{"type":"string","description":"@handle or id"},
              "limit":{"type":"integer"}},
              "required":["session_path","api_id","api_hash","group"]})
def tg_members_scrape(session_path, api_id, api_hash, group, limit=500):
    try:
        from telethon.sync import TelegramClient
        from telethon.tl.functions.channels import GetParticipantsRequest
        from telethon.tl.types import ChannelParticipantsSearch
    except ImportError:
        return "telethon not installed: pip install telethon"
    if not os.path.exists(session_path):
        return f"session file missing: {session_path}"
    members = []
    with TelegramClient(session_path, int(api_id), str(api_hash)) as client:
        entity = client.get_entity(group)
        offset = 0
        while len(members) < limit:
            part = client(GetParticipantsRequest(
                entity, ChannelParticipantsSearch(""), offset, 100, 0))
            if not part.users: break
            for u in part.users:
                members.append({"id": u.id, "username": u.username,
                                "first": u.first_name, "last": u.last_name,
                                "bot": u.bot, "premium": getattr(u, "premium", False)})
            offset += len(part.users)
            if not part.users: break
    return json.dumps({"group": group, "count": len(members),
                       "members": members[:int(limit)]}, ensure_ascii=False, indent=1)

@register(name="tg_messages_dump",
          desc="Dump last N messages of a group/channel via Telethon session (full text + sender + date).",
          params={"type":"object","properties":{
              "session_path":{"type":"string"},"api_id":{"type":"integer"},
              "api_hash":{"type":"string"},"group":{"type":"string"},
              "limit":{"type":"integer"}},
              "required":["session_path","api_id","api_hash","group"]})
def tg_messages_dump(session_path, api_id, api_hash, group, limit=200):
    try:
        from telethon.sync import TelegramClient
    except ImportError:
        return "telethon not installed"
    if not os.path.exists(session_path):
        return f"session missing: {session_path}"
    msgs = []
    with TelegramClient(session_path, int(api_id), str(api_hash)) as client:
        entity = client.get_entity(group)
        for m in client.iter_messages(entity, limit=int(limit)):
            msgs.append({"date": str(m.date), "sender_id": m.sender_id,
                         "text": (m.text or "")[:300]})
    return json.dumps({"group": group, "count": len(msgs), "messages": msgs},
                      ensure_ascii=False, indent=1)
