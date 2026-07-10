# Live work orchestration — Daily Work Planner (local system spec)

This document preserves the **design** of the ChatGPT **Daily Work Planner** agent in a form suitable for implementation inside **ai-lab**: prepared context, workers, approvals, and Command Center. It is the **source of truth** for future phases.

---

## 1. Original source summary

The original agent is a **Daily Work Planner** connected to **Google Calendar**, **GitHub**, **Google Drive**, **Gmail**, **ClickUp** (as the unified tasks + communication surface), and a **scheduling sheet**. It:

- Collects **work demands** (tasks, requests, deadlines, maintenance signals).
- Collects **time and life constraints** (calendar, focus blocks, immovable commitments).
- **Combines** them into an execution structure: prioritized tasks, blocker routing, calendar guidance, and progress tracking.
- Uses **ClickUp** for clarification threads (one question at a time, routed to the **Agent Clarifications** list) and for **canonical task tracking** in workspace lists.
- Uses **memory files** for continuity and **safety rules** to avoid over-automation.

**Archival note:** This spec now includes a reconciled **archived instruction copy** (Appendix A) for the Daily Work Planner behavior contract used by local migration. Treat this file as canonical unless a newer upstream instruction set is intentionally versioned here.

---

## 2. Role and purpose

**Role:** Principal planner for a technical operator’s day.

**Purpose:**

1. Reduce cognitive load by surfacing **what matters today** vs noise.
2. Respect **time reality** (calendar, meetings, focus windows).
3. Route **blockers** to the right surface (ClickUp clarification or task, calendar move—**only** when policy and approvals allow).
4. Maintain **continuity** across days via structured memory and snapshots.
5. Never **silently** mutate external systems; **approval-gated** writes match ai-lab governance.

---

## 3. Three-stage planning architecture

### Stage A — Collect and summarize **work demands**

**Inputs (intake):**

- ClickUp tasks (assigned, due, lists, dependencies).
- GitHub PRs/issues/mentions (optional depth by repo).
- Email / Gmail threads flagged as actionable (bounded scan).
- Google Drive “inbox” docs or review requests (metadata-first).
- Repo activity (commits, stale README, CI) via `repo_pulse` / similar.
- Manual “drop a note here” inputs (ClickUp comment, sheet row, etc.).

**Outputs:**

- Normalized **WorkDemand** records: title, source, confidence, evidence, status.
- **PlanningInputGaps** where data is missing (do **not** guess).

### Stage B — Collect and summarize **time / life constraints**

**Inputs:**

- Google Calendar (today + horizon): meetings, personal blocks, travel.
- Known **shift** boundaries (work / personal) from config.
- System / on-call hints from `system_snapshot` or ops registry (read-only in early phases).

**Outputs:**

- **TimeConstraint** / **PlanningBlock** records.
- Explicit gaps (e.g. “calendar not connected”) — **no invented meetings**.

### Stage C — Combine into **execution structure**

**Outputs:**

- **PlannedTask** list ordered by: deadline → dependency → impact → energy fit (policy-tunable).
- **Blocker** list with **route_hint**: `clickup_clarify`, `clickup_task`, `calendar_move`, `defer`, `human_only`.
- **Calendar guidance** (where to place focus blocks; **writes** only with approval + calendar policy).
- **Progress tracking** model (**ProgressEvent**); replanning triggers deferred to Phase 12+.

**Local Phase 9–10 realization:** `compile_daily_plan_preview()` produces a **read-only** `DailyPlanPreview` with those sections plus optional `**proposed_clickup_actions`** and `**pending_clarifications**` (preview payloads only). No external ClickUp writes from the compiler.

---

## 4. Intake sources


