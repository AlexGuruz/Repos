# Phase 10 — ClickUp action loop (unified tasks + communication)

This phase aligns live work orchestration with **ClickUp** as the single external surface for **tasks** and **threaded communication**, replacing earlier Slack/Asana assumptions in docs and scaffolding.

## Principles (non-negotiable)

- **No automatic** ClickUp task creation, comments, or status updates from ai-lab code paths in this phase.
- Every external mutation is **proposal → queue → approval → execution** using existing approval patterns (`external-side-effect`, fail-closed metadata).
- **One active clarification** at a time in the local clarification queue; additional items stay `queued` until promoted.
- **No** desktop monitoring and **no** autonomous replanning here.

## Modules

| Module | Role |
|--------|------|
| `brain/live_work_orchestration/clickup_routing.py` | Deterministic `classify_work_category`, `map_category_to_clickup_list`, `route_task`, `route_comment`. |
| `brain/live_work_orchestration/clickup_queue.py` | Local `clickup_action_queue.json`, `clickup_clarification_queue.json`, append-only `clickup_action_log.jsonl`. |
| `brain/live_work_orchestration/clickup_actions.py` | Proposal builders and `generate_clickup_action_recommendations` (preview-only unless explicitly enqueueing in tests). |
| `brain/live_work_orchestration/compiler.py` | `compile_daily_plan_preview` merges ClickUp recommendations; exports `generate_clickup_action_recommendations`. |

## ClickUp list mapping (exact display names)

| Category key | List |
|--------------|------|
| `dev_core_work` | Dev / Core Work |
| `agent_clarifications` | Agent Clarifications |
| `agent_bills` | Agent Bills |
| `agent_ops` | Agent Ops |
| `agent_system_feedback` | Agent System Feedback |
| `company_finances` | Company Finances |
| `nugz_bills` | Nugz Bills |
| `nugz_orders` | Nugz Orders |

Clarifications for the one-question queue are always targeted at **Agent Clarifications** in proposals.

## Local queue files (gitignored)

- `state/live_work_orchestration/clickup_action_queue.json`
- `state/live_work_orchestration/clickup_clarification_queue.json`
- `state/live_work_orchestration/clickup_action_log.jsonl`

## Command Center (read-only)

- `GET /api/live-work/clickup-queue` — current action queue envelope.
- `GET /api/live-work/clickup-preview` — compiled ClickUp action recommendations (no execution).

## Tests

- `tests/test_clickup_action_loop.py` — routing, clarification discipline, proposals, compiler wiring, queue files.

## Related

- [`LIVE_WORK_ORCHESTRATION_SPEC.md`](LIVE_WORK_ORCHESTRATION_SPEC.md)
- [`LIVE_WORK_ORCHESTRATION_PHASES.md`](LIVE_WORK_ORCHESTRATION_PHASES.md)
