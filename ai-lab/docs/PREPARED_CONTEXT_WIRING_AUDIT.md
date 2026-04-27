# Prepared Context Wiring Audit

## Snapshot matrix


| Snapshot                | Builder source                                              | Refresh trigger                                 | Refresh interval | Output file                                         | Evidence coverage                     | Command Center visibility   | Orchestrator usage                         | Stale threshold         | Quality gate behavior                    | Notes   |
| ----------------------- | ----------------------------------------------------------- | ----------------------------------------------- | ---------------- | --------------------------------------------------- | ------------------------------------- | --------------------------- | ------------------------------------------ | ----------------------- | ---------------------------------------- | ------- |
| `system_snapshot`       | `brain/prepared_context/builders.py::build_system_snapshot` | backend refresher + optional task script/manual | 15 min           | `state/prepared_context/system_snapshot.json`       | includes `evidence_items`             | top bar + Tools panel + API | yes (`try_prepared_context_answer`)        | `freshness_seconds=900` | scored in `_quality_gate`                | wired   |
| `worker_snapshot`       | `build_worker_snapshot`                                     | backend refresher + optional task script/manual | 10 min           | `state/prepared_context/worker_snapshot.json`       | includes service/tunnel evidence      | Tools + API                 | usable via message match                   | `900`                   | low score returns limited summary        | wired   |
| `repo_pulse`            | `build_repo_pulse`                                          | backend refresher + optional task script/manual | 45 min           | `state/prepared_context/repo_pulse.json`            | includes repo/docs freshness evidence | Tools + API                 | primary for repo/docs status prompts       | `3600`                  | broad question penalty applies           | wired   |
| `growflow_snapshot`     | `build_growflow_snapshot`                                   | backend refresher + optional task script/manual | 60 min           | `state/prepared_context/growflow_snapshot.json`     | includes operational evidence items   | Tools + API                 | used for growflow/company-bi style prompts | `3600`                  | stale/traceability penalties apply       | wired   |
| `project_agenda`        | `build_project_agenda`                                      | backend refresher + optional task script/manual | daily            | `state/prepared_context/project_agenda.json`        | agenda/task evidence                  | Tools + API                 | used for planning prompts                  | `86400`                 | generated_at exposure check applies      | wired   |
| `personal_ops_snapshot` | `build_personal_ops_snapshot`                               | backend refresher + optional task script/manual | daily            | `state/prepared_context/personal_ops_snapshot.json` | currently lighter evidence            | Tools + API                 | used for personal-ops prompts              | `86400`                 | low quality often yields limited summary | partial |


## End-to-end wiring proof

- Build + store:
  - `brain/prepared_context/builders.py`
  - `brain/prepared_context/store.py`
- Runtime loader + quality gate:
  - `brain/prepared_context/loader.py` (`try_prepared_context_answer`, `_quality_gate`)
- Orchestrator precheck:
  - `brain/orchestrator/main.py` calls loader before retrieval/model for `answer|ops_overview|company_bi`.
- API:
  - `command-center/backend/routers/prepared_context.py`
- UI:
  - `command-center/frontend/src/components/ToolsPanel.jsx`
  - `command-center/frontend/src/App.jsx` (health badge + popover)
- Trace:
  - `brain/orchestrator/response_trace.py` receives prepared-context and quality fields.

## Stale + quality details

- Stale runtime recomputation occurs in `loader.py` via `is_snapshot_stale` / `load_snapshot_fresh`.
- Low-quality threshold currently: `quality_score < 0.62`.
- Low quality response mode: limited summary + missing data warning + optional refresh hint.

## Missing/weak fields and risks

- `index.json` stale booleans can drift between refreshes because index writers read raw snapshots without dynamic stale recomputation.
- `personal_ops_snapshot` is mostly capability/config presence and can be content-thin.
- Prompt routing to prepared-context still depends on phrase matching (`_pick_snapshots_for_message`), so semantic misses can fall through.

