# Memory contract

All files under `memory/` are JSON. Agents and orchestrator read/write per policy; no model training.

Canonical policy linkage:

- Approval behavior is enforced by `policy/autonomy_policy.yaml`.
- Worker/runtime identities are defined in `docs_source/WORKER_CURRENT.md`.

## trust_rules.json

Array of rules: scope, script_id (or tool_name), approval_required.

```json
[
  {
    "scope": "path_pattern",
    "path_pattern": "docs/**",
    "approval_required": false
  },
  {
    "scope": "path_pattern",
    "path_pattern": "src/**",
    "approval_required": true
  },
  {
    "scope": "script",
    "tool_name": "growflow_sales_today",
    "approval_required": false
  }
]
```

## preferences.json

User/organization preferences (timezone, format, reuse rules).

```json
{
  "timezone": "America/Chicago",
  "reuse_existing_scripts_first": true,
  "docs_auto_edit_paths": ["docs/**", "docs_source/**"]
}
```

## successful_workflows.json

History of intents, script used, args, result_ok — for learning and reuse.

```json
[
  {
    "intent": "sales_today",
    "tool_name": "growflow_sales_today",
    "args": {"date": "today"},
    "result_ok": true,
    "at": "2025-03-12T10:00:00Z"
  }
]
```

## project_state.json

Active/stalled projects, last updated, summary refs.

```json
{
  "projects": [
    {
      "name": "Greg-Kylo",
      "path": "repos_mirror/Greg-Kylo",
      "status": "active",
      "last_summary": "summaries/repos/greg-kylo.json"
    }
  ]
}
```

## workflow_rules.json, business_definitions.json

Optional. workflow_rules: learned workflow behavior. business_definitions: terms like "sales", "today", "active project" (key-value or short docs).
