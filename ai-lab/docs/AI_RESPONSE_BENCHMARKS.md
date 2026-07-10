# AI response benchmarks

## Phase 5 — prepared context selection (Apr 2026)

Prepared-context routing gained a dedicated selector (`brain/prepared_context/selection.py`) with paraphrase families, negative guardrails, and optional multi-snapshot “broad lab” behavior. The benchmark script’s `PROMPTS` list was extended with representative paraphrases. To refresh the **auto-generated snapshot block** in this file (for milestones or committed tables), run from `ai-lab` with `AI_LAB_BENCH_WRITE_DOC=1`. A normal run prints the table to stdout only and does not modify this file.

## How these runs were produced

- **Command** (from `E:/Repos/ai-lab`):  
  `python scripts/benchmark_ai_response.py`  
  Optional: `set AI_LAB_BENCH_WRITE_DOC=1` (Windows) or `AI_LAB_BENCH_WRITE_DOC=1` before the command to rewrite the `<!-- AUTO_BENCHMARK_SNAPSHOT_* -->` section below.
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
| explain repo documentation status | Slow fallthrough (~6.3–6.5s), `prepared_context_used=false`, `fallback=orchestrator_fallback`. | Prepared-context fast path (`repo_pulse` + `system_snapshot`) now responds in ~10–30ms in local runs. |
| what did the last scan find? (no session artifacts) | Catalog in prompt **skipped** insufficient hard-stop → LLM → empty → **fallback**. | **Always** take insufficient hard-stop when fusion says so; catalog appended **inside** that reply instead. |
| check worker health (worker down) | ~13s due sequential HTTP + tunnel probe timeouts. | ~2.2s with 2s interactive budget, parallel probes, and degraded status payload. |

## Quality issues still visible in benchmarks

- **No-LLM UX**: replies prefixed with “local evidence only” still embed the **full** grounded template—readable for engineers, heavy for daily chat. Tracked as a follow-up in `AI_SPEED_AND_USEFULNESS_FIX_PLAN.md`.

<!-- AUTO_BENCHMARK_SNAPSHOT_START -->
## Auto Benchmark Snapshot

Updated: `2026-04-30T00:22:31Z`

| Prompt | First token ms | Total ms | Useful | Wrong refusal | Evidence used | Worker used |
|--------|----------------|----------|--------|---------------|---------------|-------------|
| hello | 31.57 | 33.6 | yes | no | 0 | False |
| what systems are active? | 31.57 | 35.4 | yes | no | 1 | False |
| what changed recently? | 2.28 | 6.0 | yes | no | 1 | False |
| summarize my ai-lab current state | 2149.0 | 2149.0 | yes | no | 0 | False |
| what should I work on today? | 161.17 | 216.0 | yes | no | 1 | False |
| summarize current repo status | 167.15 | 169.8 | yes | no | 3 | False |
| open project agenda | 3.12 | 5.2 | yes | no | 1 | False |
| check worker health | 126.31 | 184.4 | yes | no | 1 | False |
| what is Growflow status? | 9.08 | 65.1 | yes | no | 1 | False |
| what docs need cleanup? | 1426.71 | 1432.1 | yes | no | 1 | False |
| make a docs cleanup plan | 343.23 | 348.6 | yes | no | 1 | False |
| prepare a docs update proposal | 626.97 | 685.2 | yes | no | 1 | False |
| which README needs updating? | 1178.66 | 1184.6 | yes | no | 1 | False |
| what changed recently in Growflow? | 210.02 | 265.9 | yes | no | 1 | False |
| explain repo documentation status | 170.13 | 172.5 | yes | no | 1 | False |
| what is wrong with this README? | 123.7 | 126.5 | yes | no | 1 | False |
| validate repo documentation | 1045.91 | 1051.9 | yes | no | 1 | False |
| what sections are missing in docs? | 852.81 | 860.0 | yes | no | 1 | False |
| improve this repo documentation | 1008.0 | 1010.6 | yes | no | 1 | False |
| anything broken? | 177.79 | 235.0 | yes | no | 3 | False |
| status of the lab | 276.08 | 336.3 | yes | no | 3 | False |
| which repos need cleanup? | 117.49 | 121.2 | yes | no | 2 | False |
| what are my next actions? | 111.65 | 115.8 | yes | no | 1 | False |
| plan my day | 480.99 | 538.7 | yes | no | 1 | False |
| is ollama up on the worker? | 109.29 | 111.7 | yes | no | 1 | False |
| transfer receipt status | 6.18 | 10.7 | yes | no | 4 | False |
| business automation status | 117.76 | 121.8 | yes | no | 4 | False |
| who won the super bowl in 2024? | 901.91 | 906.1 | yes | yes | 0 | False |

_Generated by `scripts/benchmark_ai_response.py`._
<!-- AUTO_BENCHMARK_SNAPSHOT_END -->
