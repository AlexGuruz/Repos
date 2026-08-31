---
status: active
project: growflow
type: guide
job_id: growflow_retail
---

# Job — Growflow Retail Ops

## Goal

Fast “where are we / retail today” answers without GraphQL on the chat path and **without** triggering refresh.

## Read order (mandatory)

1. Grep / open `ai-lab/registry/growflow_read_surfaces/catalog.json` for the matching `surface_id`
2. `operator_growflow_status` / prepared `growflow_snapshot.json` (real KPIs — never formula docs as sales)
3. Else Desk tools: `operator_growflow_retail` | `_capital` | `_consignment` | `_projection` | `_bi_summary`
4. Else GET CC `/api/retail/*` or Growflow `:8791` / `/api/v1/*` (read only)
5. Declare freshness: fresh | stale_but_usable | degraded | unavailable
6. If `fixture_suspected` or trust.healthy=false — say so; do not claim store performance

## Do

- Use bounded metrics / summary_short
- Surface `known_blockers` and validation warnings
- Point humans to Retail tab / `Growflow/docs/GROWFLOW_OPS_PLATFORM.md` for deep dives

## Don't

- Call `POST /api/retail/refresh` from Operator Desk
- Treat snapshot as financial source of truth when stale/blocked/fixture
- Bypass Growflow trusted-output contracts when claiming verified metrics
- Invoke deprecated `growflow_sales_today` / Greg-Kylo sales_today.py
- Invoke `python -m company_bi.run_pipeline` (removed — use `build_company_bi_report.py`)

## Docs

- `ai-lab/registry/growflow_read_surfaces/README.md`
- `Growflow/docs/RETAIL_COMMAND_CENTER_RUNBOOK.md`
- `Growflow/docs/GROWFLOW_OPS_PLATFORM.md`
- `Growflow/docs/RETAIL_DASHBOARD_METRICS.md`
