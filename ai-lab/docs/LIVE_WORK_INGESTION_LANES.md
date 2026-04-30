# Live Work Ingestion Lanes

This document tracks ingestion lanes that feed `live_work_orchestration` progress and planning snapshots.

## Active lanes

- **Local repo activity** (`brain/live_work_orchestration/ingestion/repo_activity.py`)
  - Read-only lane based on local git metadata.
  - Writes `state/live_work_orchestration/ingestion/repo_activity_snapshot.json`.
  - Feeds `daily_progress_snapshot.json` via `builders.py`.
- **GitHub PR / issue activity** (`brain/live_work_orchestration/ingestion/github_activity.py`)
  - Read-only lane using existing connector/`gh`/fixtures.
  - Writes `state/live_work_orchestration/ingestion/github_activity_snapshot.json`.
  - Correlates local activity to PR lifecycle and emits `feature_states`.

## Purpose

- Improve "what was actually worked on" signals and connect them to remote review/rollout truth.
- Provide structured fields that are reusable in:
  - Phase 12: GitHub PR/issue ingestion
  - Phase 13: timetable builder

## Locked future lanes (not built yet)

- Timetable builder (Phase 13)
- Email
- Bank/Tiller
- Drive/Gmail
- ClickUp intake
- Desktop monitoring

## Safety baseline

- Ingestion lanes are read-only by default.
- No task creation, no status updates, and no external side effects in ingestion code paths.
