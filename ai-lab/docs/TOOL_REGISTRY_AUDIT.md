# Tool Registry Audit

## Registry layers

1. **Executable script registry**: `registry/scripts.json` consumed by `brain/execution.py::run`.
2. **Tool metadata registry**: `brain/tool_registry.py` (default metadata list, optional `ops/registry/tools.yaml` override).
3. **Supervisor bridge ops**: `command-center/backend/services/supervisor_bridge.py` (`ALLOWLISTED_READ_OPS`, `CONTROLLED_OPS`).

## Orchestrator-callable actions (effective)

| Tool/Action | Implementation | Wrapper path | Approval requirement | Allowlist eligibility | Input schema | Output schema | Command Center exposed | Tested |
|---|---|---|---|---|---|---|---|---|
| `growflow_sales_today` | `integrations/growflow/sales_today.py` (via registry path) | `brain/execution.py::run` | Depends on caller intent (`run`) | N/A | CLI args from `router` params | `RunResult` (`stdout/stderr/exit`) | Chat route (`/api/chat*`) | partial |
| `repo_search` | `brain/repo_search.py` | orchestrator direct branch | no (`AUTO_ALLOWED`) | yes | query string | list of matches in reply text | Chat UI | yes (`tests/test_router.py`) |
| `repo_cartographer` (`run_agent`) | `agents/repo_cartographer/main.py` (indirect) | orchestrator `run_agent` branch | generally no | yes | repo_name | summary artifact path + text | Chat UI | partial |
| `worker_health` | `brain/worker_health.py` | orchestrator direct + workers API | no | yes | worker name/budget | `WorkerHealthSnapshot` dict | `/api/workers/health`, chat | yes (`tests/test_worker_health.py`) |
| `worker_assistant_index_repo` | `brain/worker_clients.py::worker_assistant_index_repo` | orchestrator `worker_index` | no (intent-specific) | N/A | repo_path | normalized dict | chat intent | partial |
| `worker_assistant_retrieve` | `brain/worker_clients.py::worker_assistant_retrieve` | orchestrator `worker_retrieve` | no (intent-specific) | N/A | query | normalized dict | chat intent | partial |
| `worker_n8n_trigger` | `brain/worker_clients.py::worker_n8n_trigger` | proposal execute path | should be approval-gated | N/A | workflow + payload | normalized dict | chat intent | partial |
| `run_approved` | supervisor bridge execution stub | `supervisor_bridge.execute_approved` | yes (`CONTROLLED_OPS`) | no | payload object | status object | approvals panel | partial |
| `submit_approval` | supervisor bridge | `supervisor_bridge.route_intent` | yes (`CONTROLLED_OPS`) | no | payload object | APR event | Tools invoke API | partial |
| `write_sheet` | supervisor bridge | `supervisor_bridge.route_intent` | yes | no | payload object | APR event | Tools invoke API | partial |
| `restart_service` | supervisor bridge | `supervisor_bridge.route_intent` | yes + never permanent | no | payload object | APR event | Tools invoke API | partial |
| `modify_registry` | supervisor bridge | `supervisor_bridge.route_intent` | yes + never permanent | no | payload object | APR event | Tools invoke API | partial |

## Metadata registry (`brain/tool_registry.py`)

Default metadata tools:
- `repo_search`
- `scan_repo`
- `run_script`
- `set_process_priority`
- `n8n_trigger`
- `worker_n8n_trigger`

Fields available:
- `name`, `description`, `args`, `side_effects`, `approval_required`, `risk_level`, `output_shape`

## Approval + allowlist mapping

- Approval gate: `brain/orchestrator/approval_gate.py`
  - `AUTO_ALLOWED`: read/search/scan/status-style actions.
  - `APPROVAL_REQUIRED`: write/patch/notify/resource-control/n8n triggers.
- Permanent allowlist: `brain/permanent_allowlist.py`
  - persistent rules in `state/permanent_approvals.json`
  - hard denylist for permanent approvals includes `restart_service`, `modify_registry`.

## Gaps

- `brain/execution.py::run` executes registry scripts without explicit approval-gate check at runtime boundary.
- `ops/registry/tools.yaml` override path exists but not present by default (metadata mostly in code defaults).
- Supervisor `execute_approved` is still documented as wrapper-stub area (limited real action execution semantics).

