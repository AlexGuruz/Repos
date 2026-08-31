"""Tools documentation."""

# Tool contract (MVP)

| Logical tool_id | Module | Scope | Notes |
|-----------------|--------|-------|-------|
| operator_growflow_status | growflow_ops.get_growflow_status | read_only | Snapshot then GET; never refresh |
| operator_growflow_retail | growflow_ops.get_growflow_retail | read_only | Bounded dashboard |
| operator_growflow_capital | growflow_ops.get_growflow_capital | read_only | Capital JSON via API |
| operator_growflow_consignment | growflow_ops.get_growflow_consignment | read_only | Consignment JSON via API |
| operator_growflow_projection | growflow_ops.get_growflow_projection | read_only | EOD projection |
| operator_growflow_bi_summary | growflow_ops.get_growflow_bi_summary | read_only | Company BI report |
| operator_growflow_catalog | growflow_ops.get_growflow_catalog | read_only | read_surfaces catalog |
| operator_email_digest | email_ops.fetch_unread_digest | read_only | Redacts from/snippet; caches TTL |
| operator_email_create_draft | email_ops.propose_draft_reply | write_gated | Requires scripts.json entry before execute |
| operator_machine_list_pending | machine_ops.list_pending | read_only | brain pending.json |
| operator_machine_submit_action | machine_ops.propose_allowlisted_action | write_gated | scripts.json allowlist only |
| operator_repo_map | repo_ops.get_repo_map_summary | read_only | governance registry |

Ask-time index: `ai-lab/registry/growflow_read_surfaces/catalog.json`.

Executable `tool_name` values for approve→run must exist in `ai-lab/registry/scripts.json`.
