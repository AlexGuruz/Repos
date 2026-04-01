# Policy contract

Policy files are the authority boundary for write/execute autonomy.

## autonomy_policy.yaml

Defines tiers T0–T4 and path/action scope.

- **T0:** Read-only
- **T1:** Draft only (no write to disk without approval)
- **T2:** Approval required for execution or edits
- **T3:** Auto-allowed in scoped zones (e.g. docs/**)
- **T4:** Managed autonomy in selected repos/actions

Structure:

```yaml
default_tier: T2
tiers:
  T0: read_only
  T1: draft_only
  T2: approval_required
  T3: auto_allowed_scoped
  T4: managed_autonomy
path_rules:
  - pattern: "docs/**"
    tier: T3
  - pattern: "docs_source/**"
    tier: T3
  - pattern: "src/**"
    tier: T2
  - pattern: "**"
    tier: T2
```

## allowlists.yaml / blocklists.yaml

- **allowlists:** Scripts, repos, or paths explicitly allowed to run or edit without approval (within tier).
- **blocklists:** Scripts, repos, or paths always blocked.

Location: `policy/allowlists.yaml`, `policy/blocklists.yaml`. Format: list of identifiers or path patterns; document in file header.
