# Live work orchestration — phased delivery

This document breaks migration of the ChatGPT **Daily Work Planner** into **ai-lab** into safe, reviewable phases. See [`LIVE_WORK_ORCHESTRATION_SPEC.md`](LIVE_WORK_ORCHESTRATION_SPEC.md) for the full behavior design.

| Phase | Scope |
|-------|--------|
| **9 — Foundation** | Data model (`brain/live_work_orchestration/schema.py`), read-only worker stubs, snapshot builders under `state/live_work_orchestration/`, read-only `compile_daily_plan_preview`, snapshot script, GET `/api/live-work/*`, tests. **No** live desktop monitoring, **no** auto-Asana/Slack/calendar writes, **no** autonomous replanning. |
| **10 — Slack + Asana action loop** | Approved outbound Slack (existing gated path), Asana task create/update via approval queue, mapping to canonical taxonomy; one-question clarification queue wired to real Slack reads where allowed. |
| **11 — Local activity & progress** | Local activity signals (bounded, privacy-aware), progress monitoring tied to snapshots, richer `daily_progress_snapshot`. |
| **12 — Duration learning & replanning** | Historical completion data, adaptive estimates, governed replanning (still approval-heavy for destructive changes). |
| **13 — Calendar maintenance & full daily agent** | Calendar refresh/write policies behind approvals, scheduling sheet sync, full parity with original planner loop while preserving prepared-context quality gates. |

Cross-cutting: **approval enforcement** and **prepared-context quality gates** are never weakened; new actions extend existing patterns rather than bypassing them.
