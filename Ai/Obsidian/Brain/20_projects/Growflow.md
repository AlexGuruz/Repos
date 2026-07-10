---
project_name: Growflow
type: core-project
status: active
created: 2026-02-06
updated: 2026-05-28
---

# Growflow

## Overview
GrowFlow integration — expense tracking (NUGZ EXPENSES col 10), sales/OrderItems export for COG (planned).

## Project Notes
<!-- Add links to project-specific notes as they are created -->
- [[20_projects/Growflow/company_bi|company_bi]]
- [[20_projects/Growflow/config|config]]
- [[20_projects/Growflow/contracts|contracts]]
- [[20_projects/Growflow/data|data]]
- [[20_projects/Growflow/docs|docs]]
- [[20_projects/Growflow/exports|exports]]
- [[20_projects/Growflow/lib|lib]]
- [[20_projects/Growflow/scripts|scripts]]
- [[20_projects/Growflow/state|state]]
- [[20_projects/Growflow/tests|tests]]
- [[20_projects/Growflow/tools|tools]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Repo Structure






<!-- REPO_STRUCTURE_START -->
|-- company_bi
|   |-- config
|   |   |-- categories.yaml
|   |   +-- sources.yaml
|   |-- db
|   |   |-- 001_growflow_order_items.sql
|   |   |-- 001_growflow_order_items_pg.sql
|   |   +-- growflow.db
|   |-- docs
|   |   |-- AUTOMATION_AND_VALIDATION.md
|   |   |-- BI_BUSINESS_SUMMARY.md
|   |   |-- CATEGORY_RULES_HOWTO.md
|   |   |-- INVENTORY_DB_INGEST.md
|   |   |-- LABOR_OVERHEAD_AUDIT.md
|   |   |-- LABOR_SOURCE_IMPACT.md
|   |   |-- LABOR_SOURCE_TRACE.md
|   |   |-- MARGIN_METHOD_AUDIT.md
|   |   |-- other_expense_analysis.csv
|   |   |-- OTHER_EXPENSE_AUDIT.md
|   |   |-- PHASE2_SYSTEM_AUDIT.md
|   |   +-- RECONCILIATION_DIAGNOSTIC.md
|   |-- lib
|   |   |-- __init__.py
|   |   |-- anomaly.py
|   |   |-- categorization.py
|   |   |-- labor_source.py
|   |   |-- metrics.py
|   |   |-- normalization.py
|   |   |-- reconcile.py
|   |   |-- report.py
|   |   |-- sources.py
|   |   +-- validation.py
|   |-- output
|   |   |-- anomalies.csv
|   |   |-- dashboard.csv
|   |   |-- expense_category.csv
|   |   |-- inventory_analysis.csv
|   |   |-- labor.csv
|   |   |-- margin.csv
|   |   |-- reconciliation.csv
|   |   +-- recurring_bills.csv
|   |-- scripts
|   |   |-- __init__.py
|   |   |-- audit_other_expenses.py
|   |   |-- ingest_growflow_to_db.py
|   |   |-- list_rent_matches.py
|   |   |-- list_uncategorized_and_review.py
|   |   |-- monthly_run.py
|   |   |-- payroll_last_period.py
|   |   |-- recurring_bills_summary.py
|   |   +-- suggest_category_rules.py
|   |-- __init__.py
|   |-- CATEGORIZATION.md
|   |-- CHANGELOG_PHASE2.md
|   |-- CONFIDENCE_GAPS.md
|   |-- DESIGN.md
|   |-- FIRST_REPORT.md
|   |-- METRICS.md
|   |-- README.md
|   +-- requirements.txt
|-- config
|   |-- brand_category_normalization.json
|   |-- config.example.yaml
|   |-- config.yaml
|   |-- dashboard_sheets.env.example
|   |-- query_templates.yaml
|   +-- sku_lookup.csv
|-- contracts
|   |-- brand_profit_velocity.json
|   |-- inventory_on_hand.json
|   |-- projection_by_category_brand.json
|   |-- sales_by_brand_category.json
|   |-- sales_today.json
|   |-- schema_discovery.json
|   |-- transfer_receipts.json
|   +-- transfer_units.json
|-- data
|   |-- .gitkeep
|   |-- brand_daily_14d_projection.csv
|   |-- brand_daily_14d_projection_coverage.csv
|   |-- brand_merit_12m.csv
|   |-- brand_merit_12m_run.log
|   |-- brand_merit_90d_formats_only.csv
|   |-- brand_merit_pool_verify.csv
|   |-- growflow_schema_introspection.json
|   |-- projection_18k_summary.txt
|   |-- projection_by_category_brand.md
|   |-- projection_by_category_brand_16k_receiptaware_21d.md
|   |-- projection_by_category_brand_16k_receiptaware_21d_layer2.csv
|   |-- projection_by_category_brand_16k_receiptaware_30d.md
|   |-- projection_by_category_brand_16k_receiptaware_30d_layer2.csv
|   |-- projection_by_category_brand_16k_receiptaware_30d_tuned.md
|   |-- projection_by_category_brand_16k_receiptaware_30d_tuned_layer2.csv
|   |-- projection_by_category_brand_layer2_recovery.csv
|   |-- projection_by_category_brand_monday_po.md
|   |-- projection_by_category_brand_monday_po_layer2.csv
|   |-- projection_run_latest.log
|   |-- projection_winner_check.md
|   |-- projection_winner_check_layer2.csv
|   |-- stock_pool_by_brand.csv
|   |-- supplier_high_solutions_category_pace.csv
|   |-- supplier_high_solutions_category_pace_30d_excl5.csv
|   |-- transfer_receipt_units.jsonl
|   +-- transfer_receipts.db
|-- docs
|   |-- DASHBOARD_FILTER_DEBUG_LOG.md
|   |-- GROWFLOW_AI_LAB_INTEGRATION_TODO.md
|   |-- GROWFLOW_API.md
|   |-- GROWFLOW_API_SCHEMA_RESPONSE_MATRIX.md
|   |-- GROWFLOW_CANONICAL_RUNNERS.md
|   |-- GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md
|   |-- GROWFLOW_DATA_VALIDATION_GATEWAY.md
|   |-- GROWFLOW_NEXT_DATA_REQUEST.md
|   |-- GROWFLOW_PLANNER_DATA_MAPPING.md
|   |-- GROWFLOW_PLANNER_SCENARIO_CONTROLS.md
|   |-- GROWFLOW_RETAIL_SCHEMA_MAP.md
|   |-- GROWFLOW_SCHEMA_CONFIDENCE_PLAN.md
|   |-- INVENTORY_VS_SALES.md
|   |-- RECREATION_SPEC.md
|   +-- SETUP.md
|-- exports
|   |-- .gitkeep
|   |-- dashboard_charts.json
|   |-- projection_dashboard_layout_baseline.json
|   |-- projection_dashboard_layout_snapshot.json
|   |-- top15_mj_brands_30d_x13_windows_20260411_1938.csv
|   |-- top15_mj_brands_30d_x13_windows_20260411_1938.json
|   |-- top15_mj_brands_30d_x13_windows_20260411_2118_curated_no_prepack_flower_no_accessory_skus_no_710_empire.csv
|   |-- top15_mj_brands_30d_x13_windows_20260411_2118_curated_no_prepack_flower_no_accessory_skus_no_710_empire.json
|   |-- top15_mj_brands_30d_x13_windows_20260411_2204_curated_no_prepack_flower_no_bulk_flower_no_accessory_skus_no_710_empire.csv
|   |-- top15_mj_brands_30d_x13_windows_20260411_2204_curated_no_prepack_flower_no_bulk_flower_no_accessory_skus_no_710_empire.json
|   |-- top15_mj_brands_30d_x2_windows_20260411_1916.csv
|   |-- top15_mj_brands_30d_x2_windows_20260411_1916.json
|   |-- top15_mj_brands_30d_x2_windows_20260411_2106_curated_no_prepack_flower_no_accessory_skus_no_710_empire.csv
|   |-- top15_mj_brands_30d_x2_windows_20260411_2106_curated_no_prepack_flower_no_accessory_skus_no_710_empire.json
|   |-- top5_mj_brands_30d_x1_windows_20260411_2143_curated_no_prepack_flower_no_bulk_flower_no_accessory_skus_no_710_empire.csv
|   +-- top5_mj_brands_30d_x1_windows_20260411_2143_curated_no_prepack_flower_no_bulk_flower_no_accessory_skus_no_710_empire.json
|-- lib
|   |-- __init__.py
|   |-- allocate_stock_pool.py
|   |-- brand_category_normalize.py
|   |-- brand_daily_sales.py
|   |-- brand_merit_pool.py
|   |-- cartel_7pk_names.py
|   |-- dashboard_sheets_env.py
|   |-- data_validation_gateway.py
|   |-- growflow_graphql.py
|   |-- growflow_planner_metadata.py
|   |-- growflow_queries.py
|   |-- product_landed_cost_sqlite.py
|   |-- projection_dashboard_config.py
|   |-- projection_dashboard_sheet_dynamic.py
|   |-- projection_dashboard_sheet_rebuilt.py
|   |-- projection_exec_kpis.py
|   |-- projection_layer2_recovery.py
|   |-- projection_sku_reorder.py
|   |-- schema_verification.py
|   |-- stashbox_sheets_auth.py
|   +-- transfer_receipt_export.py
|-- scripts
|   |-- growflow_discovery_queries
|   |   |-- discover_findBrands.graphql
|   |   |-- discover_findOrderItems.graphql
|   |   |-- discover_findPackages.graphql
|   |   |-- discover_findProductCategories.graphql
|   |   |-- discover_findProducts.graphql
|   |   |-- discover_findStores.graphql
|   |   |-- discover_findTransactions.graphql
|   |   |-- discover_findTransfers.graphql
|   |   +-- README.md
|   |-- _cartel_7pk_first_receipt_sellout.py
|   |-- _cartel_7pk_sellout_projection.py
|   |-- _cartel_preroll_velocity_budget.py
|   |-- _check_fast_row.py
|   |-- _dashboard_audit_once.py
|   |-- _dump_sheet_formulas.py
|   |-- _find_pkg_by_sku.py
|   |-- _fix_arctic_line.py
|   |-- _last_accepted_transfer.py
|   |-- _orderitem_product_created.py
|   |-- _patch_ac10.py
|   |-- _patch_iferror_test.py
|   |-- _print_pool_breakdown.py
|   |-- _probe_cartel_origin.py
|   |-- _probe_introspection.py
|   |-- _probe_one_pkg.py
|   |-- _probe_pkg_fields.py
|   |-- _probe_pkg_fields2.py
|   |-- _probe_sheet_funcs.py
|   |-- _query_arctic_disposable_inventory.py
|   |-- _sales_today.py
|   |-- _scan_orderitem_names.py
|   |-- _scan_package_names.py
|   |-- _sellout_final.py
|   |-- _tax_savings_plan.py
|   |-- _tax_setaside_period.py
|   |-- _test_oi_product_where.py
|   |-- _tmp_query_transfers_db.py
|   |-- _weekday_sales_avg.py
|   |-- build_projection_by_category_brand.py
|   |-- build_projection_dashboard_google_sheet.py
|   |-- build_transfer_receipts_db.py
|   |-- build_trip_sheet_google_doc.py
|   |-- cartel_7pk_portfolio_projection.py
|   |-- complete_18k_projection.py
|   |-- diag_vape_product_buckets.py
|   |-- export_brand_suppliers_to_sheet.py
|   |-- export_projection_dashboard_layout.py
|   |-- export_top15_mj_brands_30d_windows.py
|   |-- export_transfer_receipt_units.py
|   |-- introspect_growflow_schema.py
|   |-- list_projection_dashboard_charts.py
|   |-- probe_growflow_discovery_entities.py
|   |-- probe_orderitems_field_batches.py
|   |-- projection_dashboard_to_sheet.py
|   |-- projection_efficiency_distribution_report.py
|   |-- query_sap_stix_velocity.py
|   |-- rank_mj_brands_profit_velocity_sheet.py
|   |-- README.md
|   |-- restore_dashboard_charts_from_layout_snapshot.py
|   |-- run_export_dashboard_layout.ps1
|   |-- run_growflow_discovery_queries.py
|   |-- run_sales_today.ps1
|   |-- run_stock_pool_allocation.ps1
|   |-- snapshot_dashboard_chart_layout.py
|   |-- supplier_sales_pace_by_category.py
|   |-- top_allocation_velocity_scan.py
|   |-- transfer_sellout_by_brand_category.py
|   |-- validate_cartel_7pk_projection.py
|   |-- validate_projection_layer2_csv.py
|   |-- verify_projection_dashboard_sheet.py
|   +-- worst_recovery_scan.py
|-- state
|   |-- raw_responses
|   |   |-- projection_by_category_brand
|   |   |   |-- 20260430T021736_7d6c8a03.json
|   |   |   |-- 20260430T021843_d7464129.json
|   |   |   |-- 20260430T154524_745b58a9.json
|   |   |   |-- 20260430T155116_5b316615.json
|   |   |   |-- 20260430T163948_5f207fae.json
|   |   |   |-- 20260430T164225_8ff65485.json
|   |   |   |-- 20260430T181659_639b15cb.json
|   |   |   |-- 20260430T181703_34d49536.json
|   |   |   |-- 20260430T181917_8e25e216.json
|   |   |   |-- 20260430T181917_ea82b5d5.json
|   |   |   |-- 20260430T185722_7060f749.json
|   |   |   |-- 20260430T185901_8fae78ca.json
|   |   |   |-- 20260430T190438_15d7c98a.json
|   |   |   |-- 20260430T192154_9f373a24.json
|   |   |   |-- 20260430T201109_c32c8a47.json
|   |   |   |-- 20260430T201208_2a109688.json
|   |   |   |-- 20260430T203557_53d0ba2c.json
|   |   |   +-- 20260430T231831_e1c5d0ad.json
|   |   |-- sales_today
|   |   |   +-- unit_test_req.json
|   |   |-- schema_discovery
|   |   |   +-- unit_test_req.json
|   |   +-- transfer_receipts
|   |       |-- 20260430T154646_30bcdd13.json
|   |       |-- 20260430T154804_36b709a8.json
|   |       |-- 20260430T154938_e4900284.json
|   |       |-- 20260430T155021_d67449b1.json
|   |       +-- 20260430T190237_fecda6dc.json
|   |-- trusted_outputs
|   |   |-- projection_by_category_brand
|   |   |   |-- 20260430T021843_d7464129.json
|   |   |   |-- 20260430T154524_745b58a9.json
|   |   |   |-- 20260430T155116_5b316615.json
|   |   |   |-- 20260430T163948_5f207fae.json
|   |   |   |-- 20260430T164225_8ff65485.json
|   |   |   |-- 20260430T181659_639b15cb.json
|   |   |   |-- 20260430T181703_34d49536.json
|   |   |   |-- 20260430T181917_8e25e216.json
|   |   |   |-- 20260430T181917_ea82b5d5.json
|   |   |   |-- 20260430T185722_7060f749.json
|   |   |   |-- 20260430T185901_8fae78ca.json
|   |   |   |-- 20260430T190438_15d7c98a.json
|   |   |   |-- 20260430T192154_9f373a24.json
|   |   |   |-- 20260430T201109_c32c8a47.json
|   |   |   |-- 20260430T201208_2a109688.json
|   |   |   |-- 20260430T203557_53d0ba2c.json
|   |   |   +-- 20260430T231831_e1c5d0ad.json
|   |   +-- sales_today
|   |       +-- unit_test_req.json
|   +-- validation_reports
|       |-- projection_by_category_brand
|       |   |-- 20260430T021736_7d6c8a03.json
|       |   |-- 20260430T021843_d7464129.json
|       |   |-- 20260430T154524_745b58a9.json
|       |   |-- 20260430T155116_5b316615.json
|       |   |-- 20260430T163948_5f207fae.json
|       |   |-- 20260430T164225_8ff65485.json
|       |   |-- 20260430T181659_639b15cb.json
|       |   |-- 20260430T181703_34d49536.json
|       |   |-- 20260430T181917_8e25e216.json
|       |   |-- 20260430T181917_ea82b5d5.json
|       |   |-- 20260430T185722_7060f749.json
|       |   |-- 20260430T185901_8fae78ca.json
|       |   |-- 20260430T190438_15d7c98a.json
|       |   |-- 20260430T192154_9f373a24.json
|       |   |-- 20260430T201109_c32c8a47.json
|       |   |-- 20260430T201208_2a109688.json
|       |   |-- 20260430T203557_53d0ba2c.json
|       |   +-- 20260430T231831_e1c5d0ad.json
|       |-- sales_today
|       |   +-- unit_test_req.json
|       |-- schema_discovery
|       |   +-- unit_test_req.json
|       +-- transfer_receipts
|           |-- 20260430T154646_30bcdd13.json
|           |-- 20260430T154804_36b709a8.json
|           |-- 20260430T154938_e4900284.json
|           |-- 20260430T155021_d67449b1.json
|           +-- 20260430T190237_fecda6dc.json
|-- tests
|   |-- test_allocate_stock_pool.py
|   |-- test_brand_daily_sales.py
|   |-- test_brand_merit_pool.py
|   |-- test_data_validation_gateway.py
|   |-- test_product_landed_cost_sqlite.py
|   |-- test_projection_brand_exclusions.py
|   |-- test_projection_landed_cog_override.py
|   |-- test_projection_layer2_recovery.py
|   |-- test_schema_verification.py
|   +-- test_transfer_receipt_export.py
|-- tools
|   +-- README.md
|-- .gitignore
|-- all_categories_inventory_and_daily_rebuild.py
|-- allocate_brand_pool_merit.py
|-- allocate_stock_pool_by_brand.py
|-- inventory_sales_alerts_20260316.csv
|-- inventory_sales_monitor.py
|-- inventory_vs_sales_last_6_months.py
|-- monthly_gross_projection_to_sheet.py
|-- prepackaged_flower_metrics.csv
|-- prepackaged_flower_metrics_to_sheet.py
|-- prepackaged_flower_sales_metrics.py
|-- Products-Report-02-18-2026.csv
|-- README.md
|-- requirements.txt
+-- share_sheet_once.py
<!-- REPO_STRUCTURE_END -->

## Change Log
<!-- CHANGELOG_START -->
<!-- CHANGELOG_END -->

## Related
- [[20_projects/index|Projects Index]]
