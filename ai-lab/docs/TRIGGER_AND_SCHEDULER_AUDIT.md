# Trigger and Scheduler Audit

## Backend runtime triggers (actual)

| Trigger | Expected | Actual wiring | Interval | Last run tracking | Failure visibility | Output consumed? | Command Center status |
|---|---|---|---|---|---|---|---|
| Nvidia poller | collect hardware telemetry | `backend/main.py` starts `nvidia_poll_loop()` | loop internal | telemetry/event logs | yes (logs + feed) | yes (Compute/Diagnostics) | partial |
| Repo watcher | detect file changes, mark repo dirty | `backend/main.py` -> `repo_watcher.start_watcher`; `repo_watcher.py` publishes + `mark_dirty` | event-driven | watcher events + coordinator state | partial | yes (repo index coordinator) | yes (`/api/repo/index_state`) |
| Repo index coordinator | rebuild/promote staged indexes | `backend/main.py` -> `get_coordinator().run_forever()` | ~0.5s tick | persisted state `backend/state/repo_index_state.json` | yes (`repo_index_build_failed`) | yes | yes (`/api/repo/index_state`) |
| Prepared context refresher | keep snapshots warm | `backend/main.py` -> `run_prepared_context_refresher()` | per policy (10m/15m/45m/60m/daily) | `last_runs` in refresher status endpoint | yes (`startup_error`, run errors) | yes (orchestrator + UI) | yes (`/api/prepared-context/status/refresher`) |

## Scripted scheduler triggers (Windows)

| Script | Expected trigger | Actual trigger wiring | Interval | Output consumed | Status |
|---|---|---|---|---|---|
| `scripts/setup_prepared_context_tasks.ps1` | create all prepared-context tasks | `schtasks /Create` entries for all snapshot types | 10m/15m/45m/60m/daily | snapshots/index consumed by orchestrator/UI | wired |
| `scripts/remove_prepared_context_tasks.ps1` | delete prepared-context tasks | `schtasks /Delete` for all named tasks | on demand | N/A | wired |
| `scripts/setup_worker_tunnel_task.ps1` | keep worker tunnel task installed | scheduled task setup | startup/periodic (script policy) | worker bridge + health checks | wired |
| `scripts/maintain_worker_tunnel.ps1` | restart/check tunnel | loop logic in script | script-defined | worker requests/health | wired |
| `scripts/start_worker_tunnel.ps1` | manual trigger | manual | on demand | worker requests/health | manual |

## Personal ops triggers

| Component | Expected | Actual | Output consumed? | Status |
|---|---|---|---|---|
| `scripts/personal_ops_calendar_snapshot.py` | calendar snapshot refresh | manual/script callable; no backend auto trigger | partially (prepared snapshot script availability) | partial |
| `scripts/personal_ops_daily_digest.py` | daily digest | manual/script callable | partial | partial |
| `scripts/personal_ops_repo_pulse.py` | personal repo pulse | manual/script callable | partial | partial |
| `scripts/personal_ops_worker_ollama_calendar.py` | combined worker+calendar ops | manual/script callable | no direct runtime consumer | partial |

## Growflow/dashboard trigger assumptions

| Area | Expected | Actual | Output consumed? | Status |
|---|---|---|---|---|
| Growflow export jobs (`Growflow/scripts/*.py`) | scheduled business automation | many scripts exist; only a few PS wrappers seen (`run_sales_today.ps1`, etc.) | some consumed by prepared `growflow_snapshot` via local files | partial |
| Company BI scripts (`Growflow/company_bi/scripts/*.py`) | recurring aggregation | scripts exist; schedule mostly external/manual | indirectly via `METRICS.md` in prepared context | partial |

## n8n trigger path

- Intent path: `router.py` -> `trigger_workflow` -> orchestrator proposal -> `execute_proposal` calls `worker_n8n_trigger`.
- Worker bridge also has controlled-op semantics for approvals, but orchestrator direct proposal execution is a separate lane.
- Risk: policy drift between orchestrator-direct and supervisor-bridge controlled execution.

## Gaps

- Last-run metadata for Windows `schtasks` is not yet surfaced in Command Center (only refresher in-process status is shown).
- Personal ops scripts are present but not universally scheduled/wired as durable triggers.
- Growflow script fleet is large; canonical scheduled subset is not centrally declared in ai-lab.

