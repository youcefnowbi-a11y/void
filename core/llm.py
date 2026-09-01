"""VOIDFORGE :: LLM client - any OpenAI-compatible endpoint."""
import json, time, urllib.request, urllib.error

# transient server-side refusals worth retrying (saturated free routers...)
_RETRYABLE = {429, 500, 502, 503, 504}
_BACKOFF_S = [2, 4, 8]  # short ladder — long sleeps here stack with the agent
                        # layer's retries and read as "the chat is frozen"

class LLM:
    def __init__(self, base_url, api_key, model, temperature=0.3):
        self.base_url = base_url.rstrip("/")
        self.key = api_key
        self.model = model
        self.temperature = temperature

    def chat_stream(self, messages, tools=None, max_tokens=None, on_delta=None):
        """Streaming variant: returns the SAME dict shape as chat(); fires
        on_delta(text_chunk) for every content delta as it arrives. Falls
        back to the blocking chat() on any streaming failure — streaming is
        a latency-perception upgrade, never a correctness risk."""
        body = {"model": self.model, "temperature": self.temperature,
                "messages": messages, "stream": True}
        if max_tokens:
            body["max_tokens"] = int(max_tokens)
        if tools:
            body["tools"] = [{"type": "function",
                              "function": {"name": t["name"],
                                           "description": t["desc"],
                                           "parameters": t.get("params") or {"type": "object", "properties": {}}}}
                             for t in tools]
        endpoint = self.base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint + "/chat/completions"

        req = urllib.request.Request(endpoint, method="POST")
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "text/event-stream")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
        data = json.dumps(body).encode()
        try:
            r = urllib.request.urlopen(req, data=data, timeout=300)
        except urllib.error.HTTPError as ex:
            if ex.code in _RETRYABLE:
                r = None  # saturated — let the blocking retry loop handle it
            else:
                return self.chat(messages, tools=tools, max_tokens=max_tokens)
        except Exception:
            r = None  # network hiccup — same fallback
        if r is None:
            return self.chat(messages, tools=tools, max_tokens=max_tokens)

        content_parts = []
        tool_calls = {}  # index -> {"id","name","args"}
        any_frame = False
        try:
            for raw in r:
                line = raw.decode(errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except Exception:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0] or {}).get("delta") or {}
                piece = delta.get("content")
                if piece:
                    any_frame = True
                    content_parts.append(piece)
                    if on_delta:
                        try:
                            on_delta(piece)
                        except Exception:
                            pass
                for tc in delta.get("tool_calls") or []:
                    any_frame = True
                    idx = tc.get("index", 0) or 0
                    slot = tool_calls.setdefault(idx, {"id": f"call_{idx}", "name": "", "args": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name") and not slot["name"]:
                        slot["name"] = fn["name"]  # R1-6: pas de concat en streaming (« tooltool »)
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]
        except Exception:
            # mid-stream failure with nothing usable → blocking fallback
            if not any_frame:
                return self.chat(messages, tools=tools, max_tokens=max_tokens)
        finally:
            try:
                r.close()
            except Exception:
                pass
        if not any_frame:
            return self.chat(messages, tools=tools, max_tokens=max_tokens)
        parsed = []
        for idx in sorted(tool_calls):
            slot = tool_calls[idx]
            raw_args = slot["args"] or "{}"
            try:
                args = json.loads(raw_args)
                if not isinstance(args, dict):
                    args = {"_args_error": "arguments must be a JSON object"}
            except Exception:
                try:
                    s = raw_args.strip()
                    args = json.loads(s[s.index("{"):s.rindex("}") + 1])
                except Exception:
                    args = {"_args_error": f"arguments were not valid JSON: {raw_args[:180]}"}
            parsed.append({"id": slot["id"], "name": slot["name"], "args": args})
        return {"content": ("".join(content_parts)) or None, "tool_calls": parsed}

    def chat(self, messages, tools=None, max_tokens=None):
        """Returns dict: {content, tool_calls:[{id,name,args}]}"""
        body = {"model": self.model, "temperature": self.temperature,
                "messages": messages}
        if max_tokens:
            body["max_tokens"] = int(max_tokens)
        if tools:
            body["tools"] = [{"type": "function",
                              "function": {"name": t["name"],
                                           "description": t["desc"],
                                           "parameters": t.get("params") or {"type": "object", "properties": {}}}}
                             for t in tools]
        endpoint = self.base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint + "/chat/completions"

        req = urllib.request.Request(endpoint, method="POST")
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
        data = json.dumps(body).encode()
        # patient loop: 429/5xx = the provider is drowning, not dead — retry
        # with growing pauses instead of abandoning the turn
        attempt = 0
        while True:
            try:
                r = urllib.request.urlopen(req, data=data, timeout=180)
                try:
                    resp = json.loads(r.read().decode())
                finally:
                    try:
                        r.close()
                    except Exception:
                        pass
                break
            except urllib.error.HTTPError as ex:
                body_txt = ex.read().decode(errors="replace")[:400]
                if ex.code in _RETRYABLE and attempt < len(_BACKOFF_S):
                    time.sleep(_BACKOFF_S[attempt])
                    attempt += 1
                    continue
                return {"content": f"[LLM HTTP {ex.code}] {body_txt}", "tool_calls": []}
            except Exception as ex:
                # réseau mort / timeout / DNS : on rend la main à l'agent au lieu de
                # crasher toute la mission — il pourra retenter au round suivant.
                return {"content": f"[LLM UNREACHABLE] {type(ex).__name__}: {str(ex)[:200]}", "tool_calls": []}
        choices = resp.get("choices") or []
        if not choices:
            return {"content": f"[LLM MALFORMED] no choices in response: {str(resp)[:200]}", "tool_calls": []}
        msg = (choices[0] or {}).get("message") or {}
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        tcs = []
        for tc in msg.get("tool_calls") or []:
            fn = tc["function"]
            raw_args = fn.get("arguments") or "{}"
            args = None
            try:
                args = json.loads(raw_args)
                if not isinstance(args, dict):
                    args = {"_args_error": f"arguments must be a JSON object, got {type(args).__name__}"}
            except Exception:
                # salvage pass: strip markdown fences / trailing garbage, retry once
                salv = raw_args.strip()
                if salv.startswith("```"):
                    salv = salv.strip("`")
                    if salv.startswith("json"):
                        salv = salv[4:]
                try:
                    args = json.loads(salv[salv.index("{"):salv.rindex("}") + 1])
                except Exception:
                    args = {"_args_error": f"arguments were not valid JSON: {raw_args[:180]}"}
            tcs.append({"id": tc["id"], "name": fn["name"], "args": args})
        return {"content": msg.get("content"), "reasoning": reasoning, "tool_calls": tcs}
