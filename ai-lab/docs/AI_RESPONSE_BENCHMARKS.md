# AI response benchmarks

## How these runs were produced

- **Command** (from `E:/Repos/ai-lab`):  
  `python scripts/benchmark_ai_response.py`
- **Environment**: `AI_LAB_ORCH_NO_LLM=1`, `AI_LAB_LLM_SKIP_MODEL_LIST_PROBE=1`, and `run(..., llm_base_url="", llm_model="")` so **no LM Studio** traffic is measured—only orchestrator, routing, evidence, and local branches (including worker health SSH when that prompt runs).
- **Heuristic “route” column**: derived in the script from reply shape (`_route_from_reply` in `scripts/benchmark_ai_response.py`); it is **not** the same as `route_chosen` in JSONL traces.
- **First-token latency**: not captured by this script; enable `write_response_trace=True` (default in `run()` for production chat) and inspect `state/ai_response_traces.jsonl` after Command Center traffic.

## Latest run (representative)

Captured on the same machine as development (Windows); worker health now uses a strict 2s interactive budget with parallel probes and cached last-known status.

| Prompt | Total ms | Route (heuristic) | Quality / notes |
|--------|----------|-------------------|-----------------|
| hello | 258.6 | greeting_shortcircuit | Fast, on-policy greeting. |
| what systems are active? | 514.1 | ops_evidence_or_summary | Deterministic ops registry markdown. |
| summarize my ai-lab current state | 709.1 | answer_path | Catalog substitution / grounding path; heavier string work. |
| what should I work on today? | 187.2 | ops_evidence_or_summary | Ops-backed planning fast path; with no LLM, evidence-only preamble + grounded block. |
| check worker health | 2202.6 | worker_health | Degraded response under hard timeout budget, with `worker_status`, `checked_at`, `timeout_budget_ms`, and `last_known_status`. |
| what changed recently in Growflow? | 361.7 | answer_path | README artifact fast path when `E:/Repos/Growflow/README.md` exists. |
| explain repo documentation status | 877.0 | answer_path | README fast path (`routing_policy` doc+repo branch); no longer hard “insufficient evidence” when README present. |

### Raw script output (copy of last run)

```
# AI response benchmarks (local, no LLM)

Environment: `AI_LAB_ORCH_NO_LLM=1`, `AI_LAB_LLM_SKIP_MODEL_LIST_PROBE=1`, empty `llm_base_url` in `run()`.
This measures **orchestrator + routing + evidence** latency without LM Studio.

| Prompt | Total ms | Route (heuristic) | Reply preview |
|--------|----------|-------------------|---------------|
| hello | 258.6 | greeting_shortcircuit | Ready. Active topic: **(none)**. What do you want to work on? |
| what systems are active? | 514.1 | ops_evidence_or_summary | ### Operations registry (systems / workers / automations)  # Operations registry summary  ## Systems - **ai-lab**: Comma… |
| summarize my ai-lab current state | 709.1 | answer_path | From the **lab system catalog** (authoritative):  ### Catalog: `ai-lab` (AI Lab workspace) - **lifecycle_state**: partia… |
| what should I work on today? | 187.2 | ops_evidence_or_summary | _No LLM configured (`LLM_BASE_URL` empty or `AI_LAB_ORCH_NO_LLM=1`) — **local evidence only**:_  You are a system assist… |
| check worker health | 2202.6 | worker_health | Worker **worker-rig-01** is unreachable/degraded for interactive budget checks. - `worker_status`: `offline_or_unreachable` … |
| what changed recently in Growflow? | 361.7 | answer_path | _No LLM configured (`LLM_BASE_URL` empty or `AI_LAB_ORCH_NO_LLM=1`) — **local evidence only**:_  You are a system assist… |
| explain repo documentation status | 877.0 | answer_path | _No LLM configured (`LLM_BASE_URL` empty or `AI_LAB_ORCH_NO_LLM=1`) — **local evidence only**:_  You are a system assist… |

For **first-token** and **per-stage** timings, see `state/ai_response_traces.jsonl` with `write_response_trace=True` (Command Center chat).
```

## Before / after (selected regressions fixed in this audit cycle)

| Prompt | Before (symptom) | After (this cycle) |
|--------|------------------|---------------------|
| what should I work on today? | Often **`[Orchestrator]`** fallback under no-LLM: grounded block contained `Active Topic: (none)` and the substring test treated `(none)` as “no key evidence”. | **Ops + evidence-only** path; substring check narrowed to `\nKey Evidence:\n(none)`. |
| explain repo documentation status | **`insufficient_evidence`** despite repo doc intent (internal keywords without artifact). | **`routing_policy`** doc+repo fast path loads **ai-lab README** as artifact. |
| what did the last scan find? (no session artifacts) | Catalog in prompt **skipped** insufficient hard-stop → LLM → empty → **fallback**. | **Always** take insufficient hard-stop when fusion says so; catalog appended **inside** that reply instead. |
| check worker health (worker down) | ~13s due sequential HTTP + tunnel probe timeouts. | ~2.2s with 2s interactive budget, parallel probes, and degraded status payload. |

## Quality issues still visible in benchmarks

- **No-LLM UX**: replies prefixed with “local evidence only” still embed the **full** grounded template—readable for engineers, heavy for daily chat. Tracked as a follow-up in `AI_SPEED_AND_USEFULNESS_FIX_PLAN.md`.
