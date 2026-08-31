# Script inventory / disposition (Growflow Ops Platform)

One-off probes live under `scripts/_archive/` after Phase 4 hygiene.
Canonical runners remain in `scripts/` (see `docs/GROWFLOW_CANONICAL_RUNNERS.md` and `docs/GROWFLOW_OPS_PLATFORM.md`).

## KEEP (canonical)

- ingest_growflow_facts.py
- build_retail_dashboard.py / build_retail_capital.py / build_retail_consignment.py
- reconcile_retail_dashboard.py / run_retail_release_gate.py / run_platform_release_gate.py
- run_platform_orchestrator.py / build_platform_status.py
- build_projection_by_category_brand.py / build_transfer_receipts_db.py
- consignment_daily_allocation.py / register_close_taxes_sheet.py
- run_daily_sales_projection.py / build_company_bi_report.py
- country_cannabis_infused_singles_track.py (+ blunts)

## ARCHIVE

All `scripts/_*.py` one-offs (probes, letter hacks, cartel experimental CLIs).

## LEGACY (do not extend)

Repo-root `allocate_*.py`, `inventory_*.py` — prefer capital tab / buy-plan canonical runner + fact store.
