# Prepared context selection hardening (Phase 5)

## Purpose

Snapshot choice for prepared-context answers moved from a short list of substring checks in `loader.py` to a **deterministic hybrid selector** in `brain/prepared_context/selection.py`. The goal is **paraphrase resilience** and **negative filtering** (wrong domain) while keeping **sub‑10ms** selection time, **no embeddings**, and unchanged **quality gate**, **stale warnings**, and **no worker calls** on the prepared-context answer path.

## How to run / tune

- Selection API: `select_snapshots_for_message(message, intent=None)` → `SnapshotSelection` (`snapshot_types`, `scores`, `reasons`, `rejected_candidates`, `broad_prompt`, `time_sensitive`, `selection_ms`).
- Loader: `try_prepared_context_answer` invokes the selector, then loads snapshots in the returned order.
- Adjust behavior by editing weighted hints and guardrails in `selection.py` (keyword families, intent boosts, reject rules).

## Strategy (summary)

| Mechanism | Role |
|-----------|------|
| Weighted phrase hints | Per-snapshot family scores (`system_snapshot`, `repo_pulse`, …). |
| Intent boosts | `company_bi` → growflow; `ops_overview` → system; `worker_health` → worker snapshot. |
| Reject / guardrails | Block `growflow_snapshot` for generic “inventory” without Growflow/business anchors; block `personal_ops_snapshot` for generic “work” without planning/calendar markers; require worker/ollama/n8n/tunnel anchor for `worker_snapshot`. |
| Broad lab prompts | When the message is a vague lab/status overview (and not doc/repo‑maintenance), boost the trio `system_snapshot` + `repo_pulse` + `project_agenda`. |
| Doc/repo maintenance | When documentation/repo cleanup language is present with a strong `repo_pulse` score, **pair** `system_snapshot` and **suppress** the broad trio (preserves legacy two‑snapshot answers and avoids tripping the “missing snapshot” early exit). |
| Trivia / general knowledge | Phrases like “who won …” clear all snapshot scores so prepared context is not forced. |

## Trace fields

When response tracing is enabled, additional fields may appear on prepared-context turns:

- `prepared_context_selection_scores`
- `prepared_context_selection_reasons`
- `prepared_context_selection_ms`

## Worker health path

For `intent == worker_health`, the orchestrator **tries prepared context first** (cached `worker_snapshot`). If that yields a reply, **live worker probes are skipped** for that turn (`avoided_worker_call: true` in the trace). If no cached snapshot answer is produced, behavior falls back to the existing interactive worker health check.

## Cadence

Re-run `tests/test_prepared_context_selection.py` after changing hints. Optionally extend `scripts/benchmark_ai_response.py` prompts; regenerate `docs/AI_RESPONSE_BENCHMARKS.md` only when committing a milestone snapshot (`AI_LAB_BENCH_WRITE_DOC=1`).

## Hard rules (unchanged)

- Quality gate and stale handling stay in `loader._quality_gate` / reply shaping.
- No customer alerts, no file organizer, no tool auto-registration, no approval weakening.