| Source                                                                                                           | Phase 9                  | Later                                               |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------ | --------------------------------------------------- |
| Prepared context (`repo_pulse`, `project_agenda`, `personal_ops_snapshot`, `system_snapshot`, `worker_snapshot`) | Yes (read)               | Yes                                                 |
| Integration inventory (`state/integration_inventory/*`)                                                          | Gaps only if missing     | Yes                                                 |
| Google Calendar live API                                                                                         | No                       | Phase 10+                                           |
| Gmail / Drive                                                                                                    | No                       | Phase 10+                                           |
| GitHub API                                                                                                       | Partial via repo signals | Expand                                              |
| ClickUp API                                                                                                      | No                       | Phase 10+ (read intake stub; writes approval-gated) |
| Scheduling sheet                                                                                                 | No                       | Phase 13                                            |


---

## 5. Worker / adapter mapping


| Logical worker             | Responsibility                       | Phase 9                             |
| -------------------------- | ------------------------------------ | ----------------------------------- |
| **WorkDemandWorker**       | Aggregate actionable work            | Read-only probe of prepared context |
| **TimeConstraintWorker**   | Calendar + life blocks               | Read-only probe                     |
| **CalendarIntakeWorker**   | Calendar events                      | Count from snapshot only            |
| **RepoActivityWorker**     | Repo / pulse signals                 | Read `repo_pulse`                   |
| **LocalActivityWorker**    | Desktop / IDE activity               | **Stub** (Phase 11)                 |
| **EmailDriveIntakeWorker** | Gmail/Drive                          | **Stub**                            |
| **ClickUpIntakeWorker**    | ClickUp read (tasks/comments/status) | **Stub**                            |
| **ProgressMonitorWorker**  | Progress vs plan                     | Worker snapshot probe               |


Implementations live under `brain/live_work_orchestration/workers.py` (extend, do not bypass approvals).

---

## 6. ClickUp taxonomy and routing

**Canonical ClickUp lists (exact names in code — adjust to your org):**

- **Dev / Core Work** — dev, repos, AI work
- **Agent Clarifications** — questions, blockers (one-question clarification queue targets this list)
- **Agent Bills** — expenses
- **Agent Ops** — system ops
- **Agent System Feedback** — bugs/improvements
- **Company Finances** — financial data
- **Nugz Bills** — vendor payments
- **Nugz Orders** — orders

**Routing policy:**

- Every **WorkDemand** that becomes committed work maps to **one** ClickUp list (deterministic classifier in `clickup_routing.py`).
- **Blockers** that need tracking are represented as **proposed** ClickUp tasks or comments—local JSON queues hold drafts until approval; ClickUp remains system of record once synced manually or via an approved executor.
- **No** automatic ClickUp create/update in Phase 10 foundation. Use **approval queue** + tool registry metadata (`approval_required: true`).

---

## 7. ClickUp clarification and one-question queue

**Lists / topics:**

- **Agent Clarifications** — at most **one** active clarification item in the local queue; additional items stay queued.
- Other lists carry tasks and operational threads per section 6.

**One-question queue policy:**

- Questions are **specific** (deadline, priority, which repo, which meeting may move).
- Answers feed back into **PlanRevision** / next snapshot cycle—not instant silent calendar writes.

**Phase 9–10:** `communication_queue_snapshot` mirrors pending clarification rows from local state when present; `missing_sources` lists live ClickUp read until connected.

---

## 8. Calendar block policy

- **Read-first:** always refresh from API or snapshot before proposing moves.
- **Immutable** personal blocks (e.g. school pickup) are **hard constraints**—never suggest overwrites.
- **Work meetings:** propose **adjacent** focus blocks, not splitting across 15-minute crumbs unless user opts in.
- **Writes** (create/move/delete): **approval-gated** + audit log; Phase 9 has **zero** calendar writes.

---

## 9. Scheduling sheet policy

- Sheet is a **human-visible schedule** of intent (themes per day, big rocks)—not a second calendar of truth.
- Rows: date, theme, top 3 outcomes, **blockers**, **energy** note.
- Automation may **propose** row updates (Phase 13+); **never** overwrite without approval.
- Phase 9: optional read of sheet export path from config—if missing, record gap only.

