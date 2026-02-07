---
project_name: PettyCash_Migration_Package
type: core-project
status: active
created: 2026-02-06
updated: 2026-02-06
---

# PettyCash_Migration_Package

## Overview
Petty cash sorter — Google Sheets integration, transaction processing, rules, backups.

## Project Notes
<!-- Add links to project-specific notes as they are created -->
- [[20_projects/PettyCash_Migration_Package/PettyCash/logs]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/LOCKDOWN/BACKUPS/backup_20250721_212632/config]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/LOCKDOWN/BACKUPS/backup_20250721_212632]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/LOCKDOWN/BACKUPS/backup_20250721_212527/config]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/LOCKDOWN/BACKUPS/backup_20250721_212527]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/LOCKDOWN/BACKUPS]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/LOCKDOWN]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/exports]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/zero_amount_transactions]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/processed_transactions/csv_files/PUFFIN]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/processed_transactions/csv_files/NUGZ]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/processed_transactions/csv_files/JGD]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/processed_transactions/csv_files]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/processed_transactions]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/processed_data]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data/downloaded_csv]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/data]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/config]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/backup_original_config/config]]
- [[20_projects/PettyCash_Migration_Package/PettyCash/backup_original_config]]
- [[20_projects/PettyCash_Migration_Package/PettyCash]]
## Repo Structure



