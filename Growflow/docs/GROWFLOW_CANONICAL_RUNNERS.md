# Growflow Canonical Runners

Canonical runners currently integrated with validation gateway:

| Script | Metric ID | Template ID | Default Mode | Trusted Output Behavior |
| --- | --- | --- | --- | --- |
| `scripts/build_projection_by_category_brand.py` | `projection_by_category_brand` | `order_items_projection_buy_plan_v1` | `strict` | blocks output when validation fails |
| `scripts/build_transfer_receipts_db.py` | `transfer_receipts` | `transfer_receipts_accepted_v1` | `strict` | blocks DB load when validation fails |
| `scripts/export_transfer_receipt_units.py` | `transfer_units` | `transfer_units_from_receipts_v1` | `strict` | blocks JSONL write when validation fails |
| `scripts/rank_mj_brands_profit_velocity_sheet.py` | `brand_profit_velocity` | `order_items_brand_profit_velocity_v1` | `strict` | blocks sheet write when validation fails |
| `scripts/ingest_growflow_facts.py` | `growflow_fact_ingest` | (registry) | `strict` | fact store upsert |
| `scripts/build_retail_dashboard.py` | `retail_dashboard` | — | `strict` | blocks when sum validation fails |
| `scripts/run_platform_orchestrator.py` | `platform` | — | ops | writes `platform_status_latest.json` + events |
| `scripts/build_company_bi_report.py` | `company_bi` | — | — | `data/company_bi_report_latest.json` |

## Run Guidance

- use `--validation-mode strict` for dashboards, prepared context, AI answers, and par logic.
- use `--validation-mode warning` only for temporary troubleshooting runs.
- use `--validation-mode discovery` only for schema discovery metrics.

## Traceability

Each canonical run must produce:

1. raw response artifact under `state/raw_responses/{metric_id}/`
2. validation report under `state/validation_reports/{metric_id}/`
3. trusted output artifact under `state/trusted_outputs/{metric_id}/` (only when trusted)

No script should silently coerce invalid data into trusted output.
