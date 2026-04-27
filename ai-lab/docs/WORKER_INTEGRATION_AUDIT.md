# Worker Integration Audit

## Worker health path

- Primary function: `brain/worker_health.py::get_worker_health_snapshot`.
- Interactive budget path: `timeout_budget_ms=2000` used by:
  - `brain/orchestrator/main.py` (`intent == "worker_health"`)
  - `command-center/backend/routers/workers.py` (`/api/workers/health*`)
- Services checked:
  - worker assistant (`check_worker_assistant`)
  - n8n (`check_worker_n8n`)
  - ollama (`check_worker_ollama`)
- Tunnel status:
  - `brain/worker_tunnel.py::get_tunnel_status`
- Cached last known status:
  - in-memory `_LAST_STATUS_BY_WORKER` + `last_known_status` field in snapshots.

## Worker assistant / Ollama / n8n path

| Capability | Code path | Endpoint/path assumption | Timeout behavior | Status |
|---|---|---|---|---|
| Worker assistant health/index/retrieve/promote | `brain/worker_clients.py` + `brain/worker_services.py` | worker assistant URL from env/registry | per-call timeout args + bridge budgets | wired |
| n8n trigger | `worker_n8n_trigger` | `POST {worker_n8n_url}/webhook/{workflow_id}` | standard worker timeout | partial (webhook-shape assumption) |
| Ollama reachability | `worker_ollama_tags` | `{ollama_base}/api/tags` | standard health timeout | wired |
| Tunnel reachability | `worker_tunnel.get_tunnel_status` | local forwarded ports (default `8765/5678/11434`) | bounded with total timeout | wired |

## Which orchestrator intents can call worker

- `worker_health`
- `worker_index`
- `worker_retrieve`
- `trigger_workflow` -> proposal -> `execute_proposal` -> `worker_n8n_trigger`
- `run_agent` repo cartographer path can use SSH worker depending on configuration (`brain/ssh_worker.py`).

## Prompts that should not call worker (and current control)

- Greetings/openers: early return in `brain/orchestrator/main.py` greeting logic.
- Common status/planning/repo-summary prompts: routed toward local/prepared-context paths (`router.py`, `orchestrator/routing_policy.py`, `prepared_context/loader.py`).
- Regression test exists: `tests/test_integration_flows.py::test_non_worker_questions_do_not_block_on_worker_health`.

## Risks

- Two worker invocation lanes (orchestrator direct vs supervisor bridge) can drift in policy and timeout handling.
- Last-known cache is process-memory only.
- n8n webhook assumptions may not hold in all deployments.

