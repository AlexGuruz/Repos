# Live work orchestration — phased delivery

This document breaks migration of the ChatGPT **Daily Work Planner** into **ai-lab** into safe, reviewable phases. See [`LIVE_WORK_ORCHESTRATION_SPEC.md`](LIVE_WORK_ORCHESTRATION_SPEC.md) for the full behavior design.

| Phase | Scope |
|-------|--------|
| **9 — Foundation** | Data model (`brain/live_work_orchestration/schema.py`), read-only worker stubs, snapshot builders under `state/live_work_orchestration/`, read-only `compile_daily_plan_preview`, snapshot script, GET `/api/live-work/status` and `/api/live-work/plan-preview`, tests. **No** live desktop monitoring, **no** auto ClickUp/calendar writes, **no** autonomous replanning. |
| **10 — ClickUp action loop** | Deterministic ClickUp list routing, local **proposal** queues (`clickup_action_queue.json`, `clickup_clarification_queue.json`), one-question clarification discipline, `generate_clickup_action_recommendations`, read-only `GET /api/live-work/clickup-queue` and `GET /api/live-work/clickup-preview`. **No** automatic task creation, comments, or status updates—approval enforcement unchanged. See [`LIVE_WORK_CLICKUP_ACTION_LOOP.md`](LIVE_WORK_CLICKUP_ACTION_LOOP.md). |
| **11 — Local activity & progress** | Local activity signals (bounded, privacy-aware), progress monitoring tied to snapshots, richer `daily_progress_snapshot`. |
| **12 — Duration learning & replanning** | Historical completion data, adaptive estimates, governed replanning (still approval-heavy for destructive changes). |
| **13 — Calendar maintenance & full daily agent** | Calendar refresh/write policies behind approvals, scheduling sheet sync, full parity with the original planner loop while preserving prepared-context quality gates. |

Cross-cutting: **approval enforcement** and **prepared-context quality gates** are never weakened; new actions extend existing patterns rather than bypassing them.
