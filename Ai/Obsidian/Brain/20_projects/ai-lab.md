---
project_name: ai-lab
type: core-project
status: active
created: 2026-02-06
updated: 2026-05-28
---

# ai-lab

## Overview
Multi-rig AI operations hub: orchestration, command center, agents, registry, memory, policy, observability. Primary workspace repo under `E:\Repos\ai-lab`.

## Key Areas

### Runtime
- `brain/` — orchestrator, execution, approvals, worker SSH
- `command-center/` — operator UI (Vite/React + FastAPI)
- `agents/`, `registry/`, `memory/`, `policy/`

### Docs & ops
- `docs_source/` — canonical documentation
- `scripts/` — start/stop, tunnels, sync
- `observability/` — health collection

## Project Notes
<!-- Add links to project-specific notes as they are created -->
- [[20_projects/ai-lab/agents|agents]]
- [[20_projects/ai-lab/approved_tools|approved_tools]]
- [[20_projects/ai-lab/brain|brain]]
- [[20_projects/ai-lab/command-center|command-center]]
- [[20_projects/ai-lab/config|config]]
- [[20_projects/ai-lab/docs|docs]]
- [[20_projects/ai-lab/docs_source|docs_source]]
- [[20_projects/ai-lab/email_sorter|email_sorter]]
- [[20_projects/ai-lab/experimental_tools|experimental_tools]]
- [[20_projects/ai-lab/lib|lib]]
- [[20_projects/ai-lab/logs|logs]]
- [[20_projects/ai-lab/m6b-docsync|m6b-docsync]]
- [[20_projects/ai-lab/memory|memory]]
- [[20_projects/ai-lab/observability|observability]]
- [[20_projects/ai-lab/ops|ops]]
- [[20_projects/ai-lab/policy|policy]]
- [[20_projects/ai-lab/rag_ingest|rag_ingest]]
- [[20_projects/ai-lab/registry|registry]]
- [[20_projects/ai-lab/reports|reports]]
- [[20_projects/ai-lab/repos_mirror|repos_mirror]]
- [[20_projects/ai-lab/scripts|scripts]]
- [[20_projects/ai-lab/state|state]]
- [[20_projects/ai-lab/summaries|summaries]]
- [[20_projects/ai-lab/tests|tests]]
- [[20_projects/ai-lab/tools|tools]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Repo Structure




<!-- REPO_STRUCTURE_START -->
|-- .vscode
|   +-- settings.json
|-- agents
|   |-- business_agent
|   |   +-- __init__.py
|   |-- docs_maintainer
|   |   |-- __init__.py
|   |   +-- summarizer.py
|   |-- feedback_interpreter
|   |   |-- __init__.py
|   |   +-- interpreter.py
|   |-- ops_watcher
|   |   +-- __init__.py
|   |-- rag_builder
|   |   +-- __init__.py
|   |-- repo_cartographer
|   |   |-- __init__.py
|   |   +-- cartographer.py
|   +-- script_librarian
|       +-- __init__.py
|-- approved_tools
|   +-- .gitkeep
|-- brain
|   |-- approval_queue
|   |   |-- __init__.py
|   |   +-- queue.py
|   |-- automation
|   |   |-- planner.py
|   |   +-- runner.py
|   |-- hardware
|   |   |-- collectors
|   |   |   |-- __init__.py
|   |   |   |-- cpu_monitor.py
|   |   |   |-- gpu_monitor.py
|   |   |   |-- process_monitor.py
|   |   |   +-- snapshot.py
|   |   |-- control
|   |   |   |-- __init__.py
|   |   |   |-- cpu_affinity.py
|   |   |   |-- gpu_scheduler.py
|   |   |   +-- process_priority.py
|   |   |-- schemas
|   |   |   |-- __init__.py
|   |   |   +-- hardware_metrics.py
|   |   |-- telemetry
|   |   |   |-- __init__.py
|   |   |   |-- alerts.py
|   |   |   +-- hardware_logger.py
|   |   +-- __init__.py
|   |-- integration_inventory
|   |   |-- __init__.py
|   |   |-- growflow_classify.py
|   |   +-- integration_inventory_generator.py
|   |-- live_work_orchestration
|   |   |-- ingestion
|   |   |   |-- __init__.py
|   |   |   |-- bills.py
|   |   |   |-- github_activity.py
|   |   |   +-- repo_activity.py
|   |   |-- timetable
|   |   |   |-- __init__.py
|   |   |   |-- calibration.py
|   |   |   |-- estimation.py
|   |   |   |-- feature_model.py
|   |   |   |-- guardrails.py
|   |   |   |-- measured_time.py
|   |   |   +-- timeline_builder.py
|   |   |-- __init__.py
|   |   |-- builders.py
|   |   |-- clickup_actions.py
|   |   |-- clickup_queue.py
|   |   |-- clickup_routing.py
|   |   |-- compiler.py
|   |   |-- schema.py
|   |   +-- workers.py
|   |-- orchestrator
|   |   |-- __init__.py
|   |   |-- approval_gate.py
|   |   |-- evidence_fusion.py
|   |   |-- evidence_loader.py
|   |   |-- freshness.py
|   |   |-- main.py
|   |   |-- proposal_engine.py
|   |   |-- response_trace.py
|   |   |-- routing_policy.py
|   |   |-- session_resolution.py
|   |   |-- source_router.py
|   |   +-- strategies.py
|   |-- permanent_allow
|   |-- planner
|   |   |-- __init__.py
|   |   +-- agenda.py
|   |-- prepared_context
|   |   |-- __init__.py
|   |   |-- builders.py
|   |   |-- loader.py
|   |   |-- schema.py
|   |   |-- selection.py
|   |   +-- store.py
|   |-- prompts
|   |   +-- grounded_prompt.txt
|   |-- router
|   |   |-- __init__.py
|   |   +-- router.py
|   |-- schemas
|   |   |-- __init__.py
|   |   |-- evidence.py
|   |   |-- proposals.py
|   |   +-- routing.py
|   |-- tools
|   |   |-- __init__.py
|   |   |-- time_context.py
|   |   +-- weather_context.py
|   |-- __init__.py
|   |-- approval_enforcement.py
|   |-- catalog_loader.py
|   |-- execution.py
|   |-- failure_analysis.py
|   |-- llm_client.py
|   |-- ops_registry.py
|   |-- permanent_allowlist.py
|   |-- repo_doc_policy.py
|   |-- repo_doc_validation.py
|   |-- repo_docs_maintainer.py
|   |-- repo_docs_repo_level.py
|   |-- repo_search.py
|   |-- secret_broker.py
|   |-- session_state.py
|   |-- session_store.py
|   |-- source_selection.py
|   |-- ssh_worker.py
|   |-- telemetry.py
|   |-- tool_registry.py
|   |-- web_query_builder.py
|   |-- web_tool.py
|   |-- worker_clients.py
|   |-- worker_health.py
|   |-- worker_registry.py
|   |-- worker_services.py
|   +-- worker_tunnel.py
|-- command-center
|   +-- command-center
|       |-- .logs
|       |   |-- frontend.err.log
|       |   +-- frontend.log
|       |-- {frontend
|       |   +-- src
|       |       +-- {components,hooks,lib,store},backend
|       |           +-- {routers,services,core},scripts}
|       |-- backend
|       |   |-- core
|       |   |   |-- __init__.py
|       |   |   |-- ai_lab.py
|       |   |   |-- config.py
|       |   |   +-- models.py
|       |   |-- routers
|       |   |   |-- __init__.py
|       |   |   |-- chat.py
|       |   |   |-- events.py
|       |   |   |-- guru.py
|       |   |   |-- hardware.py
|       |   |   |-- live_work.py
|       |   |   |-- prepared_context.py
|       |   |   |-- repo.py
|       |   |   |-- repo_docs.py
|       |   |   |-- repo_index.py
|       |   |   |-- tools.py
|       |   |   +-- workers.py
|       |   |-- services
|       |   |   |-- __init__.py
|       |   |   |-- feed_bus.py
|       |   |   |-- guru_service.py
|       |   |   |-- index_job_types.py
|       |   |   |-- index_policy.py
|       |   |   |-- nvidia_poller.py
|       |   |   |-- observability.py
|       |   |   |-- prepared_context_refresher.py
|       |   |   |-- repo_index_coordinator.py
|       |   |   |-- repo_index_state_store.py
|       |   |   |-- repo_watcher.py
|       |   |   +-- supervisor_bridge.py
|       |   |-- state
|       |   |   +-- repo_index_state.json
|       |   |-- tests
|       |   |   |-- __init__.py
|       |   |   |-- conftest.py
|       |   |   |-- test_chat_router.py
|       |   |   |-- test_events_router.py
|       |   |   |-- test_feed_bus.py
|       |   |   |-- test_guru_service.py
|       |   |   |-- test_hardware_router.py
|       |   |   |-- test_live_work_router.py
|       |   |   |-- test_repo_docs_router.py
|       |   |   |-- test_repo_router.py
|       |   |   |-- test_repo_summaries.py
|       |   |   +-- test_supervisor_bridge_policy_parity.py
|       |   |-- .env
|       |   |-- .env.example
|       |   |-- Dockerfile
|       |   |-- env.minimal
|       |   |-- main.py
|       |   |-- pytest.ini
|       |   |-- requirements.txt
|       |   +-- requirements-dev.txt
|       |-- config
|       |   +-- index_policy.yaml
|       |-- docs
|       |   |-- FRONTEND_BACKEND_CONTRACT_AUDIT.md
|       |   +-- WORKER_REPO_INDEX_API_CONTRACT.md
|       |-- frontend
|       |   |-- src
|       |   |   |-- components
|       |   |   |   |-- ChatPanel.jsx
|       |   |   |   |-- ChatPanel.test.jsx
|       |   |   |   |-- ComputePanel.jsx
|       |   |   |   |-- DiagnosticsPanel.jsx
|       |   |   |   |-- FeedPanel.jsx
|       |   |   |   |-- GuruPanel.jsx
|       |   |   |   |-- GuruPanel.test.jsx
|       |   |   |   |-- Primitives.jsx
|       |   |   |   |-- RepoPanel.jsx
|       |   |   |   |-- Sidebar.jsx
|       |   |   |   +-- ToolsPanel.jsx
|       |   |   |-- hooks
|       |   |   |   |-- useWebSocket.js
|       |   |   |   +-- useWebSocket.test.jsx
|       |   |   |-- lib
|       |   |   |   |-- api.js
|       |   |   |   +-- diagnostics.js
|       |   |   |-- store
|       |   |   |   +-- index.js
|       |   |   |-- test
|       |   |   |   +-- setup.js
|       |   |   |-- App.jsx
|       |   |   |-- index.css
|       |   |   +-- main.jsx
|       |   |-- .env.example
|       |   |-- Dockerfile
|       |   |-- index.html
|       |   |-- nginx.conf
|       |   |-- package.json
|       |   |-- package-lock.json
|       |   |-- postcss.config.js
|       |   |-- tailwind.config.js
|       |   |-- vite.config.js
|       |   +-- vitest.config.js
|       |-- scripts
|       |   |-- bootstrap.ps1
|       |   |-- deps.ps1
|       |   |-- restart.ps1
|       |   |-- run-backend.ps1
|       |   |-- start.ps1
|       |   |-- start.sh
|       |   |-- start-background.ps1
|       |   +-- stop.ps1
|       |-- state
|       |-- .gitignore
|       |-- backend_start.log
|       |-- backend_startup.log
|       |-- BOOT.md
|       |-- docker-compose.yml
|       |-- Guru.md
|       +-- README.md
|-- config
|   |-- bills.example.yaml
|   |-- clickup_mapping.yaml
|   |-- connectors.yaml
|   |-- live_work_ingestion.example.yaml
|   +-- personal_ops.example.yaml
|-- docs
|   |-- templates
|   |   |-- README_TEMPLATE.md
|   |   +-- RUNBOOK_TEMPLATE.md
|   |-- AI_LAB_INTEGRATION_HEALTH_SUMMARY.md
|   |-- AI_MODEL_USEFULNESS_AUDIT.md
|   |-- AI_RESPONSE_BENCHMARKS.md
|   |-- AI_RESPONSE_PIPELINE_AUDIT.md
|   |-- AI_ROUTING_POLICY.md
|   |-- AI_SPEED_AND_USEFULNESS_FIX_PLAN.md
|   |-- APPROVAL_ENFORCEMENT_PARITY.md
|   |-- EMAIL_BACKFILL_DRY_RUN_REPORT.md
|   |-- EMAIL_CLUSTER_ANALYSIS.md
|   |-- EMAIL_CLUSTER_LABEL_SUGGESTIONS.md
|   |-- EMAIL_SORTER_INTEGRATION_MAP.md
|   |-- EMAIL_SORTER_RUNBOOK.md
|   |-- GOAL_ALIGNMENT_AUDIT.md
|   |-- GROWFLOW_CANONICAL_RUNNERS.md
|   |-- LIVE_WORK_ACTION_LOOP.md
|   |-- LIVE_WORK_BILLS_INGESTION.md
|   |-- LIVE_WORK_CLICKUP_ACTION_LOOP.md
|   |-- LIVE_WORK_ESTIMATION_CALIBRATION.md
|   |-- LIVE_WORK_GITHUB_ACTIVITY_INGESTION.md
|   |-- LIVE_WORK_INGESTION_LANES.md
|   |-- LIVE_WORK_MEASURED_TIME_CALIBRATION.md
|   |-- LIVE_WORK_ORCHESTRATION_FOUNDATION.md
|   |-- LIVE_WORK_ORCHESTRATION_PHASES.md
|   |-- LIVE_WORK_ORCHESTRATION_SPEC.md
|   |-- LIVE_WORK_REPO_ACTIVITY_INGESTION.md
|   |-- LIVE_WORK_TIMETABLE_BUILDER.md
|   |-- MAIN_RIG_ORCHESTRATION.md
|   |-- ORPHANED_SCRIPT_REPORT.md
|   |-- PERSONAL_OPS_SNAPSHOT_PLAN.md
|   |-- PREPARED_CONTEXT_ARCHITECTURE.md
|   |-- PREPARED_CONTEXT_SCHEDULER_SETUP.md
|   |-- PREPARED_CONTEXT_SELECTION_HARDENING.md
|   |-- PREPARED_CONTEXT_WIRING_AUDIT.md
|   |-- REPO_DOCUMENTATION_MAINTAINER.md
|   |-- REPO_DOCUMENTATION_POLICY.md
|   |-- REPO_DOCUMENTATION_SCORING.md
|   |-- ROADMAP_PHASE_NOTES.md
|   |-- SCRIPT_TOOL_INVENTORY.md
|   |-- SCRIPT_TOOL_INVENTORY_AUTO.md
|   |-- SYSTEM_WIRING_AUDIT.md
|   |-- TOOL_REGISTRY_AUDIT.md
|   |-- TRIGGER_AND_SCHEDULER_AUDIT.md
|   |-- WORKER_INTEGRATION_AUDIT.md
|   +-- WORKSPACE_REPO_INDEX.md
|-- docs_source
|   |-- contracts
|   |   |-- execution.md
|   |   |-- memory.md
|   |   |-- policy.md
|   |   |-- registry.md
|   |   +-- worker.md
|   |-- DOCUMENTATION_STANDARD.md
|   |-- REPO_MIRROR.md
|   |-- SSH_SETUP.md
|   +-- WORKER_CURRENT.md
|-- email_sorter
|   |-- config
|   |   |-- labels.yaml
|   |   |-- rules.yaml
|   |   +-- thresholds.yaml
|   |-- gmail_portable
|   |   |-- app
|   |   |   |-- __init__.py
|   |   |   +-- gmail_client.py
|   |   +-- README.md
|   |-- scripts
|   |   |-- install_email_sorter_schedule_old_rig.ps1
|   |   +-- run_backfill_apply.ps1
|   |-- __init__.py
|   |-- backfill.py
|   |-- cluster.py
|   |-- cluster_analysis.json
|   |-- discovery.py
|   |-- imap_backfill.py
|   |-- proposed_label_mapping.yaml
|   +-- proposed_rules_patch.yaml
|-- experimental_tools
|   +-- .gitkeep
|-- lib
|   |-- google_calendar_client.py
|   |-- repo_staleness.py
|   +-- telegram_simple.py
|-- logs
|   |-- approval_logs
|   |   |-- pending.json
|   |   |-- resolved_approval_1.json
|   |   |-- resolved_approval_2.json
|   |   |-- resolved_approval_3.json
|   |   +-- resolved_approval_4.json
|   |-- command_center
|   |   |-- api_requests.jsonl
|   |   |-- errors.jsonl
|   |   |-- event_stream.jsonl
|   |   |-- smoke_chat_run.py
|   |   |-- smoke_chat_run_results.json
|   |   |-- uvicorn_smoke.log
|   |   +-- uvicorn_smoke_err.log
|   |-- config_changes
|   |-- email_sorter
|   |   |-- backfill
|   |   |   |-- phase1_dryrun_fetch_error_20260318_205208_76d07aa9.jsonl
|   |   |   +-- phase1_dryrun_fetch_error_20260318_205612_2b273af8.jsonl
|   |   |-- backfill_apply_1773974141.jsonl
|   |   |-- backfill_apply_1773974206.jsonl
|   |   |-- backfill_apply_1773974279.jsonl
|   |   |-- backfill_dryrun_1773868753.jsonl
|   |   |-- backfill_dryrun_1773869184.jsonl
|   |   |-- backfill_imap_dryrun_1773870658.jsonl
|   |   |-- backfill_imap_dryrun_1773870714.jsonl
|   |   |-- backfill_imap_dryrun_1773871392.jsonl
|   |   |-- backfill_imap_dryrun_1773872229.jsonl
|   |   |-- backfill_imap_dryrun_1773872458.jsonl
|   |   |-- backfill_imap_dryrun_1773899692.jsonl
|   |   |-- backfill_imap_dryrun_1773953698.jsonl
|   |   |-- backfill_imap_dryrun_1773957855.jsonl
|   |   |-- backfill_imap_dryrun_1773959018.jsonl
|   |   |-- backfill_imap_dryrun_1773959648.jsonl
|   |   +-- backfill_imap_dryrun_1773960246.jsonl
|   |-- execution_logs
|   |   |-- growflow_sales_today_159537.json
|   |   +-- growflow_sales_today_159636.json
|   |-- guru_threads
|   |   |-- AL.json
|   |   |-- ATL.json
|   |   |-- PR.json
|   |   |-- RR.json
|   |   +-- TL.json
|   |-- hardware
|   |   |-- snapshots_2026-03-17.jsonl
|   |   |-- snapshots_2026-03-18.jsonl
|   |   |-- snapshots_2026-03-19.jsonl
|   |   |-- snapshots_2026-03-20.jsonl
|   |   |-- snapshots_2026-03-21.jsonl
|   |   |-- snapshots_2026-03-22.jsonl
|   |   |-- snapshots_2026-03-23.jsonl
|   |   |-- snapshots_2026-03-24.jsonl
|   |   |-- snapshots_2026-03-25.jsonl
|   |   |-- snapshots_2026-03-26.jsonl
|   |   |-- snapshots_2026-04-02.jsonl
|   |   |-- snapshots_2026-04-03.jsonl
|   |   |-- snapshots_2026-04-04.jsonl
|   |   |-- snapshots_2026-04-05.jsonl
|   |   |-- snapshots_2026-04-06.jsonl
|   |   |-- snapshots_2026-04-07.jsonl
|   |   +-- snapshots_2026-05-01.jsonl
|   |-- worker_tunnel
|   |   |-- tunnel_watch_20260319.log
|   |   +-- tunnel_watch_20260407.log
|   +-- telemetry.jsonl
|-- m6b-docsync
|   +-- m6b-docsync
|       |-- {rules,templates,schemas}
|       |-- rules
|       |   |-- AGENT_RULES.md
|       |   +-- STALENESS_RULES.md
|       |-- schemas
|       |   |-- DECISION_LOG_SCHEMA.json
|       |   +-- PROPOSAL_SCHEMA.json
|       |-- templates
|       |   |-- EXAMPLE_PROPOSALS.json
|       |   +-- PROPOSAL_CARDS.md
|       +-- README.md
|-- memory
|   |-- business_definitions.json
|   |-- preferences.json
|   |-- project_state.json
|   |-- successful_workflows.json
|   |-- trust_rules.json
|   +-- workflow_rules.json
|-- observability
|   |-- collect_health.py
|   |-- health.json
|   |-- security.json
|   +-- services.json
|-- ops
|   |-- docs
|   |   |-- automations
|   |   |   +-- .gitkeep
|   |   |-- infrastructure
|   |   |   +-- .gitkeep
|   |   |-- standards
|   |   |   +-- .gitkeep
|   |   +-- systems
|   |       +-- .gitkeep
|   |-- graphs
|   |   |-- dataflows
|   |   |   +-- .gitkeep
|   |   |-- dependencies
|   |   |   +-- .gitkeep
|   |   +-- system
|   |       +-- .gitkeep
|   |-- registry
|   |   |-- automations.yaml
|   |   |-- systems.yaml
|   |   +-- workers.yaml
|   |-- reports
|   |   |-- daily
|   |   |   +-- .gitkeep
|   |   |-- health
|   |   |   +-- .gitkeep
|   |   +-- weekly
|   |       +-- .gitkeep
|   +-- runbooks
|       |-- apps
|       |   +-- .gitkeep
|       |-- connectors
|       |   +-- .gitkeep
|       +-- workers
|           +-- .gitkeep
|-- policy
|   |-- allowlists.yaml
|   |-- autonomy_policy.yaml
|   +-- blocklists.yaml
|-- rag_ingest
|   +-- docs
|       +-- .gitkeep
|-- registry
|   |-- integrations.json
|   |-- repos.json
|   |-- scripts.json
|   |-- services.json
|   +-- workflows.json
|-- reports
|   |-- invoices
|   |   |-- invoice_stoned-projects_to_leigha-saavedara.pdf
|   |   +-- invoice_stoned-projects_to_leigha-saavedra_2024-10-15.pdf
|   +-- .gitkeep
|-- repos_mirror
|   +-- .gitkeep
|-- scripts
|   |-- worker_ai
|   |   +-- validate_m1_checklist.ps1
|   |-- analyze_trace_sessions.py
|   |-- benchmark_ai_response.py
|   |-- build_live_work_orchestration_snapshots.py
|   |-- build_prepared_context.py
|   |-- calibrate_estimates.py
|   |-- check_worker_connectivity.py
|   |-- generate_growflow_runners_json.py
|   |-- generate_integration_inventory.py
|   |-- generate_invoice_pdf.py
|   |-- github_repo_sync.py
|   |-- ingest_github_activity.py
|   |-- ingest_repo_activity.py
|   |-- maintain_worker_tunnel.ps1
|   |-- personal_ops_calendar_snapshot.py
|   |-- personal_ops_daily_digest.py
|   |-- personal_ops_repo_pulse.py
|   |-- personal_ops_worker_ollama_calendar.py
|   |-- refresh_prepared_context_all.ps1
|   |-- refresh_prepared_context_growflow.ps1
|   |-- refresh_prepared_context_personal_ops.ps1
|   |-- refresh_prepared_context_project_agenda.ps1
|   |-- refresh_prepared_context_repo_pulse.ps1
|   |-- refresh_prepared_context_system.ps1
|   |-- refresh_prepared_context_worker.ps1
|   |-- remove_prepared_context_tasks.ps1
|   |-- repo_full_rebuild_gate_a.py
|   |-- repo_policy_migration_gate_c.py
|   |-- restart.ps1
|   |-- run_trace_sessions.py
|   |-- Run-GitHubRepoSync.ps1
|   |-- setup_prepared_context_tasks.ps1
|   |-- setup_worker_tunnel_task.ps1
|   |-- start.ps1
|   |-- start_worker_tunnel.ps1
|   |-- start-background.ps1
|   |-- stop.ps1
|   |-- worker_tunnel.local.json
|   |-- worker_tunnel.local.json.example
|   +-- worker_visible_ollama_demo.ps1
|-- state
|   |-- integration_inventory
|   |   |-- growflow_runners.json
|   |   |-- orphans.json
|   |   |-- scripts.json
|   |   |-- summary.json
|   |   |-- tools.json
|   |   +-- triggers.json
|   |-- live_work_orchestration
|   |   |-- calibration
|   |   |-- ingestion
|   |   |   |-- bills_snapshot.json
|   |   |   |-- github_activity_snapshot.json
|   |   |   +-- repo_activity_snapshot.json
|   |   |-- communication_queue_snapshot.json
|   |   |-- daily_progress_snapshot.json
|   |   |-- index.json
|   |   |-- planning_gaps_snapshot.json
|   |   |-- time_constraints_snapshot.json
|   |   +-- work_demand_snapshot.json
|   |-- prepared_context
|   |   |-- growflow_snapshot.json
|   |   |-- index.json
|   |   |-- personal_ops_snapshot.json
|   |   |-- project_agenda.json
|   |   |-- repo_pulse.json
|   |   |-- system_snapshot.json
|   |   +-- worker_snapshot.json
|   |-- ai_response_traces.jsonl
|   +-- github_repo_sync_config.json
|-- summaries
|   |-- projects
|   |   +-- .gitkeep
|   |-- repos
|   |   |-- .gitkeep
|   |   |-- repos_root.json
|   |   +-- repos_root_summary.md
|   +-- weekly
|       +-- .gitkeep
|-- tests
|   |-- conftest.py
|   |-- test_approval_enforcement_parity.py
|   |-- test_approval_gate.py
|   |-- test_cartographer.py
|   |-- test_clickup_action_loop.py
|   |-- test_email_sorter_backfill.py
|   |-- test_email_sorter_cluster.py
|   |-- test_evidence_loader.py
|   |-- test_freshness.py
|   |-- test_fusion.py
|   |-- test_github_repo_sync.py
|   |-- test_growflow_canonical_runners.py
|   |-- test_hardware.py
|   |-- test_hardware_control.py
|   |-- test_integration_audit_validations.py
|   |-- test_integration_flows.py
|   |-- test_integration_inventory_generator.py
|   |-- test_live_work_bills_ingestion.py
|   |-- test_live_work_estimation_calibration.py
|   |-- test_live_work_github_activity_ingestion.py
|   |-- test_live_work_measured_time_calibration.py
|   |-- test_live_work_orchestration.py
|   |-- test_live_work_repo_activity_ingestion.py
|   |-- test_live_work_timetable.py
|   |-- test_orchestrator_rules.py
|   |-- test_personal_ops_snapshot.py
|   |-- test_prepared_context.py
|   |-- test_prepared_context_selection.py
|   |-- test_proposals.py
|   |-- test_repo_doc_policy.py
|   |-- test_repo_docs_maintainer.py
|   |-- test_repo_docs_maintainer_expansion.py
|   |-- test_router.py
|   |-- test_routing_policy.py
|   |-- test_session_resolution.py
|   |-- test_source_router.py
|   |-- test_ssh_worker.py
|   |-- test_worker_health.py
|   |-- test_worker_orchestration.py
|   |-- test_worker_registry.py
|   +-- test_worker_services.py
|-- tools
|-- .gitignore
|-- cluster_500_output.txt
|-- offsite_task_tracker.html
|-- package-lock.json
|-- pytest.ini
|-- README.md
|-- requirements.txt
|-- requirements-email-sorter.txt
|-- sessions.sqlite
|-- Smaller World 1.code-workspace
+-- TESTING.md
<!-- REPO_STRUCTURE_END -->

## Change Log
<!-- CHANGELOG_START -->
<!-- CHANGELOG_END -->

## Related
- [[20_projects/index|Projects Index]]
- [[20_projects/ai-lab-governance|ai-lab-governance]]
