# Repo documentation scoring (Phase 8)

Deterministic **0–100** score and **letter grade** for a single repository root (`assess_repo_documentation`). No LLM and no worker; local filesystem read only.

## Scoring model (weights)

| Bucket | Max pts | What it measures |
|--------|---------|------------------|
| README validity | 35 | Policy validation (`validate_readme`): valid README vs missing sections / weak sections. |
| Setup / config / usage clarity | 20 | Presence (and not weak) of `setup`, `configuration`, and `usage` policy keys. |
| Verification / troubleshooting | 15 | Strong `verification` section; optional boost if troubleshooting-like signals exist. |
| Runbook / system map | 15 | Validity of discovered runbooks/system maps under `docs/`, `runbooks/`, `docs/runbooks/` (bounded scan). Neutral partial score if none discovered. |
| Freshness / pulse consistency | 15 | `repo_pulse` row when matched: `readme_fresh`, `stale`, `todo_fixme_count`. Partial score if pulse row missing. |

**Consistency penalty:** up to 15 points subtracted from the sum of buckets based on `check_repo_docs_consistency` issue count (broken links, missing backtick paths, stale template references, duplicate fenced setup blocks, README entrypoint paths).

Final score is clamped to **0–100**.

## Grades

| Grade | Score |
|-------|-------|
| A | ≥ 90 |
| B | ≥ 80 |
| C | ≥ 70 |
| D | ≥ 60 |
| F | below 60 |

## Risk level

Heuristic from score, invalid doc count, and consistency issue count (`low` / `medium` / `high`). Used for workplans and batch proposals—not for bypassing approvals.

## Workplans (`build_repo_docs_workplan`)

Builds **ordered tasks** from assessment + validation + consistency grouping:

- Each task lists **affected files**, **issue type**, **proposed fix**, **approval_required** (always true for write intent), **risk_level**, **estimated_effort** (`small` / `medium` / `large`), and **verification_steps**.
- Consistency findings are **grouped by source markdown file** so related fixes stay together.

## Batch proposals (`create_repo_docs_batch_proposal`)

Produces a single structured proposal:

- `proposal_id`, `target_files`, `proposed_changes`, `grouped_sections`
- `approval_required: true`, `action_classification: modifies-files-or-state`, `no_direct_write_performed: true`
- **No files are written** by this function.

The orchestrator may enqueue **one** approval card for the batch (primary file path + JSON summary preview)—human execution still applies. Roadmap for richer UX: see **Phase 8+ follow-ups** in [`AI_ROUTING_POLICY.md`](AI_ROUTING_POLICY.md) (multi-file approval UI with per-file cards).

## Consistency checks (`check_repo_docs_consistency`)

Lightweight rules (bounded to `docs/**/*.md` plus `README.md`, max 25 files):

- Markdown links to missing repo-relative paths
- Backticked paths to missing files (common extensions)
- References to `docs/templates/` when template files are absent
- Identical fenced install/run blocks repeated across files
- README mentions of relative script paths (`./…`, `scripts/…`) that do not exist

## Approval behavior

All automated change paths remain **proposal + approval**. Scoring, consistency, and workplans are read-only. Batch proposal generation does not modify the working tree.

## Limitations

- Scoring uses heuristics; it is not a substitute for human technical review.
- `repo_pulse` path / freshness fields must align with disk for the freshness bucket to be meaningful.
- Deep link resolution does not follow URL redirects or monorepo packages outside the repo root.
- Command Center `GET /api/repo-docs/score` defaults to the **ai-lab** repo name unless `repo` matches **repo_pulse** or you use orchestrator prompts with an explicit path.

## Orchestrator prompts (examples)

- `score repo documentation`
- `give ai-lab docs a grade`
- `make a repo docs workplan`
- `check docs consistency`
- `create a batch docs proposal`
- `what docs should be updated together?`

Include a **Windows path** or a **repo_pulse repo name** in the message when not scoring **ai-lab**.
