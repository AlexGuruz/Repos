# Growflow read surfaces (local AI SSOT)

Prefer this catalog over grepping random scripts or calling GraphQL.

## Rule

1. Open [`catalog.json`](catalog.json) and pick a `surface_id`.
2. Use only `ask_time_reads` (prepared snapshot → latest JSON → HTTP GET → Operator Desk tools).
3. Never run `build_time_only` paths or anything in `forbidden_at_ask_time` from chat/Operator Desk.
4. Writes go through the brain approval queue + [`../scripts.json`](../scripts.json) allowlist only.

## Operator Desk

- `operator_growflow_status` — platform health + bounded KPIs
- `operator_growflow_retail` / `_capital` / `_consignment` / `_projection` / `_bi_summary`
- `operator_growflow_catalog` — returns this catalog summary

## Human docs

- `Growflow/docs/GROWFLOW_CANONICAL_RUNNERS.md`
- `Growflow/docs/RETAIL_COMMAND_CENTER_RUNBOOK.md`
- `Growflow/docs/GROWFLOW_OPS_PLATFORM.md`
