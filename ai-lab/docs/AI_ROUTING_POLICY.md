# AI routing policy (fast paths and safety)

This policy describes **how user messages should be routed** for speed and usefulness. It aligns with code in `brain/router/router.py`, `brain/orchestrator/source_router.py`, `brain/orchestrator/routing_policy.py`, and early branches in `brain/orchestrator/main.py`.

## Prepared Context First

- Common system/repo/planning/business questions should first consult prepared snapshots via `brain.prepared_context.loader`.
- Snapshot **choice** is hybrid keyword + intent scoring in `brain.prepared_context.selection` (fast, deterministic). See `docs/PREPARED_CONTEXT_SELECTION_HARDENING.md`.
- If snapshots are high-confidence, answer immediately from prepared context.
- If snapshots are stale, answer with a stale warning and `generated_at`; do not fake freshness.
- If snapshots are missing/insufficient, fall back to normal retrieval/model flow.
- Do not block chat while rebuilding snapshots (refresh via scripts or API).

## Principles

1. **Local-first**: prefer registry, session artifacts, and on-disk README summaries before paid web search.
2. **No surprise web**: short planning / “today” questions must not open Tavily/Serper unless the user clearly asks for external current facts.
3. **Greetings are not retrieval tasks**: allowlisted openers return immediately from `main.run()` without evidence or LLM.
4. **Risky execution stays approval-gated**: this document does **not** relax approval rules for destructive or privileged actions.

## Route table (intent / behavior)

| User need | Intent / path | Retrieval | Worker | Implementation pointers |
|-----------|---------------|-----------|--------|-------------------------|
| Greetings / small talk / help openers | Early return in `main.run()` | **No** | **No** | `_load_conversational_openers`, `_is_short_social_greeting`, `normalize_chat_text`. |
| Common system/repo/planning questions | `prepared_context` pre-check | **Usually No** | **No** | `brain.prepared_context.loader.try_prepared_context_answer`. |
| Simple “what’s active / systems / workers” | `ops_overview` | Ops registry only | **No** | `router.classify_intent` + deterministic block in `main.run()` using `ops_registry.get_ops_summary_text_cached()`. |
| Planning / prioritization (“what should I work on”, backlog, etc.) | `answer` + fast path | **Ops registry** (no web) | **No** | `routing_policy.match_answer_fast_path` → `source_router` applies `AnswerFastPath`. |
| Lab / Command Center “current state” | `answer` + fast path | Ops + optional `ai-lab/README.md` | **No** | Same; README when path exists. |
| Repo documentation **status** (doc + repo wording) | `answer` + fast path | `ai-lab/README.md` artifact | **No** | `routing_policy` doc+repo markers. |
| Repo docs maintainer status/plan/proposal | `docs_status` / `docs_cleanup_plan` / `docs_update_proposal` | Prepared context (`repo_pulse`) | **No** (normal path) | `brain/repo_docs_maintainer.py` + orchestrator approval queue integration. |
| Repo documentation **score / grade** (single repo on disk) | `repo_docs_score` | Local README + bounded `docs/**/*.md` + `repo_pulse` row when path matches | **No** | `brain/repo_docs_repo_level.py` → `assess_repo_documentation`; resolve repo from message (`router.py`). |
| Repo documentation **consistency** (links, paths, duplicates) | `repo_docs_consistency` | Same bounded local scan | **No** | `check_repo_docs_consistency`. |
| Repo documentation **multi-file workplan** | `repo_docs_workplan` | Assessment + consistency → ordered tasks | **No** | `build_repo_docs_workplan`. |
| Repo documentation **batch proposal** (multi-file, approval-gated) | `repo_docs_batch_proposal` | Workplan-derived targets; **one** `ApprovalSpec` today | **No** | `create_repo_docs_batch_proposal` + orchestrator `submit()` — see follow-up below. |
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

Prepared-context usage is also traced via:

- `prepared_context_used`
- `snapshot_types_used`
- `snapshot_generated_at`
- `snapshot_stale`
- `context_load_ms`
- `avoided_retrieval`
- `avoided_worker_call`
- `final_answer_source`

## Repo documentation maintainer — Phase 8+ follow-ups

- **Batch approvals today:** `repo_docs_batch_proposal` enqueues a single approval card using a **primary** `file_path` and a **truncated JSON summary** in `diff_preview`. That is intentional for this phase and acceptable operationally.
- **Future improvement:** **multi-file approval UI** with **per-file cards** (one row per affected path, expandable rationale, optional per-file approve/deny or grouped approve with file checklist). Until that exists, reviewers should read `diff_preview` and the chat reply’s `target_files` list before approving.
