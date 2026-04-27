# Orphaned Script Report

Criteria:

- not imported/called by runtime services
- not in `registry/scripts.json`
- not scheduled by known task setup scripts
- not surfaced by command-center endpoints
- writes output with no known consumer

## High-confidence orphan/manual-only candidates


| Script                                                           | Why flagged                                                  | Recommended action                                           |
| ---------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `scripts/personal_ops_worker_ollama_calendar.py`                 | no clear scheduler/endpoint/tool registration                | keep manual-only unless promoted to prepared-context builder |
| `scripts/check_worker_connectivity.py`                           | diagnostics helper; no runtime references                    | keep manual-only; add doc link in runbook                    |
| `scripts/run_trace_sessions.py`                                  | ad-hoc load generator                                        | keep manual-only                                             |
| `scripts/analyze_trace_sessions.py`                              | ad-hoc reporting                                             | keep manual-only                                             |
| `email_sorter/scripts/install_email_sorter_schedule_old_rig.ps1` | host-specific legacy naming and no current wiring references | mark deprecated; archive later                               |


## Growflow orphan/manual-heavy cluster

Observed pattern: many `Growflow/scripts/_probe_*`, `_tmp_*`, `_patch_*`, `_scan_*`, `_check_*`, `_dump_*` scripts with no visible registration in `ai-lab` tool registry and no scheduler installer equivalent.

Examples:

- `Growflow/scripts/_probe_introspection.py`
- `Growflow/scripts/_tmp_query_transfers_db.py`
- `Growflow/scripts/_dump_sheet_formulas.py`
- `Growflow/scripts/_patch_iferror_test.py`

Recommendation:

- keep manual scripts as-is for now, but tag each as one of:
  - `wire into tool registry`
  - `wire into prepared context`
  - `wire into scheduler`
  - `keep manual only`
  - `delete/archive later` (future, explicit approval)

## Duplicate or overlap candidates


| Cluster                                                  | Duplicate risk                                                         | Recommendation                                          |
| -------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------- |
| Prepared-context PS wrappers vs direct task commands     | tasks currently schedule direct python calls, wrappers remain optional | standardize one invocation style                        |
| Multiple personal_ops scripts with overlapping summaries | output overlap and no central consumer map                             | define one canonical personal_ops snapshot source chain |
| Growflow export/report scripts with similar scope        | unclear canonical runner hierarchy                                     | add script ownership + cadence map in Growflow docs     |


## Risk notes

- Orphan scripts are not inherently bad; many are useful diagnostic tools.
- Risk appears when operators assume automation exists but script is manual-only.
- No deletion performed in this audit.

