"""TOOL: ws_tap - Supabase/Phoenix realtime websocket tap (postgres_changes spy)."""
import json, asyncio, os, urllib.request
from tools import register

@register(name="realtime_tap",
          desc="Connect to Supabase realtime websocket, join postgres_changes on tables, capture live row payloads. Runs for N seconds.",
          params={"type":"object","properties":{
              "ws_base":{"type":"string","description":"wss://xxx.supabase.co/realtime/v1/websocket"},
              "anon_key":{"type":"string"},
              "tables":{"type":"array","items":{"type":"string"}},
              "token":{"type":"string","description":"optional authenticated token"},
              "duration_s":{"type":"integer"}},
              "required":["ws_base","anon_key","tables"]})
def realtime_tap(ws_base, anon_key, tables, token=None, duration_s=45):
    duration_s = max(5, min(int(duration_s or 45), 600))  # clamp: max 10 min de tap
    try:
        import websockets
    except ImportError:
        return "websockets not installed: pip install websockets"

    async def run():
        out = []
        uri = f"{ws_base}?apikey={anon_key}&vsn=1.0.0"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with websockets.connect(uri, additional_headers=headers, open_timeout=25,
                                      ping_interval=20) as ws:
            await ws.send(json.dumps({"topic":"phoenix","event":"phx_join","ref":"1","payload":{}}))
            ref = 10
            for t in tables:
                ref += 1
                await ws.send(json.dumps({
                    "topic": "realtime:public", "event": "phx_join", "ref": str(ref),
                    "payload": {"config": {
                        "broadcast": {"self": True}, "presence": {"key": ""},
                        "postgres_changes": [{"event": "*", "schema": "public", "table": t}]
                    }, **({"access_token": token} if token else {})}}))
            _out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
            os.makedirs(_out_dir, exist_ok=True)
            # with: le handle ne doit jamais rester ouvert sur exception/timeout
            with open(os.path.join(_out_dir, "realtime_capture.jsonl"), "a", encoding="utf-8") as log:
                end = asyncio.get_event_loop().time() + int(duration_s)
                while asyncio.get_event_loop().time() < end:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=max(1, end - asyncio.get_event_loop().time()))
                        msg = json.loads(raw)
                        if msg.get("event") == "postgres_changes":
                            line = json.dumps(msg, ensure_ascii=False)
                            out.append(line[:800])
                            log.write(line + "\n"); log.flush()
                    except asyncio.TimeoutError:
                        break
        return out

    try:
        results = asyncio.run(run())
    except Exception as ex:
        # connect/recv failure → payload d'erreur, jamais de traceback brut au LLM
        return json.dumps({"error": f"realtime_tap failed: {type(ex).__name__}: {str(ex)[:200]}",
                           "events_captured": 0, "events": []}, ensure_ascii=False, indent=1)
    return json.dumps({"events_captured": len(results), "events": results[:20]}, ensure_ascii=False, indent=1)
