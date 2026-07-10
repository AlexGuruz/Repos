# AI speed & usefulness fix plan (summary)

This closes the audit loop: **bottlenecks**, **quality issues**, **files touched**, **benchmarks**, and **safe next steps**.

## Worker probe paths identified

- `brain/orchestrator/main.py` → `intent == "worker_health"` branch (chat/orchestrator interactive checks).
- `brain/worker_health.py` → `check_worker_assistant`, `check_worker_n8n`, `check_worker_ollama`, and `get_worker_health_snapshot`.
- `brain/worker_tunnel.py` → local tunnel reachability checks for expected ports.
- `command-center/command-center/backend/routers/workers.py` → `/api/workers/health` and `/api/workers/health/{worker_name}`.

## Top 5 bottlenecks

1. **Worker health SSH/TCP** (was ~10–13s when worker unreachable, now ~2.2s in interactive checks) — `main.py` worker branch, `worker_health.py`, `worker_tunnel.py`, command-center workers API.
2. **Common Q&A doing runtime retrieval/model work** — mitigated by new Prepared Context snapshots and orchestrator pre-check path (`brain/prepared_context/*`, `main.py`).
3. **LLM TTFT + completion** — LAN latency + model size; reduce prompt size and skip `/models` probe when possible (`AI_LAB_LLM_SKIP_MODEL_LIST_PROBE`).
4. **Large grounded prompts** — ops registry + README + catalog in one user message (`build_grounded_response` + `grounded_prompt.txt`).
5. **Web search** (when triggered) — bounded but still slower than pure local; freshness heuristics in `freshness.py` aim to avoid spurious web.

## Top 5 quality issues (addressed or tracked)

1. **Generic `[Orchestrator]` fallback** when LLM empty — mitigated by insufficient-evidence hard-stop fix + no-LLM key-evidence detection fix (`main.py`).
2. **False “insufficient evidence” / wrong gating** — catalog-in-block skipped hard-stop (**fixed**); `(none)` substring false negative (**fixed**).
3. **“What should I work on today?” under no-LLM** — now surfaces ops-backed evidence instead of dead-ending (**fixed** substring logic).
4. **“Repo documentation status” without artifact** — **fixed** via `routing_policy` doc+repo README fast path.
5. **No-LLM UX still engineer-oriented** — user sees full grounded template; **tracked** (formatter recommendation in `AI_MODEL_USEFULNESS_AUDIT.md`).

## Files changed (this audit cycle)

| File | Change |
|------|--------|
| `brain/orchestrator/main.py` | Insufficient-evidence stop always when fusion says so; no-LLM evidence reply uses precise `Key Evidence` empty check; worker-health branch now uses 2s interactive budget and degraded status fields. |
| `brain/orchestrator/routing_policy.py` | Doc+repo README fast path. |
| `brain/worker_health.py` | Parallel worker service probes with hard interactive timeout budget, status caching, timestamped snapshot, degraded/offline status metadata. |
| `brain/worker_tunnel.py` | Parallel local tunnel port checks with configurable per-port and total timeouts. |
| `command-center/command-center/backend/routers/workers.py` | Worker health API now uses interactive 2s budget snapshot path. |
| `brain/prepared_context/schema.py` | Snapshot schema + validation for prepared context records. |
| `brain/prepared_context/store.py` | Snapshot persistence in `state/prepared_context/` + index. |
| `brain/prepared_context/builders.py` | Builders for system/repo/agenda/personal_ops/growflow/worker snapshots. |
| `brain/prepared_context/loader.py` | Prepared-context selection and answer path decision logic. |
| `command-center/command-center/backend/routers/prepared_context.py` | API visibility + refresh endpoints for prepared context. |
| `scripts/build_prepared_context.py` | CLI refresh job for all or specific snapshot types. |
| `tests/test_integration_flows.py` | Random `session_id` for insufficient test; assertion avoids accepting fallback; non-worker questions do not probe worker health. |
| `tests/test_routing_policy.py` | New test for doc/repo README path. |
| `tests/test_worker_health.py` | Added budget-latency and last-known-status coverage for worker-down behavior. |
| `tests/test_prepared_context.py` | Schema/staleness/fallback/orchestrator trace coverage for prepared context. |

*(Earlier session work—already in repo—includes `response_trace.py`, `chat.py` trace args, `evidence_fusion.py`, `source_router.py`, `router.py`, `llm_client.py`, `.gitignore` for traces, `scripts/benchmark_ai_response.py`.)*

## Before / after benchmark table (no-LLM script)

Approximate **before** state refers to the broken behaviors described in `AI_RESPONSE_BENCHMARKS.md` (fallback / insufficient on specific prompts). **After** numbers from `python scripts/benchmark_ai_response.py` on 2026-04-26 (same machine; worker row reflects the 2s interactive budget path).

| Prompt | Before (issue) | After total ms | After quality |
|--------|----------------|----------------|----------------|
| hello | OK | ~259 | Greeting short-circuit |
| what systems are active? | Sometimes fallback | ~514 | Ops markdown |
| summarize my ai-lab current state | OK / heavy | ~709 | Catalog-heavy |
| what should I work on today? | Orchestrator fallback | ~187 | Ops + evidence-only |
| check worker health | Slow if down (~13s) | ~2203 | Degraded status within interactive timeout budget |
| what changed recently in Growflow? | Fallback | ~362 | README evidence |
| explain repo documentation status | Insufficient | ~877 | README evidence |

## Remaining recommended changes (safe, incremental)

1. **Prepared context scheduler wiring**: attach `scripts/refresh_prepared_context_*.ps1` to OS task scheduler cadence.
2. **Compact prompt mode** for chat: shrink `_format_evidence` caps via env (`AI_LAB_CHAT_EVIDENCE_CHAR_CAP`).
3. **No-LLM friendly formatter**: short markdown summary instead of raw `grounded_prompt.txt` body.
4. **Frontend timing**: log `performance.now()` delta to first SSE `delta` in `ChatPanel.jsx` and optionally POST to a dev-only endpoint (later).
5. **Trace coverage**: ensure every early `return` in `run()` calls `_write_turn_trace_if_enabled` with consistent `final_answer_type`.

## Safe next steps

- Run **`pytest tests/test_integration_flows.py tests/test_routing_policy.py tests/test_fusion.py`** before merges.
- Run **`python scripts/benchmark_ai_response.py`** after routing changes.
- For production chat, keep **`write_response_trace=True`** temporarily during tuning; traces live under `state/` (gitignored).
- **Do not** remove approval gates for risky proposals; any worker change should be **timeout-only** or **presentation-only** first.
