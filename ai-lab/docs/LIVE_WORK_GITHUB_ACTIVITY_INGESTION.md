# Phase 12 — GitHub PR / Issue Ingestion

## Why GitHub is second

Phase 11 established local work signals (branches, commits, changed files).  
Phase 12 adds remote project truth (PR/issue status) so planning can distinguish:

- in-flight coding
- blocked review/check work
- ready-to-merge work
- stale remote items

This enables plan reconciliation without mutating GitHub or ClickUp.

## What this lane reads

- GitHub PR metadata (read-only):
  - title, branches, state, draft, labels, reviewers, reviews, checks, linked issues
- GitHub issue metadata (read-only):
  - state, labels, assignees, milestone, linked PR references
- Local repo activity snapshot for correlation:
  - `state/live_work_orchestration/ingestion/repo_activity_snapshot.json`

## What this lane does NOT do

- No PR/issue create/update/close
- No review submission
- No comments
- No label edits
- No branch writes
- No ClickUp execution

## Access method

Preferred order:
1. existing connector (if present)
2. `gh` CLI read-only API calls
3. test/mock data for unit tests

If access is unavailable, snapshot returns:
- `stale: true`
- `missing_sources: ["github_access_unavailable"]`
- explicit error messages

## Config

`config/live_work_ingestion.example.yaml`

```yaml
github_activity:
  enabled: true
  repos:
    - owner: YOUR_ORG_OR_USER
      name: ai-lab
      local_path: E:/Repos/ai-lab
  include_prs: true
  include_issues: true
  include_closed_recent: false
  since_days: 14
  max_items_per_repo: 50
```

## Correlation with local repo activity

`correlate_github_with_repo_activity(...)` links local and remote by:

- local `current_branch` ↔ PR `head_branch`
- local `likely_feature_name` ↔ PR feature/title

It then emits `feature_states` with:
- `feature_name`
- `repo_name`
- `local_activity_present`
- `linked_pr`
- `issue_refs`
- `rollout_stage`
- `blockers`
- `next_action`
- `confidence`
- `evidence`

## Snapshot output

Writes:

- `state/live_work_orchestration/ingestion/github_activity_snapshot.json`

Includes:
- `prs`
- `issues`
- `feature_states`
- `correlation_summary`

## How it feeds planning

- `builders.py` injects GitHub feature/blocker signals into `daily_progress_snapshot`.
- `compiler.py` can mention:
  - PRs needing review
  - blocked PRs/issues
  - local work without PR
  - PRs ready to merge
  - stale open PRs without recent local activity

No completion is assumed.

## Phase 13 preparation

Combining Phase 11 local tempo and Phase 12 remote lifecycle states creates the minimum timeline substrate for Phase 13 timetable building.
