# Phase 11 — Local Repo Activity Ingestion

## Purpose

Add a single read-only ingestion lane that captures local git activity as planning-grade progress signals.

## What it reads

- Local repository metadata only:
  - git repo discovery via `.git` directories under configured roots (bounded by `scan_depth`)
  - `git rev-parse --abbrev-ref HEAD`
  - `git status --short`
  - `git log --pretty=format:%s|%cI` with bounded `-n` (optional `--since`)
  - **Phase 16:** `os.stat` **mtime only** for paths reported by `git status` (changed/untracked), capped by `max_file_timestamp_samples` — **no file contents**, **no full-repo scan**
  - **Phase 16:** read-only upstream hints: `git remote -v`, `git rev-parse --verify @{upstream}`, `git rev-list --left-right --count HEAD...@{upstream}` (no fetch, no push, no commit)
- File *paths* from git status (sampled), not file contents.

## Local file activity tracking (Phase 16)

- `file_activity_window_start` / `file_activity_window_end`: earliest / latest **mtime** among status-listed files (bounded sample).
- `modified_file_timestamps_sample`: bounded list of `{path, mtime_iso}` for auditability.
- `modified_files_count`: count of paths that yielded a successful file mtime (may be less than `changed_files_count` if paths are missing or not files).
- `first_commit_time`, `last_commit_time`, `commit_timestamps`: bounded commit **timestamps** from `git log` (no message body reads beyond subject line in existing flow).
- `activity_window_start` / `activity_window_end`: combined earliest / latest of file window and commit bounds when present; never fabricated.
- **Git hygiene (advisory only):** `commit_needed`, `push_needed`, `branch_ahead` / `branch_behind`, `has_remote`, `uncommitted_work_age_hours`, `git_hygiene_summary` — suggestions only; **no** auto-commit or auto-push.

### Why mtimes

Commits can be sparse; local saves often reflect real work sessions. Mtimes are coarse, machine-local signals — not proof of continuous focus.

### Limitations

- A wide window does **not** mean continuous work between start and end.
- Clock skew, rebases, cherry-picks, and CI touching files can distort mtimes.
- Hygiene flags are conservative when no upstream is configured.

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
  include_file_activity: true
  max_file_timestamp_samples: 25
  include_commit_subjects: true
  max_commit_subjects: 20
  include_commit_timestamps: true
  max_commit_timestamps: 20
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
