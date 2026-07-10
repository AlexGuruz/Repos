# Live work — external action loop (ClickUp)

**Superseded naming:** earlier drafts described a Slack + Asana loop. The supported design is now **ClickUp-only** for unified tasks and communication.

Authoritative detail: **[`LIVE_WORK_CLICKUP_ACTION_LOOP.md`](LIVE_WORK_CLICKUP_ACTION_LOOP.md)**.

## Summary

- **Proposals** are built in `brain/live_work_orchestration/clickup_actions.py` (`build_clickup_*_proposal`, `generate_clickup_action_recommendations`).
- **Queues** live under `state/live_work_orchestration/` as JSON / JSONL (`clickup_action_queue.json`, `clickup_clarification_queue.json`, `clickup_action_log.jsonl`).
- **Command Center (read-only):**
  - `GET /api/live-work/clickup-queue`
  - `GET /api/live-work/clickup-preview`

No automatic ClickUp mutations: execution remains behind your existing approval flows.
