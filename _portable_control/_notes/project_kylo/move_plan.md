# Project-Kylo Move Plan

**Date:** 2026-01-27  
**Status:** Planning Phase - DRY-RUN ONLY  
**Agent:** Agent 2 (Read-Only)

## Overview

This plan organizes Project-Kylo into a clean, maintainable structure. All moves are proposed within `D:\Project-Kylo\` to maintain relative paths and preserve the repository structure.

## Proposed Target Structure

```
D:\Project-Kylo\
├── repos\                    # Git repositories (atomic units)
│   └── .git\                 # Keep .git as-is (DO NOT MOVE)
│
├── services\                  # Runtime services (already exists, consolidate)
│   ├── bus\                  # Kafka consumers
│   ├── common\               # Shared utilities
│   ├── intake\               # Data intake services
│   ├── mover\                # Data mover service
│   ├── n8n\                  # n8n workflows
│   ├── replay\               # Replay workers
│   ├── rules_loader\         # Rules loading service
│   └── watcher\              # Watcher services
│
├── scripts\active\           # Active operational scripts
│   ├── auto_start_kylo*.ps1
│   ├── start_*.ps1
│   ├── stop_*.ps1
│   ├── restart_*.ps1
│   ├── smart_restart.ps1
│   ├── kafka_topics.*
│   ├── kill_python_processes.ps1
│   ├── kylo_monitor_gui.ps1
│   ├── show_watcher_logs.ps1
│   ├── system_monitor.ps1
│   ├── setup_*.ps1
│   └── config\               # Script configuration
│
├── scripts\archive\          # Legacy/deprecated scripts
│   └── (to be determined during review)
│
├── config\                   # Application configuration (already exists)
│   ├── companies\            # Company configs
│   └── instances\            # Instance configs
│
├── docs\                     # Documentation (already exists)
│   ├── *.md                  # Markdown docs
│   ├── n8n\                  # n8n workflow configs
│   └── runbooks\             # Operational runbooks
│
├── data\raw\                 # Raw input data
│   └── (from current data\)
│
├── data\exports\             # Exported/processed data
│   └── (future exports)
│
├── db\                       # Database files (already exists)
│   ├── ddl\                  # Schema definitions
│   ├── rules_snapshots\      # Rule snapshots
│   ├── tmp_rules\            # Temporary rules
│   └── apply.ps1             # DB apply script
│
├── _archive\YYYY-MM-DD\      # Dated archives
│   └── (uncertain items go here)
│
├── bin\                      # Executable utilities (keep as-is)
├── kylo\                     # Main application package (keep as-is)
├── kylo-dashboard\           # Dashboard app (keep as-is)
├── scaffold\                 # Project scaffold (keep as-is)
├── tools\                    # Development tools (keep as-is)
├── telemetry\                # Telemetry (keep as-is)
├── syncthing_monitor\        # Monitor service (keep as-is)
├── workflows\                # Workflow definitions (keep as-is)
├── layout\                   # Layout configs (keep as-is)
│
└── Root level files:
    ├── README.md
    ├── COMMAND_REFERENCE.md
    ├── MAINTENANCE.md
    ├── START_SERVICES_COMMANDS.md
    ├── pyproject.toml
    ├── requirements.txt
    ├── requirements-kafka.txt
    ├── pytest.ini
    ├── setup_db.py
    ├── pg_hba_fixed.conf
    ├── redpanda.yaml
    ├── docker-compose*.yml
    ├── Dockerfile.*
    └── Project-Kylo.code-workspace
