# ScriptHub Classification Report

**Analysis Date:** 2026-01-27  
**Repository:** D:\ScriptHub  
**Status:** FROZEN - READ-ONLY MODE  
**Purpose:** Classify all components for migration to Project Kylo

---

## Executive Summary

ScriptHub contains a mix of:
- **ACTIVE components** currently used by Project Kylo (sync scripts, server)
- **REQUIRED FOR KYLO** components that Kylo depends on at runtime
- **REUSABLE** generic utilities that could be migrated
- **OBSOLETE** components safe to archive
- **DANGEROUS/UNCLEAR** components requiring human review

**Critical Finding:** Project Kylo has a copy of ScriptHub code at `D:\Project-Kylo\tools\scripthub_legacy` but also references external ScriptHub paths. This creates a dependency that needs resolution.

---

## Classification by Category

### A) ACTIVE – Currently Used by Project Kylo

These components are actively referenced and used by Project Kylo.

#### 1. Sync Scripts (Runtime Dependency)
- **Path:** `D:\ScriptHub\PettyCash\` (likely contains sync scripts)
- **Status:** ACTIVE - Referenced by Kylo watcher
- **Kylo Dependency:** 
  - `kylo/watcher_runtime.py` calls `tools/scripthub_legacy/sync_runner.py`
  - `sync_runner.py` runs `sync_bank.py` and `dynamic_columns_jgdtruth.py`
- **Language:** Python
- **How Used:** 
  - Called by Kylo watcher via `KYLO_SYNC_BEFORE_TICK` environment variable
  - Runs periodically to sync Kylo_Config rules and refresh layout maps
- **Migration Recommendation:** 
  - **MUST MIGRATE** - These are critical runtime dependencies
  - Already partially copied to `D:\Project-Kylo\tools\scripthub_legacy`
  - Need to verify if external ScriptHub path is still required

#### 2. ScriptHub FastAPI Server
- **Path:** `D:\ScriptHub\` (server.py - location TBD)
- **Status:** ACTIVE - Started by Kylo auto-start scripts
- **Kylo Dependency:**
  - `scripts/active/auto_start_kylo_simple.ps1` starts ScriptHub server
  - `scripts/active/system_monitor.ps1` monitors ScriptHub server
  - `scripts/active/kylo_monitor_gui.ps1` has ScriptHub sync UI
- **Language:** Python (FastAPI/uvicorn)
- **How Used:**
  - Webhook server on port 8000
  - Provides API endpoints for ScriptHub services
- **Migration Recommendation:**
  - **MUST MIGRATE** or document external dependency
  - Currently referenced at `D:\Project-Kylo\tools\scripthub_legacy\server.py`
  - Verify if this is the same as ScriptHub root server.py

#### 3. ScriptHub Sync Runner
- **Path:** `D:\Project-Kylo\tools\scripthub_legacy\sync_runner.py` (already in Kylo)
- **Status:** ACTIVE - Partially migrated
- **Kylo Dependency:**
  - Called by watcher runtime
  - Runs `sync_bank.py` and `dynamic_columns_jgdtruth.py`
- **Language:** Python
- **Migration Recommendation:**
  - **ALREADY IN KYLO** - Verify completeness
  - Check if external ScriptHub version is still needed

---

### B) REQUIRED FOR KYLO – Not Currently Inside Kylo Repo But Still Used at Runtime

These components are required for Kylo to function but live outside the Kylo repo.

#### 1. DO NOT DELETE / GrowFlow
- **Path:** `D:\ScriptHub\DO NOT DELETE\GrowFlow\`
- **Status:** REQUIRED FOR KYLO - Sacred folder
- **Contents:**
  - `growflow_automation.py` - Automated GrowFlow sales data download
  - `upload_sales_to_gsheet.py` - Uploads sales to Google Sheets
  - `daily_automation.py` - Daily sales export automation
  - `sales_summary_automation.py` - Sales summary export
  - `generate_sales_report.py` - Telegram sales report generation
  - `send_sales_report.py` - Telegram message sending
- **Language:** Python
- **How Used:**
  - Downloads sales data from GrowFlow retail portal
  - Uploads to Google Sheets (likely used by Kylo for data ingestion)
  - Scheduled task runs nightly at 10:00 PM
  - Sends Telegram reports
- **Kylo Dependency:** 
  - Likely provides data that Kylo processes
  - Google Sheets integration may feed into Kylo intake
- **Migration Recommendation:**
  - **DO NOT MIGRATE AUTOMATICALLY** - Marked as "DO NOT DELETE"
  - **HUMAN REVIEW REQUIRED** - Determine if this is Kylo-critical or separate system
  - If Kylo-critical: Document external dependency clearly
  - If separate: Leave in ScriptHub, document relationship

#### 2. DO NOT DELETE / Sales Analytics
- **Path:** `D:\ScriptHub\DO NOT DELETE\Sales Analytics\`
- **Status:** REQUIRED FOR KYLO - Sacred folder
- **Contents:**
  - CSV files: `Nugz (date ranges) OrderItems.csv`
  - Excel file: `Sales_Analytics (1).xlsx`
- **Language:** Data files
- **How Used:**
  - Contains historical sales data
  - May be referenced by Kylo for analysis
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Data files, not code
  - **HUMAN REVIEW REQUIRED** - Determine if Kylo needs access to these files
  - If needed: Document external data dependency

#### 3. PettyCash Folder
- **Path:** `D:\ScriptHub\PettyCash\`
- **Status:** REQUIRED FOR KYLO - Likely critical
- **Contents:**
  - `petty_cash_sorter_optimized.py` - Main sorter (batch/range logic)
  - `desktop_widget_enhanced.py` - Desktop widget UI
  - `petty_cash_monitor.py` - Monitoring
  - `check_*.py` - Various check/validation scripts
  - `test_*.py` - Test scripts
- **Language:** Python
- **How Used:**
  - Processes petty cash transactions
  - Integrates with Google Sheets
  - May feed data into Kylo system
- **Kylo Dependency:**
  - Kylo processes petty cash data
  - May depend on ScriptHub PettyCash for data ingestion
- **Migration Recommendation:**
  - **HUMAN REVIEW REQUIRED** - Determine relationship to Kylo
  - If Kylo uses this: **MUST MIGRATE** or document external dependency
  - Check if Kylo has its own petty cash processing

---

### C) REUSABLE – Generic Utilities That Could Be Migrated

These are generic utilities that could be useful in other projects.

#### 1. Agents System
- **Path:** `D:\ScriptHub\agents\`
- **Status:** REUSABLE
- **Contents:**
  - `ai_file_organizer.py` - AI-powered file organization
  - `coordination_layer.py` - Agent coordination
  - `cross_review_system.py` - Cross-review system
  - `file_monitor_agent.py` - File monitoring
  - `git_integration.py` - Git integration utilities
  - `github_api.py` - GitHub API wrapper
  - `github_repo_manager.py` - Repository management
  - `learning_memory.py` - Learning/memory system
  - `task_queue_system.py` - Task queue
- **Language:** Python
- **Migration Recommendation:**
  - **OPTIONAL MIGRATION** - Generic utilities
  - Could be useful for Kylo if it needs agent/AI capabilities
  - Evaluate if Kylo needs these features

#### 2. Plugins System
- **Path:** `D:\ScriptHub\plugins\`
- **Status:** REUSABLE
- **Contents:**
  - `code_analyzer.py` - Code analysis plugin
  - `performance_monitor.py` - Performance monitoring
- **Language:** Python
- **Migration Recommendation:**
  - **OPTIONAL MIGRATION** - Generic plugin system
  - Could be useful for Kylo development/debugging

#### 3. Development Agent
- **Path:** `D:\ScriptHub\DevelopmentAgent\`
- **Status:** REUSABLE
- **Contents:**
  - `dev_monitor.py` - Development monitoring
  - `dev_optimizer.py` - Development optimization
- **Language:** Python
- **Migration Recommendation:**
  - **OPTIONAL MIGRATION** - Development tools
  - May be useful for Kylo development workflow

#### 4. Configuration System
- **Path:** `D:\ScriptHub\config\`
- **Status:** REUSABLE
- **Contents:**
  - `ai_config.json` - AI configuration
  - `app_config.json` - Application configuration
  - `file_monitor_config.json` - File monitor config
  - `github_config.json` - GitHub config
  - `system_config.json` - System config
- **Language:** JSON
- **Migration Recommendation:**
  - **EVALUATE** - Check if Kylo needs any of these config patterns
  - Likely not needed if Kylo has its own config system

---

### D) OBSOLETE – Safe to Archive

These components appear to be old, unused, or superseded.

#### 1. Archive Folder
- **Path:** `D:\ScriptHub\archive\`
- **Status:** OBSOLETE
- **Contents:** Old versions of chink_eyes components
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Already archived
  - Safe to leave in ScriptHub

#### 2. Test Systems
- **Path:** 
  - `D:\ScriptHub\final_test_system\`
  - `D:\ScriptHub\test_ai_system\`
- **Status:** OBSOLETE
- **Contents:** Test files (test_file_0.py, test_file_1.py, etc.)
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Test files, not production code
  - Safe to archive

#### 3. Old Documentation
- **Path:** Various README files at root
- **Status:** OBSOLETE (for migration purposes)
- **Contents:**
  - `CHINK_EYES_README.md`
  - `COLLABORATIVE_AI_README.md`
  - `GIT_GITHUB_INTEGRATION_SUMMARY.md`
  - `GUI_IMPROVEMENTS_SUMMARY.md`
  - `PHASE2_README.md`
  - `README_COMPLETE_SYSTEM.md`
  - `README_PROFESSIONAL.md`
  - `QUICK_START.md`
  - `SYSTEM_STATUS_REPORT.md`
  - `TEST_RESULTS_SUMMARY.md`
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Historical documentation
  - May be useful as reference, but not needed in Kylo

#### 4. Launch Scripts
- **Path:** `D:\ScriptHub\QuickLaunch\`
- **Status:** OBSOLETE (for Kylo)
- **Contents:** Batch files for launching various ScriptHub tools
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - ScriptHub-specific launchers
  - Not needed in Kylo

#### 5. Ollama Files
- **Path:** `D:\ScriptHub\ollama\`, `ollama.zip`, `ollama_temp.zip`
- **Status:** OBSOLETE (for Kylo)
- **Contents:** Ollama model files and executables
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Not Kylo-related
  - Safe to archive

#### 6. WebScraper
- **Path:** `D:\ScriptHub\WebScraper\`
- **Status:** OBSOLETE (for Kylo)
- **Contents:** Web scraping utilities
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Not Kylo-related
  - Safe to archive

#### 7. ytdl2mp4
- **Path:** `D:\ScriptHub\ytdl2mp4\`
- **Status:** OBSOLETE (for Kylo)
- **Contents:** YouTube downloader
- **Migration Recommendation:**
  - **DO NOT MIGRATE** - Not Kylo-related
  - Safe to archive

---

### E) DANGEROUS / UNCLEAR – Needs Human Review

These components require human judgment to determine their status.

#### 1. ScriptHub Root Files
- **Path:** `D:\ScriptHub\` (root level)
- **Status:** UNCLEAR
- **Contents:**
  - `database_schema.sql` - Database schema (which database?)
  - `create_shortcuts.ps1` - Shortcut creation script
  - `launch_citizensfinance.*` - Citizens Finance launcher (what is this?)
  - `setup_git_path.bat` - Git path setup
  - `scripts_config.json` - Scripts configuration
  - Various requirements files
- **Migration Recommendation:**
  - **HUMAN REVIEW REQUIRED** - Determine purpose and Kylo relationship
  - Check if any are referenced by Kylo

#### 2. Sync Scripts Location
- **Path:** Unknown - Need to find actual location
- **Status:** DANGEROUS - Critical but location unclear
- **Issue:** 
  - Kylo references `tools/scripthub_legacy/sync_runner.py`
  - But ScriptHub may have original versions
  - Need to determine which is authoritative
- **Migration Recommendation:**
  - **CRITICAL REVIEW REQUIRED** - Must identify all sync scripts
  - Verify if ScriptHub has original versions that need migration
  - Check if Kylo's copy is complete

#### 3. Server.py Location
- **Path:** Unknown - Need to find actual location
- **Status:** DANGEROUS - Critical but location unclear
- **Issue:**
  - Kylo references `tools/scripthub_legacy/server.py`
  - But ScriptHub root may have a server.py
  - Need to determine relationship
- **Migration Recommendation:**
  - **CRITICAL REVIEW REQUIRED** - Must identify server.py location
  - Verify if Kylo's copy is complete and up-to-date

---

## KYLO DEPENDENCY MAP

### Runtime Dependencies

| Component | ScriptHub Path | Kylo Reference | Dependency Type | Critical? |
|-----------|---------------|----------------|-----------------|-----------|
| Sync Runner | `PettyCash/sync_runner.py` (?) | `tools/scripthub_legacy/sync_runner.py` | Runtime (watcher calls) | ✅ YES |
| Sync Bank | `PettyCash/sync_bank.py` (?) | Called by sync_runner | Runtime | ✅ YES |
| Dynamic Columns | `PettyCash/dynamic_columns_jgdtruth.py` (?) | Called by sync_runner | Runtime | ✅ YES |
| ScriptHub Server | `server.py` (?) | `tools/scripthub_legacy/server.py` | Runtime (auto-start) | ✅ YES |
| GrowFlow Automation | `DO NOT DELETE/GrowFlow/` | External data source | Data dependency | ⚠️ REVIEW |
| PettyCash Sorter | `PettyCash/` | External processor? | Runtime dependency? | ⚠️ REVIEW |

### Configuration Dependencies

| Component | ScriptHub Path | Kylo Reference | Dependency Type |
|-----------|---------------|----------------|-----------------|
| Layout Map | `config/layout_map.json` (?) | `tools/scripthub_legacy/config/layout_map.json` | Configuration |
| Service Account | `config/service_account.json` (?) | `tools/scripthub_legacy/config/service_account.json` | Credentials |

### Script Dependencies

| Component | ScriptHub Path | Kylo Reference | Dependency Type |
|-----------|---------------|----------------|-----------------|
| Auto-start Scripts | N/A | `scripts/active/auto_start_kylo_simple.ps1` | References ScriptHub |
| System Monitor | N/A | `scripts/active/system_monitor.ps1` | Monitors ScriptHub |
| GUI Monitor | N/A | `scripts/active/kylo_monitor_gui.ps1` | Shows ScriptHub status |

---

## Summary by Folder

| Folder | Classification | Action Required |
|--------|---------------|-----------------|
| `DO NOT DELETE/` | B (REQUIRED FOR KYLO) | **HUMAN REVIEW** - Sacred folder |
| `PettyCash/` | B (REQUIRED FOR KYLO) | **HUMAN REVIEW** - May be critical |
| `agents/` | C (REUSABLE) | Optional migration |
| `plugins/` | C (REUSABLE) | Optional migration |
| `DevelopmentAgent/` | C (REUSABLE) | Optional migration |
| `config/` | C (REUSABLE) | Evaluate for Kylo needs |
| `archive/` | D (OBSOLETE) | Do not migrate |
| `final_test_system/` | D (OBSOLETE) | Do not migrate |
| `test_ai_system/` | D (OBSOLETE) | Do not migrate |
| `QuickLaunch/` | D (OBSOLETE) | Do not migrate |
| `ollama/` | D (OBSOLETE) | Do not migrate |
| `WebScraper/` | D (OBSOLETE) | Do not migrate |
| `ytdl2mp4/` | D (OBSOLETE) | Do not migrate |
| Root files | E (UNCLEAR) | **HUMAN REVIEW** required |

---

## Critical Issues Requiring Immediate Attention

1. **Sync Scripts Location Unknown**
   - Kylo uses sync scripts but exact ScriptHub location unclear
   - Need to find: `sync_runner.py`, `sync_bank.py`, `dynamic_columns_jgdtruth.py`
   - Verify if Kylo's copy at `tools/scripthub_legacy/` is complete

2. **Server.py Location Unknown**
   - Kylo references ScriptHub server but exact location unclear
   - Need to find original `server.py` in ScriptHub
   - Verify if Kylo's copy is up-to-date

3. **DO NOT DELETE Folder**
   - Contains GrowFlow automation (may feed Kylo)
   - Marked as sacred - requires human decision
   - Determine if Kylo-critical or separate system

4. **PettyCash Relationship**
   - ScriptHub has PettyCash processing
   - Kylo also processes petty cash
   - Need to determine relationship and dependencies

---

## Recommended Next Steps

1. **IMMEDIATE:** Find exact locations of sync scripts and server.py in ScriptHub
2. **IMMEDIATE:** Review DO NOT DELETE folder contents with human
3. **IMMEDIATE:** Determine PettyCash relationship to Kylo
4. **PHASE 1:** Create migration allowlist based on human review
5. **PHASE 2:** Migrate approved components (copy-only)
6. **PHASE 3:** Update Kylo to remove external ScriptHub dependencies
7. **PHASE 4:** Archive ScriptHub properly

---

## Notes

- This classification is based on code analysis and file structure
- Some paths are marked as "unknown" because exact locations need verification
- All "DO NOT DELETE" folders are treated as sacred and require human approval
- Kylo already has partial ScriptHub code at `tools/scripthub_legacy/` - need to verify completeness

**Report Generated:** 2026-01-27  
**Status:** READ-ONLY ANALYSIS COMPLETE - AWAITING HUMAN REVIEW
