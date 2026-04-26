# AI routing policy (fast paths and safety)

This policy describes **how user messages should be routed** for speed and usefulness. It aligns with code in `brain/router/router.py`, `brain/orchestrator/source_router.py`, `brain/orchestrator/routing_policy.py`, and early branches in `brain/orchestrator/main.py`.

## Principles

1. **Local-first**: prefer registry, session artifacts, and on-disk README summaries before paid web search.
2. **No surprise web**: short planning / “today” questions must not open Tavily/Serper unless the user clearly asks for external current facts.
3. **Greetings are not retrieval tasks**: allowlisted openers return immediately from `main.run()` without evidence or LLM.
4. **Risky execution stays approval-gated**: this document does **not** relax approval rules for destructive or privileged actions.

## Route table (intent / behavior)

| User need | Intent / path | Retrieval | Worker | Implementation pointers |
|-----------|---------------|-----------|--------|-------------------------|
| Greetings / small talk / help openers | Early return in `main.run()` | **No** | **No** | `_load_conversational_openers`, `_is_short_social_greeting`, `normalize_chat_text`. |
| Simple “what’s active / systems / workers” | `ops_overview` | Ops registry only | **No** | `router.classify_intent` + deterministic block in `main.run()` using `ops_registry.get_ops_summary_text_cached()`. |
| Planning / prioritization (“what should I work on”, backlog, etc.) | `answer` + fast path | **Ops registry** (no web) | **No** | `routing_policy.match_answer_fast_path` → `source_router` applies `AnswerFastPath`. |
| Lab / Command Center “current state” | `answer` + fast path | Ops + optional `ai-lab/README.md` | **No** | Same; README when path exists. |
| Repo documentation **status** (doc + repo wording) | `answer` + fast path | `ai-lab/README.md` artifact | **No** | `routing_policy` doc+repo markers. |
| Growflow “what changed / recent” (local README) | `answer` + fast path | `Growflow/README.md` when present | **No** | `routing_policy` growflow + change markers. |
| Repo file / script questions | `repo_search` / `run_agent` | Repo index / cartographer | **Optional worker** | `router` + execution (`brain/execution.py`); worker index/retrieve intents per `router.py`. |
| Heavy summarization over large corpora | `answer` or agent-specific | Evidence + LLM and/or **worker** | **Yes** when configured | Prefer worker when index is large; keep timeouts (see fix plan). |
| Code / doc cleanup that mutates state | Proposals + approvals | As needed | As needed | `proposal_engine`, `approval_queue` — **approval gates stay on** for risky tools. |
| Calendar / personal ops | Tooling scripts / future intent hooks | Configured calendars | **No** unless script uses worker | Outside core chat path today; use `ai-lab/scripts/personal_ops_*.py` and env config. |
| Growflow POS / business facts | `run` (`growflow_sales_today`, etc.) or `company_bi` | BI summary artifact / tools | **No** by default | `router` Growflow hooks + `source_router` `company_bi` local target. |
| Customer messaging / outbound comms | Not auto-routed without governance | N/A | N/A | Requires explicit product “consent validator” workflow — **do not** bypass in chat router. |

## Timeouts and fallbacks (policy-level)

- **Web search**: bounded timeout in `web_tool` / `evidence_loader` (e.g. POST timeout passed through); avoid chaining multiple queries for casual chat.
- **Worker / SSH**: treat slow worker as **degraded** state; surface partial health and avoid blocking the whole orchestrator longer than a configured budget (recommended follow-up).
- **LLM unreachable**: with `AI_LAB_ORCH_NO_LLM=1` or empty base URL, prefer **deterministic** intent handlers (`ops_overview`, catalog substitution where implemented) and **evidence-only** answers when key evidence exists—not the generic `[Orchestrator]` string.

## Trace field: `route_chosen`

Structured traces (`state/ai_response_traces.jsonl`) use `route_chosen` (e.g. `greeting_shortcircuit`, `ops_overview`, intent name from `classify_intent`) for analytics—see `main._write_turn_trace_if_enabled` and `response_trace.append_response_trace`.
