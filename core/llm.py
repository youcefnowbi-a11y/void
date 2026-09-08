"""VOIDFORGE :: LLM client - any OpenAI-compatible endpoint."""
import json, time, urllib.request, urllib.error

# transient server-side refusals worth retrying (saturated free routers...)
_RETRYABLE = {429, 500, 502, 503, 504}
_BACKOFF_S = [2, 4, 8]  # short ladder — long sleeps here stack with the agent
                        # layer's retries and read as "the chat is frozen"

# K5-FAILOVER (LO's directive 2026-09-06): a router Postgres can die
# mid-campaign (b.ai died for ~40 min across missions H/I/K). The
# client now carries a provider FLEET — the first endpoint that
# answers wins; the last known-good is memoized and tried first on
# the next call. Defined as a module constant so the config loader
# (and only it) can rewrite the primary in flight.
FAILOVER_PROVIDERS = [
    # (base_url, api_key, model)
    # K5 (LO's arsenal, 2026-09-06): tokenrouter as the standing
    # second brain — proven FORGE-OK before mounting. The primary
    # (api.b.ai glm-5.3-flash) flapped for ~40 min across missions
    # H/I/K with its routing-DB outages; this one answered clean.
    ("https://api.tokenrouter.com/v1",
     "sk-Sjm2794mPacYSOie2UtKA4BWTawaRxyP90f8yIhaqla2Pwt2",
     "z-ai/glm-5.3-free"),
]


class LLM:
    def __init__(self, base_url, api_key, model, temperature=0.3):
        self.base_url = base_url.rstrip("/")
        self.key = api_key
        self.model = model
        self.temperature = temperature
        # K5: provider fleet — self first, then every failover entry.
        # _active_idx memoizes the last endpoint that ANSWERED so a
        # dying primary costs us exactly one probe, not one per round.
        self._fleet = [(self.base_url, self.key, self.model)] + [
            (u.rstrip("/"), k, m) for u, k, m in FAILOVER_PROVIDERS
            if u.rstrip("/") != self.base_url]
        self._active_idx = 0

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
        # K5-FAILOVER: patient loop per provider, then fleet rotation —
        # a dead primary (Postgres/router outage) burns its retries,
        # then the next endpoint takes the call without the agent
        # layer ever seeing an outage longer than one short backoff.
        resp = None  # audit #20 fix: a stale resp from a previous probe
                     # could survive a mid-loop provider rotation (the
                     # dir() sniff passed on the OLD provider's payload)
                     # and be parsed as this provider's answer.
        for _probe in range(len(self._fleet)):
            fbase, fkey, fmodel = self._fleet[self._active_idx]
            fbody = dict(body)
            fbody["model"] = fmodel
            fdata = json.dumps(fbody).encode()
            endpoint = fbase
            if not endpoint.endswith("/chat/completions"):
                endpoint = endpoint + "/chat/completions"
            req = urllib.request.Request(endpoint, method="POST")
            req.add_header("Authorization", f"Bearer {fkey}")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
            # patient loop: 429/5xx = the provider is drowning, not dead — retry
            # with growing pauses instead of abandoning the turn
            attempt = 0
            while True:
                try:
                    # X4.1 (audit-3): 180s here vs 300s in streaming — a response
                    # that would complete in 4 min via stream died here when
                    # falling back. Aligned at 300.
                    r = urllib.request.urlopen(req, data=fdata, timeout=300)
                    try:
                        # X4.3: a malformed provider echoing the full context
                        # could return 100KB+ — cap the read, the payload we
                        # need is a JSON envelope.
                        resp = json.loads(r.read(2_000_000).decode())
                    finally:
                        try:
                            r.close()
                        except Exception:
                            pass
                    break
                except urllib.error.HTTPError as ex:
                    # X4.2: 400 chars cut "context length exceeded — reduce to N
                    # tokens" mid-sentence, losing the actionable part.
                    body_txt = ex.read().decode(errors="replace")[:1600]
                    if ex.code in _RETRYABLE and attempt < len(_BACKOFF_S):
                        time.sleep(_BACKOFF_S[attempt])
                        attempt += 1
                        continue
                    # K5: non-retryable HTTP error on THIS endpoint → try
                    # the next provider before declaring the layer dead
                    if _probe + 1 < len(self._fleet):
                        self._active_idx = (self._active_idx + 1) % len(self._fleet)
                        break
                    return {"content": f"[LLM HTTP {ex.code}] {body_txt}", "tool_calls": []}
                except Exception as ex:
                    # réseau mort / timeout / DNS on THIS endpoint → next
                    # provider; only if the WHOLE fleet is unreachable do we
                    # hand back to the agent layer's own retry doctrine.
                    if _probe + 1 < len(self._fleet):
                        self._active_idx = (self._active_idx + 1) % len(self._fleet)
                        break
                    return {"content": f"[LLM UNREACHABLE] {type(ex).__name__}: {str(ex)[:200]}", "tool_calls": []}
            else:
                # inner while exhausted without break → unreachable in
                # practice (backoff ladder ends in a return/continue),
                # kept for structural safety
                continue
            if isinstance(resp, dict) and resp.get("choices"):
                break
        choices = (resp or {}).get("choices") or []
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
