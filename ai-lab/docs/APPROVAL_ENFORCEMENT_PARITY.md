# Approval Enforcement Parity (Phase 1)

## Goal

Ensure state-changing actions cannot execute through any lane unless the same approval policy is applied.

## Entrypoints audited

- `brain/execution.py::run`
- `brain/orchestrator/main.py` (`intent == "run"`, `intent == "execute_proposal"`)
- `command-center/backend/routers/events.py::_execute_approved`
- `command-center/backend/services/supervisor_bridge.py::route_intent`
- `command-center/backend/routers/tools.py::tools_invoke`
- `registry/scripts.json`
- `brain/tool_registry.py`

## Policy model implemented

Shared enforcement module:
- `brain/approval_enforcement.py`
  - `evaluate_action(...)`
  - Returns a normalized decision:
    - `allowed`
    - `requires_approval`
    - `classification`
    - `reason`

Classification categories used:
- `read-only`
- `modifies-files-or-state`
- `external-side-effect`
- `system-control`

## Enforcement changes

1. **Execution boundary guard** (`brain/execution.py`)
   - `run(...)` now checks `evaluate_action(action="run_script", tool_name=...)`.
   - For state-changing tools:
     - approval is required (`approval_context={"approved": True}`).
     - missing metadata fails closed.

2. **Approved queue execution path** (`backend/routers/events.py`)
   - `_execute_approved` now passes `approval_context` to `execution.run`, so approved runs are explicit and auditable.

3. **Orchestrator "do it" parity** (`brain/orchestrator/main.py`)
   - `execute_proposal` now evaluates policy before action execution.
   - Approval-required proposals are blocked from direct `"do it"` execution and redirected to approval flow.

4. **Supervisor bridge parity checks** (`backend/services/supervisor_bridge.py`)
   - Added shared policy check per op.
   - Fails closed on policy mismatch between `ALLOWLISTED_READ_OPS` and approval requirements.

5. **Approval-required action set update** (`brain/orchestrator/approval_gate.py`)
   - Added controlled bridge ops to `APPROVAL_REQUIRED`:
     - `restart_service`, `modify_registry`, `write_sheet`, `run_approved`, `submit_approval`

6. **Tool metadata completeness** (`brain/tool_registry.py`)
   - Added metadata entries for:
     - `growflow_sales_today` (read-only)
     - `repo_full_rebuild_gate_a` (approval-required)
     - `repo_policy_migration_gate_c` (approval-required)
     - `rules_sheet_apps_script` (approval-required)

## Verification

New tests:
- `tests/test_approval_enforcement_parity.py`
  - direct `execution.run` cannot bypass approvals
  - missing metadata fails closed for state-changing script execution
  - read-only tool execution still works
  - orchestrator `"do it"` blocks approval-required proposal execution
- `command-center/backend/tests/test_supervisor_bridge_policy_parity.py`
  - controlled supervisor op queues approval
  - read-only supervisor op remains callable

## Remaining risks

- Scheduler/background processes still rely on action classification choices; parity now applies at runtime boundaries that execute script tools and controlled ops, but governance review should continue for newly-added ops.
- `WORKER_READ_OPS_EXTRA` can still widen read op surface; policy mismatch checks reduce risk but config governance remains critical.

## How to validate manually

1. Attempt unapproved execution of a state-changing registry tool -> should fail with approval policy block.
2. Approve queued action and execute via approvals endpoint -> should pass with explicit approval context.
3. Run read-only operation (`health`) through tools invoke -> should still work.
4. Try `"do it"` on approval-required proposal -> should return approval-gated response.

