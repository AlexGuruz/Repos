# Project-Kylo Repository Map

**Analysis Date:** 2026-01-27  
**Root Path:** `D:\Project-Kylo\`  
**Repository Type:** Single Git Repository (Python + Node.js hybrid)

---

## High-Level Structure (Top Folders)

```
D:\Project-Kylo\
├── .github/              # CI/CD workflows
├── .git/                 # Git repository (repo boundary)
├── bin/                  # Executable scripts and utilities
├── config/               # Configuration files (YAML, JSON)
├── data/                 # Data files and layouts
├── db/                   # Database DDL and snapshots
├── docs/                 # Documentation
├── kylo/                 # Core Kylo package (main entrypoint)
├── kylo-dashboard/       # Electron dashboard app (subproject)
├── layout/               # Layout files (DUPLICATE - see data/layouts)
├── scripts/              # PowerShell operational scripts
├── scaffold/             # Template/test scaffolding
├── services/             # Service modules (bus, intake, mover, etc.)
├── syncthing_monitor/    # Monitoring utility
├── telemetry/            # Telemetry emitter
├── tools/                # Debug, tests, legacy code
└── workflows/            # n8n workflow definitions
```

---

## Repository Boundaries / Subprojects

### Primary Repository
- **Single Git Repository** at `D:\Project-Kylo\`
- Contains all project code and configuration

### Subprojects / Embedded Projects

1. **kylo-dashboard/** (Node.js/Electron)
   - Independent package with `package.json`
   - Electron desktop application
   - React + TypeScript frontend
   - Build output: `dist/`

2. **scaffold/** (Python template)
   - Template project structure
   - Has own `requirements.txt` and `pytest.ini`
   - Used for generating new company pipelines

---

## Entrypoints (Main Scripts, Services, Runners)

### Primary CLI Entrypoint
- **`kylo/cli.py`** → `kylo` command (via pyproject.toml script entry)
  - Commands: `watcher`, `hub`, `ops`, `config`
  - Main entry: `kylo.cli:main`

### Runtime Services
- **`kylo/hub.py`** - Hub supervisor (manages watcher instances)
- **`kylo/watcher_runtime.py`** - Watcher runtime
- **`kylo/watcher.py`** - Watcher implementation

### Service Modules (services/)
- **`services/bus/`** - Kafka consumers (promote, txns, sync)
- **`services/intake/`** - CSV downloader, processor, sheets intake
- **`services/mover/`** - Data movement service
- **`services/posting/`** - Sheet posting services
- **`services/rules/`** - Rules provider and listener
- **`services/triage/`** - Triage worker
- **`services/webhook/`** - Webhook server

### Operational Scripts (bin/)
- **`bin/kylo_hub.py`** - Hub runner
- **`bin/ops_dashboard.py`** - Operations dashboard
- **`bin/watch_all.py`** - Watcher runner
- **`bin/csv_intake.py`** - CSV intake utility
- **`bin/validate_config.py`** - Config validator
- 30+ utility scripts for specific operations

### PowerShell Scripts (scripts/)
- **`scripts/start_hub.ps1`** - Start hub supervisor
- **`scripts/start_watchers_by_year.ps1`** - Start watchers
- **`scripts/stop_all_services.ps1`** - Stop all services
- **`scripts/kylo_monitor_gui.ps1`** - GUI monitor
- **`scripts/system_monitor.ps1`** - System monitoring

### Docker Services
- **`docker-compose.yml`** - PostgreSQL service
- **`docker-compose.kafka.yml`** - Kafka/Redpanda service
- **`docker-compose.kafka-consumer.yml`** - Kafka consumer service

---

## Config Locations

### Primary Configuration
- **`config/kylo.config.yaml`** - Main Kylo configuration
- **`config/global.yaml`** - Global settings
- **`config/companies/`** - Company-specific configs (EMPIRE.yaml, JGD.yaml, NUGZ.yaml, PUFFIN.yaml)
- **`config/instances/`** - Instance configs (KYLO_2025.yaml, KYLO_2026.yaml, JGD_2025.yaml, JGD_2026.yaml)
- **`config/companies.json`** - Company data
- **`config/csv_processor_config.json`** - CSV processor settings
- **`config/dsn_map.json`** / **`dsn_map_local.json`** - Database connection strings

### Environment Files
- **`syncthing_monitor/.env`** - Syncthing monitor env vars
- **`scaffold/example.env`** - Example environment template
- **`.env`** - Root env (gitignored, may not exist)

### Docker Configuration
- **`docker-compose.yml`** - PostgreSQL config
- **`docker-compose.kafka.yml`** - Kafka config
- **`docker-compose.kafka-consumer.yml`** - Consumer config
- **`Dockerfile.kafka-consumer`** - Consumer Dockerfile
- **`pg_hba_fixed.conf`** - PostgreSQL HBA config

### Script Configuration
- **`scripts/config/config.json`** - Script config
- **`scripts/config/layout_map.json`** - Layout mapping
- **`scripts/config/service_account.json`** - Service account credentials

### Package Configuration
- **`pyproject.toml`** - Python package config (HIGH VALUE)
- **`requirements.txt`** - Python dependencies (HIGH VALUE)
- **`requirements-kafka.txt`** - Kafka-specific dependencies
- **`pytest.ini`** - Test configuration
- **`kylo-dashboard/package.json`** - Node.js dependencies (HIGH VALUE)

---

## Data Folders

### Active Data Directories
- **`data/`** - Data files
  - **`data/layouts/`** - Layout JSON files (710-2025.json, jgd-2025.json, nugz-2025.json, puffin-2025.json, example-2025.json)

- **`layout/`** - **DUPLICATE** of data/layouts/ (contains same 2025 JSON files)
  - 710-2025.json
  - jgd-2025.json
  - nugz-2025.json
  - puffin-2025.json

- **`db/`** - Database artifacts
  - **`db/ddl/`** - SQL migration files (0001-0014, company_0001-0003, etc.)
  - **`db/rules_snapshots/`** - SQL rule snapshots (with _fixed variants)
  - **`db/tmp_rules/`** - Temporary rule files

- **`workflows/`** - Workflow definitions
  - **`workflows/n8n/`** - n8n workflow JSON files
  - **`workflows/telemetry/`** - Telemetry workflow JSON

### Runtime Data (Generated)
- **`.kylo/`** - Runtime state (gitignored)
  - Instance logs, state files, ops dashboard JSON

---

## Duplicates / Versioned Copies / "Old" Folders

### Identified Duplicates

1. **Layout Files Duplication**
   - **`layout/`** folder contains same files as **`data/layouts/`**
   - Files: 710-2025.json, jgd-2025.json, nugz-2025.json, puffin-2025.json
   - **Status:** ARCHIVE CANDIDATE - `layout/` likely redundant

2. **"Fixed" Variants (Versioned Copies)**
   - **`db/rules_snapshots/`** contains pairs:
     - `710_empire_rules.sql` + `710_empire_rules_fixed.sql`
     - `jgd_rules.sql` + `jgd_rules_fixed.sql`
     - `nugz_rules.sql` + `nugz_rules_fixed.sql`
     - `puffin_pure_rules.sql` + `puffin_pure_rules_fixed.sql`
   - **`bin/`** contains:
     - `load_main_worksheet_rules.py` + `load_main_worksheet_rules_fixed.py`
     - `update_nugz_main_active.py` + `update_nugz_main_active_fixed.py`
   - **`tools/tests_manual/`** contains:
     - `test_kafka_aiokafka_fixed.py` (likely supersedes older test)
   - **Status:** ARCHIVE CANDIDATE - "_fixed" variants likely newer, originals may be obsolete

3. **Legacy ScriptHub Code**
   - **`tools/scripthub_legacy/`** - Legacy ScriptHub implementation
   - Contains duplicate config: `tools/scripthub_legacy/config/layout_map.json` (also in `scripts/config/`)
   - **Status:** ARCHIVE CANDIDATE - Marked as legacy

### Dated Folders / Files

- **Year-based configs:** `config/instances/*_2025.yaml`, `config/instances/*_2026.yaml`
- **Year-based layouts:** `data/layouts/*-2025.json`, `layout/*-2025.json`
- **Dated log files:** `tools/scripthub_legacy/logs/dynamic_columns_202601*.log` (gitignored, may not be visible)

### Archive References

- **README.md** mentions `archive/` folder but it's gitignored (may not exist in repo)
- **MAINTENANCE.md** references `archive/docs/` for historical data

---

## Additional Observations

### High-Value Files (Keep)
- `.git/` - Repository history
- `pyproject.toml` - Package definition
- `requirements.txt`, `requirements-kafka.txt` - Dependencies
- `docker-compose*.yml` - Service definitions
- `kylo-dashboard/package.json` - Dashboard dependencies
- `config/` - All configuration files
- `kylo/` - Core package
- `services/` - Service implementations

### Test Infrastructure
- **`scaffold/tests/`** - Comprehensive test suite
- **`tools/tests_manual/`** - Manual/integration tests (15+ test files)
- **`pytest.ini`** - Test configuration

### Documentation
- **`docs/`** - 29 files (markdown, JSON, SQL)
- **`README.md`** - Main readme
- **`COMMAND_REFERENCE.md`** - Operational commands
- **`MAINTENANCE.md`** - Maintenance guide

### Operational Tools
- **`tools/debug/`** - 12 debug scripts
- **`tools/ops_oneoffs/`** - 3 one-off operational scripts
- **`scripts/gui_helpers/`** - 5 PowerShell GUI helper scripts

---

## Summary

**Repository Type:** Single monolithic Python/Node.js hybrid repository  
**Main Language:** Python 3.11+  
**Secondary:** Node.js/TypeScript (dashboard)  
**Architecture:** Microservices-style with Kafka event bus  
**Status:** Maintenance-only mode (per README.md)