---

## 10. Progress check and replanning policy

**Progress check:**

- Compare **PlannedTask** completion vs **ProgressEvent** (from activity, ClickUp state when wired, manual check-ins).
- Surface “**at risk**” tasks before end of **during shift** window.

**Replanning (Phase 12+):**

- Triggers: slipped task, new urgent demand, failed blocker resolution.
- **Autonomous** replanning is **off** until policy + UX exist; human or explicit command initiates replan.
- Any replan that **shrinks** commitments or **moves** external meetings requires **approval**.

---

## 11. Memory / state files


| Artifact                                                          | Role                                                 |
| ----------------------------------------------------------------- | ---------------------------------------------------- |
| `state/live_work_orchestration/work_demand_snapshot.json`         | Latest normalized demands                            |
| `state/live_work_orchestration/time_constraints_snapshot.json`    | Constraints / calendar slim                          |
| `state/live_work_orchestration/daily_progress_snapshot.json`      | Progress events / probes                             |
| `state/live_work_orchestration/communication_queue_snapshot.json` | ClickUp clarification queue mirror                   |
| `state/live_work_orchestration/clickup_action_snapshot.json`      | Optional mirror of `clickup_action_queue.json`       |
| `state/live_work_orchestration/clickup_action_queue.json`         | Proposed actions (local; not committed by default)   |
| `state/live_work_orchestration/clickup_clarification_queue.json`  | One-question clarification queue                     |
| `state/live_work_orchestration/clickup_action_log.jsonl`          | Append-only local audit of queue events              |
| `state/live_work_orchestration/planning_gaps_snapshot.json`       | Missing inputs                                       |
| `state/live_work_orchestration/index.json`                        | Index of snapshots                                   |
| Future: `memory/live_work/*.json`                                 | Longer-horizon preferences (bounded, redact secrets) |


**Rules:** no secrets in JSON; redact tokens; prefer references to vault paths.

---

## 12. Safety rules

1. **No surprise writes** to ClickUp, Calendar, Gmail, or Drive.
2. **No** customer-facing outbound comms from this planner path unless a **separate** consent workflow exists.
3. **Prepared-context quality gates** stay on: stale or low-confidence snapshots produce **warnings**, not fabricated facts.
4. **One-question clarification** discipline: no walls of text; no parallel ambiguous threads.
5. **Evidence-first:** every `WorkDemand` / `Blocker` should carry `evidence` or explicit low-confidence flag.
6. **Kill switch:** disabling `live_work` workers leaves core chat and prepared context unaffected.

---

## 13. Local migration plan

1. **Phase 9 (done in code):** schemas, stubs, snapshots, compiler preview, script, GET APIs, tests.
2. **Wire prompts** (optional): route benchmark phrases to snapshot + preview in orchestrator (later).
3. **Phase 10:** ClickUp routing + local action/clarification queues + read-only Command Center endpoints; extend `communication_queue_snapshot` and optional `clickup_action_snapshot`. **No** auto posts or task mutations—approval pipeline only.
4. **Phase 11:** `LocalActivityWorker` real collectors (privacy budget).
5. **Phase 12–13:** duration learning, calendar/sheet maintenance, full daily loop.

**Portability:** keep adapter interfaces small; swap ChatGPT tool plugins for `brain` workers + `scripts`.

---

## 14. Future phases roadmap

See `[LIVE_WORK_ORCHESTRATION_PHASES.md](LIVE_WORK_ORCHESTRATION_PHASES.md)`.

---

## Appendix A — Archived Daily Work Planner instruction copy (reconciled)

This appendix is the preserved behavior contract for the original planner, normalized for local ai-lab implementation so Phase 10+ work can proceed without ambiguity.

### A.1 Role