<!-- REPO_STRUCTURE_START -->
|-- PettyCash
|   |-- backup_original_config
|   |   |-- config
|   |   |   |-- layout_map.json
|   |   |   +-- system_config.json
|   |   +-- google_sheets_integration.py
|   |-- config
|   |   |-- ai_quota_config.json
|   |   |-- ai_widget_config.json
|   |   |-- batch_range_config.json
|   |   |-- batch_ranges_to_fill.txt
|   |   |-- layout_map.json
|   |   |-- layout_map_cache.json
|   |   |-- operation_progress.json
|   |   |-- payroll_rules_group.json
|   |   |-- pending_rule_suggestions.json
|   |   |-- petty_cash.db
|   |   |-- processing_progress.json
|   |   |-- rules_database.db
|   |   |-- service_account.json
|   |   |-- sheet_structure_config.json
|   |   |-- system_config.json
|   |   |-- system_logic_qa.txt
|   |   |-- tree_optimization_config.json
|   |   +-- widget_config.json
|   |-- data
|   |   |-- downloaded_csv
|   |   |-- processed_data
|   |   |-- processed_transactions
|   |   |   |-- csv_files
|   |   |   |   |-- JGD
|   |   |   |   |   |-- 2025_01_transactions.csv
|   |   |   |   |   |-- 2025_02_transactions.csv
|   |   |   |   |   |-- 2025_03_transactions.csv
|   |   |   |   |   |-- 2025_04_transactions.csv
|   |   |   |   |   |-- 2025_05_transactions.csv
|   |   |   |   |   |-- 2025_06_transactions.csv
|   |   |   |   |   +-- 2025_07_transactions.csv
|   |   |   |   |-- NUGZ
|   |   |   |   |   |-- 2025_01_transactions.csv
|   |   |   |   |   |-- 2025_02_transactions.csv
|   |   |   |   |   |-- 2025_03_transactions.csv
|   |   |   |   |   |-- 2025_04_transactions.csv
|   |   |   |   |   |-- 2025_05_transactions.csv
|   |   |   |   |   |-- 2025_06_transactions.csv
|   |   |   |   |   +-- 2025_07_transactions.csv
|   |   |   |   +-- PUFFIN
|   |   |   |       |-- 2025_01_transactions.csv
|   |   |   |       |-- 2025_03_transactions.csv
|   |   |   |       |-- 2025_04_transactions.csv
|   |   |   |       +-- 2025_05_transactions.csv
|   |   |   +-- filing_system.db
|   |   |-- zero_amount_transactions
|   |   |-- header_monitor.db
|   |   |-- last_check.json
|   |   +-- real_data_analysis.json
|   |-- exports
|   |   |-- data_export_20250721_213850.json
|   |   |-- rules_20250721_213850.csv
|   |   +-- transactions_20250721_213850.csv
|   |-- LOCKDOWN
|   |   |-- BACKUPS
|   |   |   |-- backup_20250721_212527
|   |   |   |   |-- config
|   |   |   |   |   |-- layout_map.json
|   |   |   |   |   +-- system_config.json
|   |   |   |   |-- ai_rule_matcher_enhanced.py
|   |   |   |   |-- csv_downloader_fixed.py
|   |   |   |   |-- database_manager.py
|   |   |   |   |-- google_sheets_integration.py
|   |   |   |   |-- hash_deduplication.py
|   |   |   |   +-- petty_cash_sorter_final_comprehensive.py
|   |   |   +-- backup_20250721_212632
|   |   |       |-- config
|   |   |       |   |-- layout_map.json
|   |   |       |   +-- system_config.json
|   |   |       |-- ai_rule_matcher_enhanced.py
|   |   |       |-- csv_downloader_fixed.py
|   |   |       |-- database_manager.py
|   |   |       |-- google_sheets_integration.py
|   |   |       |-- hash_deduplication.py
|   |   |       +-- petty_cash_sorter_final_comprehensive.py
|   |   |-- daily_autorun.bat
|   |   |-- file_checksums.json
|   |   +-- lockdown.log
|   |-- logs
|   |   |-- add_missing_sources.log
|   |   |-- ai_observer.log
|   |   |-- ai_observer_enhanced.log
|   |   |-- ai_observer_with_execution.log
|   |   |-- ai_rule_matcher.log
|   |   |-- ai_rule_matcher_enhanced.log
|   |   |-- api_rate_limiter.log
|   |   |-- audit_and_reporting.log
|   |   |-- audit_trail.json
|   |   |-- batch_debug.log
|   |   |-- bulletproof_sorter.log
|   |   |-- check_headers.log
|   |   |-- cleanup_duplicates.log
|   |   |-- clear_refresh_dropdowns.log
|   |   |-- complete_pipeline_test.log
|   |   |-- csv_downloader.log
|   |   |-- debug_sheets.log
|   |   |-- direct_cell_test.log
|   |   |-- enhanced_widget.log
|   |   |-- error_recovery.log
|   |   |-- failed_transactions.json
|   |   |-- final_sorter.log
|   |   |-- find_correct_sheets.log
|   |   |-- fresh_test_100.log
|   |   |-- google_sheets_integration.log
|   |   |-- header_monitor.log
|   |   |-- jgdtruth_extraction.log
|   |   |-- live_monitor.log
|   |   |-- live_sorter.log
|   |   |-- ollama_analysis_output.txt
|   |   |-- ollama_auto_review.log
|   |   |-- ollama_qa_review.txt
|   |   |-- payroll_duplication_fix.log
|   |   |-- performance_metrics.log
|   |   |-- petty_cash_monitor.log
|   |   |-- petty_cash_sorter.log
|   |   |-- petty_cash_sorter_ai_enhanced.log
|   |   |-- petty_cash_sorter_enhanced.log
|   |   |-- petty_cash_sorter_final.log
|   |   |-- petty_cash_sorter_fixed.log
|   |   |-- petty_cash_sorter_v2.log
|   |   |-- pipeline_test.log
|   |   |-- progress_monitor.log
|   |   |-- proper_batch_test.log
|   |   |-- rule_loader.log
|   |   |-- sheets_downloader.log
|   |   |-- simple_sheets_test.log
|   |   |-- simple_sorter.log
|   |   |-- simple_test_100.log
|   |   |-- test_100_with_sheets.log
|   |   |-- test_25_transactions.log
|   |   |-- test_bulletproof_sorter.log
|   |   +-- test_first_100.log
|   |-- ✅ SCRIPT REVIEW COMPLETE - OPTIMIZED AND.ini
|   |-- 2025 JGD Financials.xlsx
|   |-- 64DD1310
|   |-- 6B4B1310
|   |-- 8F822310
|   |-- add_hash_deduplication.py
|   |-- add_registers_to_dropdown.py
|   |-- ai_enhanced_widget.py
|   |-- AI_RULE_MANAGER_IMPLEMENTATION.md
|   |-- ai_rule_matcher.py
|   |-- ai_rule_matcher_enhanced.py
|   |-- api_rate_limiter.py
|   |-- audit_and_reporting.py
|   |-- backup_original_config.py
|   |-- BATCH_RANGE_IMPLEMENTATION_README.md
|   |-- check_actual_updates.py
|   |-- check_available_transactions.py
|   |-- check_database_schema.py
|   |-- check_empty_rows.py
|   |-- check_filing_duplication.py
|   |-- check_header_structure.py
|   |-- check_lockdown_status.py
|   |-- check_program_results.py
|   |-- check_rebuilt_rules.py
|   |-- check_remaining_empty.py
|   |-- check_rules.py
|   |-- check_sheet_dates.py
|   |-- check_transaction_processing.py
|   |-- CLARIFICATION_QUESTIONS.md
|   |-- CLAUDE.md
|   |-- clean_recreate_dropdowns.py
|   |-- cleanup_duplicate_rules.py
|   |-- cleanup_filing_system.py
|   |-- cleanup_rules.py
|   |-- CLEANUP_SUMMARY.md
|   |-- clear_and_restart.py
|   |-- clear_database_fresh_start.py
|   |-- clear_everything_fresh_start.py
|   |-- clear_google_sheets_before_run.py
|   |-- comment_processor.py
|   |-- comprehensive_data_analysis.py
|   |-- comprehensive_feature_test.py
|   |-- config_manager.py
|   |-- copy_to_desktop.bat
|   |-- create_migration_package.bat
|   |-- create_migration_verification.py
|   |-- csv_downloader.py
|   |-- csv_downloader_fixed.py
|   |-- data_analyzer.py
|   |-- database_manager.py
|   |-- DC421310
|   |-- debug_jgd_truth_rules.py
|   |-- debug_layout_mapping.py
|   |-- debug_rule_loading.py
|   |-- debug_sheets_update.py
|   |-- debug_target_sheet_error.py
|   |-- demo_rule_management.py
|   |-- desktop_widget_enhanced.py
|   |-- diagnose_row_counting.py
|   |-- diagnostic_test.py
|   |-- direct_cell_test.py
|   |-- direct_dropdown_check.py
|   |-- Discord Bot Token.FdEzDO
|   |-- DOWNLOADER_README.md
|   |-- enhanced_live_monitor.py
|   |-- ENHANCED_SYSTEM_README.md
|   |-- ERROR_HANDLING_README.md
|   |-- examine_jgd_truth_structure.py
|   |-- FINAL_CLARIFICATION_QUESTIONS.md
|   |-- FINAL_SORTER_README.md
|   |-- final_verification_test.py
|   |-- fix_duplicate_transactions.py
|   |-- fix_logging_encoding.py
|   |-- fix_reg_duplication.py
|   |-- fresh_test_100_transactions.py
|   |-- generate_failure_report.bat
|   |-- google_sheets_downloader.py
|   |-- google_sheets_integration.py
|   |-- google_sheets_integration_safe.py
|   |-- google_sheets_manager.py
|   |-- hash_deduplication.py
|   |-- IMPLEMENTATION_PROGRESS.md
|   |-- IMPLEMENTATION_RESPONSE.md
|   |-- IMPLEMENTATION_STATUS.md
|   |-- IMPLEMENTATION_SUMMARY.md
|   |-- investigate_cell_j184.py
|   |-- investigate_reg_amounts.py
|   |-- investigate_target_cells.py
|   |-- JGD Truth Current.xlsx
|   |-- JGDTruth.xlsx
|   |-- launch_enhanced_widget.bat
|   |-- live_monitor.py
|   |-- LOCKDOWN_NOW.bat
|   |-- LOCKDOWN_SUMMARY.md
|   |-- lockdown_system.py
|   |-- make_files_readonly.py
|   |-- make_files_writable.py
|   |-- make_portable.py
|   |-- migrate_coordinate_columns.py
|   |-- migrate_database.py
|   |-- migrate_rules_company.py
|   |-- MIGRATION_PLAN.md
|   |-- MIGRATION_SUMMARY.md
|   |-- monitor_system.py
|   |-- performance_comparison_test.py
|   |-- performance_monitor.py
|   |-- PERFORMANCE_OPTIMIZATIONS_README.md
|   |-- Petty cash Gemini vs.py
|   |-- petty_cash.db
|   |-- petty_cash_monitor.py
|   |-- petty_cash_sorter_final.py
|   |-- petty_cash_sorter_final_comprehensive.py
|   |-- petty_cash_sorter_v2.py
|   |-- PROBLEM_ANALYSIS_AND_SOLUTIONS.md
|   |-- processed_transaction_manager.py
|   |-- PRODUCTION_READINESS_SUMMARY.md
|   |-- PRODUCTION_READY_CHECKLIST.md
|   |-- proper_batch_test.py
|   |-- quick_db_check.py
|   |-- quick_feature_test.py
|   |-- README.md
|   |-- README_PETTY_CASH_SORTER_PROGRESS.md
|   |-- README_PRODUCTION_READY.md
|   |-- README_PROGRESS_TEST_25_TRANSACTIONS.md
|   |-- real_time_monitor.py
|   |-- real_time_monitor_enhanced.py
|   |-- requirements.txt
|   |-- requirements_downloader.txt
|   |-- reset_and_rebuild_rules.py
|   |-- review_rule_suggestions.py
|   |-- review_suggestions.bat
|   |-- RULE_FORMAT_CLARIFICATION.md
|   |-- rule_loader.py
|   |-- run_complete_pipeline_test.py
|   |-- run_downloader.bat
|   |-- run_downloader_once.bat
|   |-- run_enhanced_final_sorter.bat
|   |-- run_final_comprehensive.bat
|   |-- run_final_sorter.bat
|   |-- run_monitor_only.py
|   |-- run_petty_cash_v2.bat
|   |-- run_petty_cash_with_comments.bat
|   |-- run_production.py
|   |-- run_retry_failed.bat
|   |-- run_safe_pipeline.py
|   |-- run_simple_display.py
|   |-- run_slow_demo.py
|   |-- run_test_25_transactions.bat
|   |-- run_test_first_100.bat
|   |-- run_test_monitor.py
|   |-- run_tests.py
|   |-- run_verbose_sorter.py
|   |-- run_with_live_display.py
|   |-- safe_google_sheets_reset.py
|   |-- SCRIPT_RISK_ASSESSMENT_AND_ACTION_PLAN.md
|   |-- setup_task_scheduler.bat
|   |-- show_target_cells.py
|   |-- simple_data_test.py
|   |-- simple_dropdown_add.py
|   |-- simple_lockdown.py
|   |-- simple_sheets_test.py
|   |-- simple_test_100_transactions.py
|   |-- summary_row_analysis.py
|   |-- test_100_with_sheets_update.py
|   |-- test_25_transactions.py
|   |-- test_ai_learning.bat
|   |-- test_ai_learning_system.py
|   |-- test_ai_rule_suggestions.py
|   |-- test_ai_suggestions.bat
|   |-- test_amount_parsing.py
|   |-- test_batch_coordinates.py
|   |-- test_comprehensive_simple.py
|   |-- test_connection.py
|   |-- test_csv_downloader.py
|   |-- test_dashboard_updates.py
|   |-- test_data_loading.py
|   |-- test_database_status.py
|   |-- test_date_finding.py
|   |-- test_date_format.py
|   |-- test_enhanced_monitor.py
|   |-- test_filing_integration.bat
|   |-- test_filing_integration.py
|   |-- test_first_100_transactions.py
|   |-- test_fixes.py
|   |-- test_full_update.py
|   |-- test_hash_deduplication.py
|   |-- test_hash_integration.py
|   |-- test_in_memory_coordinates.py
|   |-- test_layout_coordinates.py
|   |-- test_layout_mapping_fixes.py
|   |-- test_method_fix.py
|   |-- test_optimized_download.py
|   |-- test_output.txt
|   |-- test_performance_optimizations.py
|   |-- test_production_readiness.py
|   |-- test_row_1805.py
|   |-- test_rule_loader.py
|   |-- test_rule_management.py
|   |-- test_sheet_access.py
|   |-- test_sheets_update.py
|   |-- THe.py
|   |-- update_to_practice_spreadsheet.py
|   |-- user_inspection_list.json
|   |-- USER_INSPECTION_REPORT.md
|   |-- verify_google_sheets_updates.py
|   +-- view_coordinate_logs.py
<!-- REPO_STRUCTURE_END -->

## Change Log
<!-- CHANGELOG_START -->
<!-- CHANGELOG_END -->

## Related
- [[index|Projects Index]]
