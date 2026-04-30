# Live work orchestration — Phase 9 foundation

Phase 9 establishes **read-only** plumbing for migrating the Daily Work Planner into ai-lab. It does **not** implement the full agent.

## What was built

| Artifact | Purpose |
|----------|---------|
| `brain/live_work_orchestration/schema.py` | Serializable planning objects (`WorkDemand`, `TimeConstraint`, … `DailyPlanPreview`). |
| `brain/live_work_orchestration/workers.py` | Stub / read-only worker interfaces (no Slack send, no Asana mutations). |
| `brain/live_work_orchestration/builders.py` | Snapshot JSON builders consuming **prepared context** (`repo_pulse`, `project_agenda`, `personal_ops_snapshot`, `system_snapshot`, `worker_snapshot`). |
| `brain/live_work_orchestration/compiler.py` | `compile_daily_plan_preview()` — merges snapshots into the **preview section** layout (Today, Before shift, …). |
| `scripts/build_live_work_orchestration_snapshots.py` | CLI to rebuild snapshots; `--preview` prints a text preview. |
| `state/live_work_orchestration/*.json` | Outputs (created by the script, not committed unless you choose to). |
| Command Center | `GET /api/live-work/status`, `GET /api/live-work/plan-preview` (read-only). |

## What is intentionally not built yet

- Live desktop / foreground monitoring.
- Auto-created Asana tasks (unless later routed through **approval** / existing execution).
- Auto-sent Slack messages (unless later routed through **approved Slack** path).
- Calendar event create/update.
- Autonomous replanning loops.
- Full merge into prepared-context **selection** scoring (documented only; trivial merge deferred).

## How to run the snapshot builder

From `ai-lab` root:

```bash
python scripts/build_live_work_orchestration_snapshots.py
python scripts/build_live_work_orchestration_snapshots.py --preview
```

Ensure prepared context snapshots exist (`state/prepared_context/*.json`) so builders have inputs; missing inputs are listed under `missing_sources` rather than fabricated.

## How to inspect outputs

- Directory: `state/live_work_orchestration/`
- Index: `index.json`
- Plan preview: call `compile_daily_plan_preview()` in Python or `GET /api/live-work/plan-preview` when Command Center is running.

## Connection to Phase 10+

- Snapshots are designed to feed **prepared context selection**, daily planning prompts, progress checks, and eventually the **Slack + Asana action loop** (Phase 10).
- `communication_queue_snapshot` is scaffolded empty with explicit `missing_sources` for live integrations.

## Future benchmark / chat prompts (documented only for Phase 9)

These natural prompts should eventually route to live-work flows (not all wired in Phase 9):

- `what should I focus on today?`
- `build my day plan`
- `what is blocking me?`
- `what did I miss today?`
- `replan my day`

## Related docs

- [`LIVE_WORK_ORCHESTRATION_SPEC.md`](LIVE_WORK_ORCHESTRATION_SPEC.md) — full planner design.
- [`LIVE_WORK_ORCHESTRATION_PHASES.md`](LIVE_WORK_ORCHESTRATION_PHASES.md) — roadmap table.
