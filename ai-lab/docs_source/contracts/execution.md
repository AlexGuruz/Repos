# Execution contract

This contract defines how orchestrator-approved actions are executed and logged.

## Interface

Orchestrator (or approval flow) calls:

```python
def run(tool_name: str, args: dict) -> RunResult
```

**RunResult** (dataclass or dict):

| Field     | Type   | Description        |
|----------|--------|--------------------|
| stdout   | str    | Standard output     |
| stderr   | str    | Standard error      |
| exit_code| int    | Process exit code   |
| duration | float  | Seconds             |
| success  | bool   | exit_code == 0      |

## Rules

- Execution layer **reads only** registry (scripts.json) and policy (autonomy_policy, allowlists, blocklists). It does not modify them.
- Validates `tool_name` against registry; validates path/action against policy before running.
- Runs script **locally** or **via SSH** per worker contract (worker.md). Path mapping: main vs worker paths per registry contract.
- Logs every run to `logs/execution_logs/` (tool_name, args, result, timestamp).
- Timeout and safe execution rules (e.g. max 300s); no ad hoc arbitrary execution.

## Handoff guarantees

- Command center and orchestrator may request execution, but execution policy checks remain mandatory.
- Worker-side execution must return structured output consumable by main for persistence and UI events.

## Location

Implementation: `brain/execution.py` or `execution/run.py` (single module or package). Invoked only by orchestrator after policy check (or after approval when required).
