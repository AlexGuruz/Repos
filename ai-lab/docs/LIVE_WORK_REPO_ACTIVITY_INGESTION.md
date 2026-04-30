# Phase 11 — Local Repo Activity Ingestion

## Purpose

Add a single read-only ingestion lane that captures local git activity as planning-grade progress signals.

## What it reads

- Local repository metadata only:
  - git repo discovery via `.git` directories under configured roots (bounded by `scan_depth`)
  - `git rev-parse --abbrev-ref HEAD`
  - `git status --short`
  - `git log --pretty=format:%s|%cI -n 20` (optional `--since`)
- File *paths* from git status (sampled), not file contents.

## What it does NOT read

- Full source file bodies by default.
- GitHub API / PR data.
- Email, bank/Tiller, Drive, calendar, desktop/window telemetry.
- ClickUp tasks/comments/status.

## Privacy and safety guarantees

- Read-only ingestion lane.
- No repo file modifications.
- No ClickUp execution or mutation.
- Snapshot output stays local in `state/live_work_orchestration/ingestion/`.

## Configuration

Template: `config/live_work_ingestion.example.yaml`

```yaml
repo_activity:
  enabled: true
  repo_roots:
    - E:/Repos/ai-lab
  scan_depth: 2
  include_file_samples: true
  max_file_samples: 20
  include_commit_subjects: true
  since_hours: 24
```

## How to run

From `ai-lab` root:

```bash
python scripts/ingest_repo_activity.py
python scripts/ingest_repo_activity.py --rebuild-daily-progress
```

## Output

- Primary snapshot:
  - `state/live_work_orchestration/ingestion/repo_activity_snapshot.json`
- Daily progress integration:
  - `state/live_work_orchestration/daily_progress_snapshot.json` includes:
    - `repo_activity_rows`
    - `repo_activity_events`
    - `repo_activity_ingestion_summary`

## Planning feed behavior

- Compiler consumes these progress signals in read-only mode.
- It can highlight potential mismatch between planned priorities and observed local activity.
- It does not assume completion and does not create tasks.

## Future integration path

- Phase 12: add GitHub PR ingestion and link to `linked_pr_guess`.
- Phase 13: timetable builder can consume activity intensity and feature area hints.