You are the **Daily Work Planner**. Your job is to convert incoming obligations plus constraints into a practical daily execution structure while minimizing context-switching and preserving human control over external writes.

### A.2 Core operating sequence (must follow)

1. **Collect and summarize work demands** from trusted sources.
2. **Collect and summarize time/life constraints** (calendar and fixed boundaries).
3. **Combine into execution structure** with:
  - Today
  - Before shift
  - During shift
  - After shift
  - Top priorities
  - Constraints
  - Risks to watch
  - A good day looks like
4. Surface blockers and route them through approved channels (ClickUp clarification queue and task lists, calendar guidance) according to policy.

### A.3 Source hierarchy and confidence behavior

- Prefer concrete evidence from connected systems and prepared snapshots.
- Record confidence per synthesized item.
- If a source is missing or stale, report a **gap** explicitly and avoid speculation.
- Do not fabricate meetings, tasks, owners, deadlines, or completion claims.

### A.4 ClickUp task and list routing contract

- ClickUp is the canonical task and threaded-communication surface for committed execution work.
- Map each committed `WorkDemand` to one list in the workspace taxonomy (see section 6).
- Blockers that need persistence should be represented as ClickUp tasks or threaded comments with dependency context.
- Avoid duplicate shadow systems for ownership tracking.
- Any create/update action must remain approval-gated in local ai-lab flows.

### A.5 ClickUp clarification contract (one-question queue)

- Clarifications use the **Agent Clarifications** list (and the local one-question queue for ordering).
- Ask **one clarification question at a time** when ambiguity blocks safe planning.
- Queue questions in order; avoid parallel unresolved asks.
- Questions should be concrete and answerable (priority, due date, owner, sequencing, constraints).
- Outbound ClickUp comments or tasks must use approved/gated execution paths.

### A.6 Calendar policy

- Refresh/confirm calendar constraints before proposing schedule guidance.
- Treat immovable personal constraints as hard boundaries.
- Produce block guidance in read-only form unless calendar mutations are explicitly approved.
- No silent rewrites or auto-reschedules.

### A.7 Scheduling-sheet policy

- Scheduling sheet is a human-visible planning surface, not an autonomous source of truth.
- Keep entries aligned with current plan and constraints.
- Do not auto-overwrite sheet data without explicit approval and provenance.

### A.8 Memory/state model

- Persist planning artifacts as structured state files/snapshots.
- Store evidence references and confidence, not secrets.
- Preserve revision context (`PlanRevision`) for explainability.

### A.9 Safety and governance rules

- Never bypass approval enforcement for mutating actions.
- Never weaken prepared-context quality gates.
- Never run customer-alert or unrelated automation from this planner role.
- Keep high-risk automation disabled until explicitly phased in.

### A.10 Portability and migration rules

- Preserve planner semantics independent of provider-specific APIs.
- Keep adapters thin; planner logic stays in local policy/compiler layers.
- Add capabilities by phase with tests and docs, not ad hoc behavior changes.

### A.11 Explicitly deferred from foundation

- Autonomous replanning loops
- Live desktop monitoring
- Unapproved ClickUp/calendar writes
- Full scheduling-sheet sync writes

These remain deferred until later phases with approval-aware wiring.

---

## Appendix B — `DailyPlanPreview` section meanings


| Section                   | Intent                                                  |
| ------------------------- | ------------------------------------------------------- |
| **Today**                 | One-line synthesis of the day’s theme from top demands. |
| **Before shift**          | Prep that fits before core working hours.               |
| **During shift**          | Execution focus tied to constraints.                    |
| **After shift**           | Wind-down: notes, tomorrow seed, low-energy tasks.      |
| **Top priorities**        | Bulleted ordered list.                                  |
| **Constraints**           | Calendar + life + system limits.                        |
| **Risks to watch**        | Gaps, missing data, stale snapshots, dependency risk.   |
| **A good day looks like** | Human-readable success criteria—not metrics gaming.     |
