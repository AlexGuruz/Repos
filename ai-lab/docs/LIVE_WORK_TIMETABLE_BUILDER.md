# Phase 13 — Project Timetable + Estimation Guardrails

This phase adds a read-only timetable builder that combines:

- Phase 11 local repo activity
- Phase 12 GitHub PR/issue feature states

It is designed to avoid false precision and unsafe planning outputs.

## Core components

- `brain/live_work_orchestration/timetable/feature_model.py`
  - `build_feature_states(...)`
- `brain/live_work_orchestration/timetable/estimation.py`
  - `estimate_feature_effort(...)`
- `brain/live_work_orchestration/timetable/guardrails.py`
  - range/quality guardrails
  - clarification generation
- `brain/live_work_orchestration/timetable/timeline_builder.py`
  - `build_project_timetable(...)`

## Guardrail rules

- No point estimates.
- Estimates are ranges only.
- Each estimate includes confidence, risk level, and evidence.
- If evidence is insufficient, status is `unknown_needs_calibration`.

## Clarification behavior

- Missing scope/deadline/priority or low-confidence features emit clarification proposals.
- Clarification target is `Agent Clarifications`.
- No automatic task creation or execution.

## Integration points

- Compiler:
  - `generate_project_timetable(...)`
  - `compile_daily_plan_preview(...)` includes:
    - `project_timetable`
    - `timetable_estimates`
    - `timetable_clarifications`
- Snapshot (optional):
  - `state/live_work_orchestration/timetable_snapshot.json`

## What this phase does NOT do

- No autonomous replanning
- No ClickUp task execution
- No repo/PR/issue mutation
- No new ingestion lanes
