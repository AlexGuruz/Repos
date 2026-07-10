# AI Lab Integration Health Summary

## Top 10 wired and working systems

1. Chat SSE pipeline (`ChatPanel` -> `/api/chat/stream` -> orchestrator).
2. Intent classification and early-path handling.
3. Prepared context build/store/load flow.
4. Prepared context backend refresher loop with status endpoint.
5. Prepared context top-bar health badge + diagnostics popover.
6. Worker health bounded checks (2s interactive budget).
7. Worker tunnel status checking.
8. Approval queue persistence and resolve APIs.
9. Repo watcher -> repo index coordinator dirty/build loop.
10. Structured response tracing (`state/ai_response_traces.jsonl`).

## Top 10 partial systems

1. Approval enforcement at execution boundary (`execution.run` not gate-enforced).
2. Supervisor bridge vs orchestrator direct execution policy parity.
3. Personal ops snapshot depth/content quality.
4. Prepared context phrase matching robustness.
5. Stale status consistency between snapshot reads and index rows.
6. n8n trigger endpoint assumptions.
7. Growflow script fleet central trigger ownership.
8. Tool metadata override path (`ops/registry/tools.yaml`) not actively used.
9. Last-run visibility for OS-level scheduled tasks in UI.
10. Unified inventory/orphan automation.

## Top 10 orphan/manual-heavy scripts/tools

1. `scripts/personal_ops_worker_ollama_calendar.py`
2. `scripts/check_worker_connectivity.py`
3. `scripts/run_trace_sessions.py`
4. `scripts/analyze_trace_sessions.py`
5. `email_sorter/scripts/install_email_sorter_schedule_old_rig.ps1`
6. `Growflow/scripts/_probe_introspection.py`
7. `Growflow/scripts/_tmp_query_transfers_db.py`
8. `Growflow/scripts/_dump_sheet_formulas.py`
9. `Growflow/scripts/_patch_iferror_test.py`
10. `Growflow/scripts/_scan_package_names.py`

## Top 10 missing triggers

1. Personal ops canonical scheduled refresh chain.
2. Automated orphan inventory generation cadence.
3. Growflow canonical scheduler map for script subsets.
4. Task Scheduler run-state ingestion into Command Center.
5. Runtime check for stale/deprecated old-rig task scripts.
6. Continuous verification for registry path existence.
7. Cross-lane approval parity check (orchestrator vs supervisor).
8. Prepared-context semantic routing fallback trigger tuning.
9. End-to-end n8n trigger health validation trigger.
10. Unified "integration health" endpoint for all subsystems.

## Highest-risk gaps

- Approval policy can be bypassed by direct execution wrapper calls.
- Split execution lanes create inconsistent behavior under approvals.
- Snapshot stale signals can diverge in UI vs loader truth.

## Fastest fixes

- Add execution-boundary approval assertion before running registry scripts.
- Recompute stale flags when serving prepared-context index.
- Add nightly inventory validation test for scripts/registry/schedulers.

## Recommended implementation order

1. Approval boundary hardening.
2. Prepared-context stale/index consistency.
3. Trigger visibility for scheduled tasks.
4. Personal ops canonical data source + cadence.
5. Growflow canonical runner registry and ownership map.