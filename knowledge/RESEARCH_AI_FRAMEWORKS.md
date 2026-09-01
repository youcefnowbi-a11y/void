# VOIDFORGE RESEARCH — AI Offensive Framework Landscape (survey 2026-08)

## Titans (architecture to steal from)
| Framework | ★ | Pattern worth taking |
|---|---|---|
| PentestGPT (GreyDGL) | 15.0K | Phase-driven reasoning: recon→enum→exploit loops with task queue |
| HexStrike AI | 11.4K | **Tools exposed as MCP server** → ANY AI client (Claude/GPT/Copilot) can drive 150+ tools. VOIDFORGE v0.3 should expose its registry over MCP |
| GH05TCREW/pentestagent | 3.0K | Black-box testing agent; bug-bounty oriented workflows |
| samugit83/redamon | 2.4K | Agentic red-team automation end-to-end |
| ASCIT31/Dark-Moon | 872 | **Continuous mode**: persistent daemon re-attacking on schedule |
| Gabson0x/pentdem | 80 | Visual **attack-map** output + WAF-bypass engine module |

## Patterns VOIDFORGE adopts
1. Function-calling tool loop (already implemented v0.1)
2. Tool registry as pluggable modules with danger ratings (implemented)
3. NEXT: expose registry as local MCP server → any LLM client drives it
4. NEXT: `--continuous` daemon mode with target watch
5. NEXT: attack-map markdown/graph output per mission
6. Knowledge-base injection into system prompt per-target-class (doctrine-aware planning)

## Gaps in all surveyed frameworks (VOIDFORGE differentiators)
- No Supabase-specific siege doctrine (ours: SUPABASE_SIEGE_PLAYBOOK)
- No Telegram shop-bot taxonomy/war plan (ours: WAR_PLAN_TELEGRAM)
- No HAR-first forensics pipeline (ours: har_dissect/har_tokens)
- No realtime postgres_changes wiretap as first-class tool (ours: realtime_tap)
