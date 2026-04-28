# Script and Tool Inventory

See also: auto-generated drift inventory (`docs/SCRIPT_TOOL_INVENTORY_AUTO.md`, run `python scripts/generate_integration_inventory.py`).

Method: path scan + reference scan across `ai-lab`, `command-center`, and `Growflow` plus registry and router/orchestrator wiring.

Status legend: `wired` / `partial` / `orphan` / `deprecated` / `risky`.

## A) ai-lab scripts

| Script/file | Purpose | Called by what | Registered tool? | Exposed in Command Center? | Scheduled? | Approval-gated? | Writes state/files? | Last known output path | Status |
|---|---|---|---|---|---|---|---|---|---|
| `scripts/build_prepared_context.py` | build snapshots/index | manual, task scripts, refresher parity | no | indirect via prepared endpoints | yes (optional tasks) | no | yes (`state/prepared_context`) | `state/prepared_context/*.json` | wired |
| `scripts/setup_prepared_context_tasks.ps1` | install scheduled refresh tasks | manual operator run | no | no | N/A (creates tasks) | no | no | task scheduler entries | wired |
| `scripts/remove_prepared_context_tasks.ps1` | remove refresh tasks | manual operator run | no | no | N/A | no | no | scheduler cleanup | wired |
| `scripts/refresh_prepared_context_all.ps1` | manual one-shot refresh | manual/task wrappers | no | no | optional | no | yes | `state/prepared_context` | partial |
| `scripts/refresh_prepared_context_system.ps1` | refresh one snapshot | manual/task wrappers | no | no | optional | no | yes | snapshot json | partial |
| `scripts/refresh_prepared_context_worker.ps1` | refresh worker snapshot | manual/task wrappers | no | no | optional | no | yes | snapshot json | partial |
| `scripts/refresh_prepared_context_repo_pulse.ps1` | refresh repo pulse | manual/task wrappers | no | no | optional | no | yes | snapshot json | partial |
| `scripts/refresh_prepared_context_project_agenda.ps1` | refresh project agenda | manual/task wrappers | no | no | optional | no | yes | snapshot json | partial |
| `scripts/refresh_prepared_context_personal_ops.ps1` | refresh personal ops | manual/task wrappers | no | no | optional | no | yes | snapshot json | partial |
| `scripts/refresh_prepared_context_growflow.ps1` | refresh growflow | manual/task wrappers | no | no | optional | no | yes | snapshot json | partial |
| `scripts/setup_worker_tunnel_task.ps1` | install worker tunnel task | manual operator run | no | no | yes (creates task) | no | no | scheduler entry | wired |
| `scripts/maintain_worker_tunnel.ps1` | keep ssh tunnel alive | scheduled task/manual | no | indirect (worker status visible) | yes | no | no | tunnel process/log output | wired |
| `scripts/start_worker_tunnel.ps1` | start tunnel manually | manual | no | indirect | no | no | no | tunnel startup output | manual |
| `scripts/check_worker_connectivity.py` | connectivity diagnostics | manual | no | no | no | no | no | stdout only | manual |
| `scripts/benchmark_ai_response.py` | benchmark latency/usefulness | manual/CI-like audit | no | no | no | no | yes (doc update) | `docs/AI_RESPONSE_BENCHMARKS.md` | wired |
| `scripts/run_trace_sessions.py` | generate live traces | manual | no | no | no | no | yes | `state/ai_response_traces.jsonl` | partial |
| `scripts/analyze_trace_sessions.py` | analyze traces | manual | no | no | no | no | no | stdout summary | partial |
| `scripts/personal_ops_calendar_snapshot.py` | personal ops data pull | manual | no | indirectly via prepared snapshot | no | no | likely yes | script-defined outputs | partial |
| `scripts/personal_ops_daily_digest.py` | daily digest | manual | no | no | no | no | likely yes | script-defined outputs | partial |
| `scripts/personal_ops_repo_pulse.py` | repo pulse for personal ops | manual | no | indirect | no | no | likely yes | script-defined outputs | partial |
| `scripts/personal_ops_worker_ollama_calendar.py` | combined personal ops/worker flow | manual | no | no | no | no | likely yes | script-defined outputs | orphan |
| `scripts/repo_full_rebuild_gate_a.py` | approval gate script for rebuild | registry entry | yes (`registry/scripts.json`) | indirectly via approvals/execution | on-demand | yes | yes | execution logs + worker side effects | wired |
| `scripts/repo_policy_migration_gate_c.py` | approval gate C migration rebuild | registry entry | yes | indirectly | on-demand | yes | yes | execution logs + worker side effects | wired |

## B) command-center scripts

| Script/file | Purpose | Called by what | Registered tool? | Exposed in Command Center? | Scheduled? | Approval-gated? | Writes state/files? | Status |
|---|---|---|---|---|---|---|---|---|
| `command-center/scripts/start.ps1` | dev start wrapper | manual | no | no | no | no | no | manual |
| `command-center/scripts/start-background.ps1` | background startup | manual | no | no | no | no | yes (process state/logs) | manual |
| `command-center/scripts/stop.ps1` | stop services | manual | no | no | no | no | no | manual |
| `command-center/scripts/restart.ps1` | restart services | manual | no | no | no | no | no | manual |
| `command-center/scripts/run-backend.ps1` | backend runner | manual | no | no | no | no | no | manual |
| `command-center/scripts/deps.ps1` | dependency install/bootstrap | manual | no | no | no | no | yes | manual |
| `command-center/scripts/bootstrap.ps1` | local setup | manual | no | no | no | no | yes | manual |

## C) Growflow scripts (discovered set)

- Discovered `65` python scripts under `Growflow/scripts` + `Growflow/company_bi/scripts`.
- Discovered `3` PowerShell wrappers in `Growflow/scripts`: `run_sales_today.ps1`, `run_stock_pool_allocation.ps1`, `run_export_dashboard_layout.ps1`.
- High-confidence wired to ai-lab runtime today: **minimal/direct-none** except through:
  - `registry/scripts.json` entry `growflow_sales_today` (`integrations/growflow/sales_today.py`)
  - prepared context `growflow_snapshot` reading local operational artifacts.
- Most underscore-prefixed scripts (`_probe_*`, `_tmp_*`, `_patch_*`, `_scan_*`) are likely manual diagnostics or migration helpers; classify as `orphan/manual` pending explicit scheduler or registry references.

## D) Evidence pointers

- Registry: `registry/scripts.json`, `brain/execution.py`
- Approval gate: `brain/orchestrator/approval_gate.py`, `brain/permanent_allowlist.py`
- Prepared context consumers: `brain/prepared_context/*`, `command-center/backend/routers/prepared_context.py`, `frontend/src/App.jsx`, `frontend/src/components/ToolsPanel.jsx`
- Scheduler scripts: `scripts/setup_prepared_context_tasks.ps1`, `scripts/setup_worker_tunnel_task.ps1`

