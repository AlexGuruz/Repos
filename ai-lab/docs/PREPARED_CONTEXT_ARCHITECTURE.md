# Prepared Context Architecture

Prepared Context adds a **cached intelligence layer** ahead of retrieval/model calls so common questions can be answered quickly and traceably from prebuilt snapshots.

## Architecture

```mermaid
flowchart TD
  SCH[Scheduled scripts / on-demand refresh] --> BLD[scripts/build_prepared_context.py]
  BLD --> MOD[brain.prepared_context.builders]
  MOD --> STORE[state/prepared_context/*.json]
  STORE --> IDX[state/prepared_context/index.json]

  CHAT[Command Center chat] --> ORCH[brain.orchestrator.main.run]
  ORCH --> LOADER[brain.prepared_context.loader.try_prepared_context_answer]
  LOADER -->|hit| FAST[Prepared response path]
  LOADER -->|miss/low confidence| FALL[Normal routing + retrieval + model]

  API[GET /api/prepared-context] --> STORE
  API2[POST /api/prepared-context/refresh/{snapshot_type}] --> BLD
```

## Snapshot schema

Each snapshot includes:

- `snapshot_type`
- `generated_at`
- `freshness_seconds`
- `source_files_or_tools`
- `confidence`
- `stale`
- `errors`
- `data`
- `summary_short`
- `summary_detailed`
- `suggested_questions`

Validation lives in `brain/prepared_context/schema.py`.

## Snapshot files

Stored under `state/prepared_context/`:

- `system_snapshot.json`
- `repo_pulse.json`
- `project_agenda.json`
- `personal_ops_snapshot.json`
- `growflow_snapshot.json`
- `worker_snapshot.json`
- `index.json`

## Refresh policy

- `worker_snapshot`: every 5–15 minutes or on demand
- `system_snapshot`: every 15 minutes
- `repo_pulse`: every 30–60 minutes
- `project_agenda`: daily + on demand
- `personal_ops_snapshot`: daily + on calendar changes when possible
- `growflow_snapshot`: based on data freshness / export cadence

Refresh tools:

- `python scripts/build_prepared_context.py --snapshot all`
- `python scripts/build_prepared_context.py --snapshot system_snapshot`
- `python scripts/build_prepared_context.py --snapshot repo_pulse`
- `python scripts/build_prepared_context.py --snapshot project_agenda`
- `python scripts/build_prepared_context.py --snapshot personal_ops_snapshot`
- `python scripts/build_prepared_context.py --snapshot growflow_snapshot`
- `python scripts/build_prepared_context.py --snapshot worker_snapshot`

PowerShell wrappers are available in `scripts/refresh_prepared_context_*.ps1`.
Windows scheduler automation helper: `scripts/setup_prepared_context_tasks.ps1` (see `docs/PREPARED_CONTEXT_SCHEDULER_SETUP.md`).
Command Center backend also runs an automatic refresher loop (`services/prepared_context_refresher.py`) on startup.

## Routing behavior

Orchestrator checks prepared context before grounded retrieval/model for common `answer`, `ops_overview`, and `company_bi` turns:

1. If high confidence + present snapshots -> answer immediately from prepared context.
2. If stale -> answer with stale warning + explicit `generated_at`.
3. If missing/insufficient -> fall back to existing retrieval/model path.

No chat turn blocks on rebuild; refresh is on-demand/scheduled via scripts or API.

## Failure modes and stale handling

- Missing snapshot file -> loader miss, normal fallback.
- Invalid schema -> validation errors captured in snapshot `errors`.
- Stale snapshot -> response includes stale warning and refresh command.
- Builder error -> snapshot preserved with degraded confidence and explicit error list.

Prepared context never claims fresh state without exposing `generated_at`.

## Trace integration

When prepared context is used, response trace includes:

- `prepared_context_used`
- `snapshot_types_used`
- `snapshot_generated_at`
- `snapshot_stale`
- `context_load_ms`
- `avoided_retrieval`
- `avoided_worker_call`
- `final_answer_source`

## Benchmark targets

- Prepared-context answers: under 1.5s total
- Prepared-context + model polish: under 3s
- No worker call unless required
- No retrieval unless prepared context missing/insufficient

## Future expansion

- Replace heuristic project agenda with task/calendar connectors.
- Add repo pulse integration with repo-index coordinator metadata.
- Add confidence scoring per field (not just per snapshot).
- Add partial snapshot diffs for “what changed since last refresh?”.

