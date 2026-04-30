# Live Work Ingestion Lanes

This document tracks ingestion lanes that feed `live_work_orchestration` progress and planning snapshots.

## Phase 11 active lane

- **Local repo activity** (`brain/live_work_orchestration/ingestion/repo_activity.py`)
  - Read-only lane based on local git metadata.
  - Writes `state/live_work_orchestration/ingestion/repo_activity_snapshot.json`.
  - Feeds `daily_progress_snapshot.json` via `builders.py`.

## Purpose

- Improve "what was actually worked on" signals without requiring network integrations.
- Provide structured fields that are reusable in:
  - Phase 12: GitHub PR ingestion
  - Phase 13: timetable builder

## Locked future lanes (not built in Phase 11)

- GitHub PRs (Phase 12)
- Timetable builder (Phase 13)
- Email
- Bank/Tiller
- ClickUp intake
- Desktop monitoring

## Safety baseline

- Ingestion lanes are read-only by default.
- No task creation, no status updates, and no external side effects in ingestion code paths.