```

## What Moves Where (Summary)

### High Confidence Moves (confidence >= 0.80)

1. **Scripts Consolidation**
   - `scripts\*.ps1` → `scripts\active\*.ps1` (operational scripts)
   - `scripts\gui_helpers\*` → `scripts\active\gui_helpers\*`
   - `scripts\config\*` → `scripts\active\config\*`
   - `restart_all_services.ps1` → `scripts\active\restart_all_services.ps1`
   - `start_all_services*.ps1` → `scripts\active\start_all_services*.ps1`
   - `start_with_logs_simple.ps1` → `scripts\active\start_with_logs_simple.ps1`

2. **Data Organization**
   - `data\*.json` → `data\raw\*.json` (if raw data)
   - `data\*.csv` → `data\raw\*.csv` (if raw data)

3. **Archive Organization**
   - `archive\*` → `_archive\2026-01-27\archive\*` (preserve existing archive)

### Medium Confidence (0.50-0.79) - Archive Only

1. **Legacy Scripts**
   - Scripts in `bin\` that appear to be one-offs → `_archive\2026-01-27\bin_legacy\`
   - Old test scripts → `_archive\2026-01-27\tests_legacy\`

2. **Temporary/Development Files**
   - `db\tmp_rules\*` → Keep in place (may be actively used)
   - `*.pyc` files → Skip (auto-generated)
   - `__pycache__\` → Skip (auto-generated)

### Low Confidence (< 0.50) - Skip or Manual Review

1. **Repository Internals**
   - `.git\*` → **SKIP** (never move)
   - `.github\*` → **SKIP** (CI/CD configs)
   - `.venv\*` → **SKIP** (virtual environment)
   - `project_kylo.egg-info\*` → **SKIP** (build artifacts)

2. **Build Artifacts**
   - `*.pyc` → **SKIP**
   - `__pycache__\` → **SKIP**
   - `node_modules\` (if exists) → **SKIP**

3. **Runtime State**
   - Files in `data\` that appear to be runtime state → **MANUAL REVIEW**
   - Log files → **MANUAL REVIEW** (may be actively written)

## Items That Must NOT Be Moved Automatically

### Critical - Never Move

1. **`.git\` directory** - Repository metadata (atomic unit)
2. **`.github\workflows\`** - CI/CD configuration
3. **`.venv\`** - Virtual environment (should be recreated, not moved)
4. **`project_kylo.egg-info\`** - Build artifacts (regenerated)
5. **Active log files** - May be actively written
6. **Database files in use** - `db\` structure should be preserved

### Manual Review Required

1. **`data\` contents** - Need to determine if raw data or runtime state
2. **`archive\` contents** - May contain important historical data
3. **`db\tmp_rules\`** - May be actively used or temporary
4. **Root-level PowerShell scripts** - Some may be entry points
5. **`kylo-dashboard\`** - May have build artifacts or node_modules
6. **`syncthing_monitor\`** - May have active `.env` with secrets

## Manual Review List

Before executing moves, manually review:

1. **`data\` directory contents**
   - Determine if files are raw input data or runtime state
   - Check for active file locks or recent modifications

2. **`archive\` directory**
   - Verify contents are truly archived
   - Check for any active references

3. **Root-level scripts**
   - `restart_all_services.ps1`
   - `start_all_services.ps1`
   - `start_all_services_with_logs.ps1`
   - `start_with_logs_simple.ps1`
   - These may be entry points referenced externally

4. **`db\tmp_rules\`**
   - Verify if these are temporary or actively used
   - Check for references in code

5. **`syncthing_monitor\.env`**
   - Contains secrets - handle carefully
   - May need to stay in place

6. **`kylo-dashboard\`**
   - Check for `node_modules\` (skip if exists)
   - Verify build artifacts

## Safety Rules Applied

✅ Never touch `.git` internal contents  
✅ Never auto-move database dumps unless clearly labeled  
✅ Never move `node_modules\` or `venv` caches  
✅ Prefer archiving uncertain items  
✅ All moves use `-WhatIf` in dry-run  
✅ No deletions - only moves/copies  
✅ Confidence < 0.80 → archive_only or skip

## Next Steps

1. Review this plan
2. Run dry-run script: `.\_scripts\move_project_kylo_dryrun.ps1`
3. Review dry-run log: `_logs\move_project_kylo_dryrun.log`
4. Adjust manifest if needed
5. If approved, run execute script: `.\_scripts\move_project_kylo_execute.ps1 -Execute`
