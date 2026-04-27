# Growflow Canonical Runners

Purpose: define the canonical classification for Growflow automation scripts so we can clearly separate production runners from diagnostics and cleanup helpers.

## Classification Rules

- **Official tools**
  - Intended for repeatable business output.
  - Backed by docs and stable inputs/outputs.
  - Eligible for registry/tool exposure.
- **Scheduled jobs**
  - Official tools with expected recurring cadence (Task Scheduler/cron).
  - Must write durable outputs consumed by dashboards, sheets, or downstream scripts.
- **Manual diagnostics**
  - Investigative, ad-hoc, or one-off probes.
  - Usually prefixed with `_probe_`, `_scan_`, `_check_`, `_tmp_`, `_dump_`.
- **Deprecated helpers**
  - Migration/patch/test scripts no longer part of the canonical flow.
  - Candidates for archive later (do not delete yet).

## Source-of-Truth Inputs

- `Growflow/scripts/README.md` (canonical script intent and recommended commands).
- `ai-lab/registry/scripts.json` (current tool registry; note Growflow registry entry is `growflow_sales_today` under `Greg-Kylo` path).
- Existing Growflow script naming conventions in `Growflow/scripts/`.

## Canonical Classification

## 1) Official Tools

- `Growflow/allocate_stock_pool_by_brand.py`
- `Growflow/allocate_brand_pool_merit.py`
- `Growflow/scripts/build_projection_by_category_brand.py`
- `Growflow/scripts/build_projection_dashboard_google_sheet.py`
- `Growflow/scripts/export_projection_dashboard_layout.py`
- `Growflow/scripts/snapshot_dashboard_chart_layout.py`
- `Growflow/scripts/restore_dashboard_charts_from_layout_snapshot.py`
- `Growflow/scripts/list_projection_dashboard_charts.py`
- `Growflow/scripts/projection_dashboard_to_sheet.py`
- `Growflow/scripts/verify_projection_dashboard_sheet.py`
- `Growflow/scripts/build_transfer_receipts_db.py`
- `Growflow/scripts/export_transfer_receipt_units.py`
- `Growflow/scripts/transfer_sellout_by_brand_category.py`
- `Growflow/scripts/rank_mj_brands_profit_velocity_sheet.py`
- `Growflow/scripts/export_top15_mj_brands_30d_windows.py`
- `Growflow/scripts/export_brand_suppliers_to_sheet.py`
- `Growflow/scripts/introspect_growflow_schema.py`
- `Growflow/scripts/run_growflow_discovery_queries.py`

## 2) Scheduled Jobs (Recommended Canonical Cadence)

- **Daily**
  - `Growflow/scripts/build_projection_by_category_brand.py`
  - `Growflow/scripts/build_projection_dashboard_google_sheet.py`
  - `Growflow/scripts/rank_mj_brands_profit_velocity_sheet.py`
- **Every 1-3 days**
  - `Growflow/scripts/build_transfer_receipts_db.py`
  - `Growflow/scripts/export_transfer_receipt_units.py`
  - `Growflow/scripts/export_top15_mj_brands_30d_windows.py`
- **Weekly**
  - `Growflow/scripts/export_projection_dashboard_layout.py` (layout baseline snapshot)
  - `Growflow/scripts/introspect_growflow_schema.py --write-docs` (schema drift detection)

PowerShell launch wrappers intended for operator convenience:

- `Growflow/scripts/run_sales_today.ps1`
- `Growflow/scripts/run_stock_pool_allocation.ps1`
- `Growflow/scripts/run_export_dashboard_layout.ps1`

## 3) Manual Diagnostics

High-confidence diagnostic pattern group (manual-only unless promoted):

- `Growflow/scripts/_probe_`*
- `Growflow/scripts/_scan_`*
- `Growflow/scripts/_check_*`
- `Growflow/scripts/_tmp_*`
- `Growflow/scripts/_dump_*`
- `Growflow/scripts/_print_*`
- `Growflow/scripts/diag_vape_product_buckets.py`
- `Growflow/scripts/probe_orderitems_field_batches.py`
- `Growflow/scripts/probe_growflow_discovery_entities.py`
- `Growflow/scripts/query_sap_stix_velocity.py`
- `Growflow/scripts/worst_recovery_scan.py`
- `Growflow/scripts/top_allocation_velocity_scan.py`
- `Growflow/scripts/projection_efficiency_distribution_report.py`

## 4) Deprecated Helpers (Archive-Later Candidates)

These should be treated as non-canonical unless explicitly reactivated:

- `Growflow/scripts/_patch_ac10.py`
- `Growflow/scripts/_patch_iferror_test.py`
- `Growflow/scripts/_test_oi_product_where.py`
- `Growflow/scripts/_sellout_final.py`
- `Growflow/scripts/_fix_arctic_line.py`
- `Growflow/scripts/_orderitem_product_created.py`

## Registry and Exposure Notes

- Current ai-lab registry (`ai-lab/registry/scripts.json`) contains `growflow_sales_today`, but points to `Greg-Kylo/integrations/growflow/sales_today.py`, not `Growflow/scripts/run_sales_today.ps1`.
- For canonicalization, prefer registering one stable Growflow entrypoint per domain:
  - projection build/publish
  - transfer receipts ingest/export
  - ranking/export
  - schema/discovery checks

## Promotion Checklist (Manual -> Official)

Promote a script to **Official tool** only if all are true:

- Documented purpose and stable arguments.
- Deterministic output file or API side effect.
- Basic validation/test path exists.
- Clear owner and expected cadence.
- Approval requirement defined if state-changing.

