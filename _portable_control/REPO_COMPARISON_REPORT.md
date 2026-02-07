# Repository Comparison Report: Remodel vs Project Kylo

**Analysis Date:** 2026-01-27  
**Repos Analyzed:**
- **Repo A (Remodel):** D:\REMODEL
- **Repo B (Current Kylo):** D:\Project-Kylo

---

## 1) Repo A Summary (Remodel)

### Purpose Statement
Remodel is a redesigned version of the Kylo transaction processing system focused on accuracy-first, quota-aware batching. It processes financial transactions from Google Sheets, Plaid, and CSV sources, applies matching rules, and posts results back to Google Sheets. The system is designed for single-operator use with explicit approval workflows and performance targets of processing ~4,000 initial rows in ≤10 minutes and ≤100 daily rows in ≤2 minutes.

### High-Level Architecture
- **Architecture Pattern:** Event-driven micro-processes with per-company isolation
- **Data Flow:** Pooled ingestion DB → per-company replication → company-specific processing pipelines
- **Modules/Services:**
  - `services/intake/` - CSV downloader, processor, deduplication, storage
  - `services/mover/` - Data movement from global to company DBs
  - `services/triage/` - Transaction-to-rule matching worker
  - `services/replay/` - Replay worker after rule promotion
  - `services/rules_loader/` - Rules loading from Google Sheets
  - `services/rules_promoter/` - Rules promotion service
  - `services/sheets/` - Google Sheets posting and projection
  - `services/bus/` - Kafka consumers (promote, txns, sync)
  - `services/webhook/` - FastAPI webhook server
  - `services/config/` - Connection management, schema resolution, SQL preprocessing
  - `scaffold/` - Template project structure with tests
- **Dataflow:** CSV/Sheets/Plaid → Global DB (intake/core/control schemas) → Mover → Company DBs (app schema) → Triage → Sort Queue → Aggregator → Sheets Poster

### Directory Map
```
D:\REMODEL\
├── .github/workflows/        # CI/CD (pytest with Postgres)
├── bin/                      # CLI utilities (check_*, load_*, verify_*)
├── config/                   # companies.json, dsn_map.json
├── data/                     # Layout JSON files (710-2025.json, jgd-2025.json, etc.)
├── db/
│   ├── ddl/                  # 23 SQL migration files (0001-0019, company_0001-0003, etc.)
│   ├── multi_schema/         # Multi-schema deployment SQL
│   ├── sql/                  # Additional SQL files
│   └── tmp_rules/            # Temporary rule files
├── docs/                     # Extensive documentation (20+ markdown files)
├── layout/                   # Layout JSON files (duplicate of data/)
├── scaffold/                 # Template project with tests (26 test files)
├── scripts/                  # Deployment and validation scripts
├── services/                 # Core service modules (29 Python files)
├── telemetry/                # Telemetry emitter
└── docker-compose*.yml       # Docker services (Postgres, Kafka, consumers)
```

### Entry Points
- **CLI Tools:** Multiple `bin/*.py` scripts with `if __name__ == "__main__"` entry points
  - `bin/csv_intake.py` - CSV intake CLI tool
  - `bin/check_*.py` - Various validation/checking utilities
  - `bin/load_*.py` - Rules loading utilities
- **Service Workers:**
  - `services/bus/kafka_consumer_*.py` - Kafka consumer entry points (async main functions)
  - `services/triage/worker.py` - Triage worker (company-first fork)
  - `services/replay/worker.py` - Replay worker
- **Webhook Server:** `services/webhook/server.py` - FastAPI app with `/webhook/kylo/move-batch` and `/healthz` endpoints
- **Scaffold Tools:** `scaffold/tools/sheets_cli.py` - Sheets CLI helper
- **No unified CLI:** No `kylo` command or `pyproject.toml` script entry

### Config System
- **Primary Config:** `config/companies.json` - Company definitions, active sources, target workbooks, intake settings
- **Database Connections:** `dsn_map.json` / `dsn_map_local.json` - Per-company database connection strings
- **Environment:** `.env` file (gitignored) - `DATABASE_URL`, `DATABASE_URL_POOL`, `DATABASE_URL_<COMPANY_ID>`, `GOOGLE_APPLICATION_CREDENTIALS`
- **Layout Files:** `layout/*.json` or `data/layouts/*.json` - Sheet layout definitions per company/year
- **No YAML config:** Unlike Project-Kylo, no `kylo.config.yaml` or instance configs

### Data Layer
- **Database Technology:** PostgreSQL 16
- **Architecture:** Multi-DB pooled architecture
  - **Global/Pooled DB:** Schemas `intake`, `core`, `control`
    - `intake.raw_transactions` - Immutable raw intake
    - `core.transactions_unified` - Normalized, deduped transactions
    - `control.ingest_batches` - Batch tracking
    - `control.company_feeds` - Per-company feed state
    - `control.outbox_events` - Application outbox pattern
  - **Company DBs:** Separate database per company (e.g., `kylo_nugz`, `kylo_710`)
    - `app.transactions` - Company-specific transactions (txn_uid PK, hash_norm for change detection)
    - `app.rules_active` - Live rules snapshot
    - `app.sort_queue` - Processing queue
    - `app.outputs_projection` - Output state
    - `app.pending_txns` - Unmatched transactions
- **Migrations:** Raw SQL DDL files in `db/ddl/` (23 files), no Alembic
- **Multi-Schema Support:** `db/multi_schema/` contains deployment scripts for multi-tenant schema approach

### Integrations
- **Google Sheets:** Primary integration via `google-api-python-client`
  - Service account authentication via `GOOGLE_APPLICATION_CREDENTIALS`
  - Batch updates only (no single-cell updates)
  - Layout cache for coordinate resolution
  - Rate limiting: token bucket (~60 calls/min)
- **CSV Downloader:** `services/intake/csv_downloader.py` - Downloads CSV from Google Sheets
- **Plaid:** Mentioned in config but not actively implemented (commented in `scaffold/example.env`)
- **Kafka/Redpanda:** Event bus for `kylo.txns`, `kylo.promote` topics
- **n8n:** Workflow definitions in `docs/n8n/` and `kylo_telemetry_workflow.json`
- **No Tiller integration:** Not found in codebase

### Watchers / Background Jobs / Schedulers
- **No Watcher System:** Remodel does not have a watcher component like Project-Kylo
- **Event-Driven Processing:** Uses Kafka consumers and LISTEN/NOTIFY for triggering
- **Workers:**
  - `services/triage/worker.py` - Processes company batches, matches transactions to rules
  - `services/replay/worker.py` - Replays after rule promotion
- **Kafka Consumers:**
  - `kafka_consumer_txns.py` - Consumes transaction events, triggers triage
  - `kafka_consumer_promote.py` - Consumes promotion events, triggers replay
  - `kafka_consumer_txns_sync.py` - Sync consumer variant
- **Manual/UI Triggered:** Processing starts via manual triggers or webhook calls

### Observability
- **Logging:** Python `logging` module (structured logging in triage worker)
- **Telemetry:** `telemetry/emitter.py` - Telemetry event emitter
- **n8n Integration:** Telemetry workflow for event tracking
- **No Metrics/Tracing:** No explicit metrics collection or distributed tracing
- **No Dashboard:** No ops dashboard component

### Tests
- **Framework:** pytest
- **Configuration:** `pytest.ini` - Test paths: `scaffold/tests`, markers for integration tests
- **Structure:** `scaffold/tests/` - 26 test files covering:
  - `ingest/` - Intake tests (sheets_seed_loader)
  - `sheets/` - Poster tests
  - `mover/` - Mover service tests
  - Integration tests marked with `@pytest.mark.integration`
- **How to Run:** `pytest -q` (unit), `pytest -m integration -q` (integration)
- **CI/CD:** GitHub Actions runs tests with Postgres 16 service

### Deployment
- **Docker Compose:**
  - `docker-compose.yml` - PostgreSQL 16 service (port 5433)
  - `docker-compose.kafka.yml` - Kafka/Redpanda service
  - `docker-compose.kafka-consumer.yml` - Kafka consumer services
  - `Dockerfile.kafka-consumer` - Consumer Docker image
- **Local Development:** Supports local Postgres (port 5432) or Docker (port 5433)
- **Multi-Schema Deployment:** `scripts/deploy_multi_schema.sh` and `scripts/rollout_manager.py`
- **No Systemd:** No systemd service files
- **CI/CD:** GitHub Actions workflow (`.github/workflows/ci.yml`) - Runs pytest with Postgres service

### Security/Secrets Handling
- **Service Account:** `GOOGLE_APPLICATION_CREDENTIALS` environment variable points to JSON key file
- **Database Credentials:** Stored in `.env` file (gitignored) or `dsn_map_local.json`
- **No Secret Manager:** No integration with cloud secret managers
- **Postgres HBA:** `pg_hba_fixed.conf` for PostgreSQL authentication configuration

### Known TODOs or Unfinished Areas
- **Shadow Mode:** `services/sheets/poster.py` has TODO comments for shadow mode and apply mode processing
- **API Endpoints:** README mentions planned API endpoints (POST `/api/process/start`, GET `/api/process/status`, etc.) - not implemented
- **Live Progress View:** Docs mention "Not implemented yet" for live progress view during long runs
- **Migration from SQLite:** Migration checklist exists but status unclear

---

## 2) Repo B Summary (Current Kylo)

### Purpose Statement
Project-Kylo is a maintenance-only repository for the Kylo processing system. It is a production system that processes financial transactions from Google Sheets, applies matching rules, and posts results back to Google Sheets. The system uses a watcher-based architecture that monitors for changes and triggers processing pipelines. Development is paused; the system is kept running as-is.

### High-Level Architecture
- **Architecture Pattern:** Watcher-driven with hub supervisor, microservices-style with Kafka event bus
- **Data Flow:** Watcher monitors Sheets → Intake → Global DB → Mover → Company DBs → Rules Matching → Posting → Sheets
- **Modules/Services:**
  - `kylo/` - Core CLI and watcher runtime (`cli.py`, `watcher.py`, `watcher_runtime.py`, `hub.py`)
  - `services/intake/` - CSV downloader, processor, deduplication, sheets intake, storage
  - `services/mover/` - Data movement service
  - `services/posting/` - Sheet posting services (jgdtruth_poster, assurance)
  - `services/rules/` - Rules provider (jgdtruth_provider) and listener
  - `services/rules_loader/` - Rules loading from Google Sheets
  - `services/rules_promoter/` - Rules promotion service
  - `services/bus/` - Kafka consumers (promote, txns, sync)
  - `services/triage/` - Triage worker
  - `services/sheets/` - Google Sheets poster and projection
  - `services/webhook/` - Webhook server
  - `services/ops/` - Operations dashboard and heartbeat
  - `services/state/` - State store for incremental posting
  - `services/common/` - Config loader, instance management, normalization, retry logic
  - `kylo-dashboard/` - Electron desktop application (React + TypeScript)
- **Dataflow:** Watcher → Intake → Global DB → Mover → Company DBs → Triage → Rules → Posting → Sheets

### Directory Map
```
D:\Project-Kylo\
├── .github/workflows/        # CI/CD (pytest)
├── .kylo/                    # Runtime state (gitignored)
├── bin/                      # 30+ utility scripts
├── config/                   # YAML configs, companies.json, dsn_map.json
├── data/layouts/             # Layout JSON files
├── db/
│   ├── ddl/                  # 19 SQL migration files
│   ├── rules_snapshots/      # SQL rule snapshots (with _fixed variants)
│   └── tmp_rules/            # Temporary rule files
├── docs/                     # Documentation (29 files)
├── kylo/                     # Core package (CLI, watcher, hub)
├── kylo-dashboard/           # Electron dashboard app (subproject)
├── layout/                   # Layout files (DUPLICATE of data/layouts)
├── scripts/
│   └── active/               # Active PowerShell scripts (26 files)
├── services/                 # Service modules
├── scaffold/                 # Template project with tests (47 files)
├── syncthing_monitor/        # Monitoring utility
├── telemetry/                # Telemetry emitter
├── tools/                    # Debug scripts, manual tests, legacy code (48 files)
├── workflows/                # n8n workflow definitions
└── docker-compose*.yml       # Docker services
```

### Entry Points
- **Primary CLI:** `kylo` command (via `pyproject.toml` script entry `kylo.cli:main`)
  - `kylo watcher run` - Run watcher instance
  - `kylo hub start/stop/status` - Hub supervisor commands
  - `kylo ops dashboard` - Build ops dashboard JSON
  - `kylo config validate` - Validate config
- **Runtime Services:**
  - `kylo/hub.py` - Hub supervisor (manages watcher instances)
  - `kylo/watcher_runtime.py` - Watcher runtime (main entry: `main()`)
  - `kylo/watcher.py` - Watcher implementation (compatibility wrapper)
- **Service Modules:** Same as Remodel (bus, intake, mover, posting, rules, triage, webhook)
- **Operational Scripts:** `bin/*.py` - 30+ utility scripts
- **PowerShell Scripts:** `scripts/active/*.ps1` - Start/stop scripts, monitoring, GUI helpers
- **Docker Services:** `docker-compose.yml`, `docker-compose.kafka.yml`, `docker-compose.kafka-consumer.yml`

### Config System
- **Primary Config:** `config/kylo.config.yaml` - Main Kylo configuration
- **Global Config:** `config/global.yaml` - Global settings
- **Company Configs:** `config/companies/` - Company-specific YAML files (EMPIRE.yaml, JGD.yaml, NUGZ.yaml, PUFFIN.yaml)
- **Instance Configs:** `config/instances/` - Instance configs (KYLO_2025.yaml, KYLO_2026.yaml, JGD_2025.yaml, JGD_2026.yaml)
- **Company Data:** `config/companies.json` - Company definitions
- **Database Connections:** `config/dsn_map.json` / `config/dsn_map_local.json`
- **CSV Processor:** `config/csv_processor_config.json`
- **Environment:** `.env` file (gitignored) - Various env vars
- **Script Config:** `scripts/config/config.json`, `scripts/config/layout_map.json`, `scripts/config/service_account.json`
- **Package Config:** `pyproject.toml` - Python package definition with script entry

### Data Layer
- **Database Technology:** PostgreSQL 16
- **Architecture:** Similar multi-DB structure to Remodel
  - **Global DB:** Schemas `intake`, `core`, `control` (same structure as Remodel)
  - **Company DBs:** Separate database per company with `app` schema
- **Migrations:** Raw SQL DDL files in `db/ddl/` (19 files, fewer than Remodel's 23)
- **Rules Snapshots:** `db/rules_snapshots/` - SQL rule snapshots with `_fixed` variants
- **No Multi-Schema:** No `db/multi_schema/` directory (Remodel has this)

### Integrations
- **Google Sheets:** Primary integration via `google-api-python-client`
  - Service account authentication
  - Batch updates with incremental posting support
  - Layout cache for coordinate resolution
- **CSV Downloader:** `services/intake/csv_downloader.py`
- **Kafka/Redpanda:** Event bus for `kylo.txns`, `kylo.promote` topics
- **n8n:** Workflow definitions in `workflows/` and `docs/n8n/`
- **Syncthing Monitor:** `syncthing_monitor/monitor.py` - Monitoring utility
- **No Plaid/Tiller:** Not actively implemented

### Watchers / Background Jobs / Schedulers
- **Watcher System:** Core component (`kylo/watcher_runtime.py`)
  - Monitors Google Sheets for changes (checksums on rules and intake data)
  - Triggers intake, mover, and posting pipelines
  - Supports multiple instances (KYLO_2025, KYLO_2026) for year-based routing
  - Configurable watch interval and jitter
  - State persistence in `.kylo/instances/<INSTANCE_ID>/state/`
- **Hub Supervisor:** `kylo/hub.py` - Manages watcher instances (start/stop/status)
- **Kafka Consumers:** Same as Remodel (txns, promote, sync)
- **PowerShell Scripts:** `scripts/active/start_watchers_by_year.ps1` - Start dual watchers for 2025+2026
- **Task Scheduler:** GUI scheduler mentioned in docs (`tools/scripthub_legacy/gui_scheduler.py`)

### Observability
- **Logging:** Python `logging` module
- **Telemetry:** `telemetry/emitter.py` - Telemetry event emitter
- **Ops Dashboard:** `services/ops/dashboard.py` - Generates dashboard JSON
- **Heartbeat:** `services/ops/heartbeat.py` - Heartbeat tracking
- **GUI Monitor:** `scripts/active/kylo_monitor_gui.ps1` - PowerShell GUI monitor
- **System Monitor:** `scripts/active/system_monitor.ps1` - System monitoring script
- **n8n Integration:** Telemetry workflow for event tracking
- **No Metrics/Tracing:** No explicit metrics collection or distributed tracing

### Tests
- **Framework:** pytest
- **Configuration:** `pytest.ini` - Test paths: `scaffold/tests`, markers for integration tests
- **Structure:** 
  - `scaffold/tests/` - Comprehensive test suite (39 Python files)
  - `tools/tests_manual/` - Manual/integration tests (15+ test files)
- **How to Run:** `pytest -q` (unit), `pytest -m integration -q` (integration)
- **CI/CD:** GitHub Actions workflow (`.github/workflows/ci.yml`) - Runs pytest with Postgres service

### Deployment
- **Docker Compose:**
  - `docker-compose.yml` - PostgreSQL 16 service (port 5433)
  - `docker-compose.kafka.yml` - Kafka/Redpanda service
  - `docker-compose.kafka-consumer.yml` - Kafka consumer services
  - `Dockerfile.kafka-consumer` - Consumer Docker image
- **PowerShell Scripts:** Extensive operational scripts in `scripts/active/`
  - `start_all_services.ps1` - Start all services
  - `start_watchers_by_year.ps1` - Start watchers
  - `stop_all_services.ps1` - Stop all services
  - `kylo_monitor_gui.ps1` - GUI monitor
- **No Systemd:** No systemd service files
- **CI/CD:** GitHub Actions workflow (`.github/workflows/ci.yml`) - Runs pytest

### Security/Secrets Handling
- **Service Account:** `GOOGLE_APPLICATION_CREDENTIALS` environment variable or `google.service_account_json_path` in config
- **Database Credentials:** Stored in `.env` file (gitignored) or `dsn_map_local.json`
- **Script Config:** `scripts/config/service_account.json` - Service account credentials
- **No Secret Manager:** No integration with cloud secret managers
- **Postgres HBA:** `pg_hba_fixed.conf` for PostgreSQL authentication configuration

### Known TODOs or Unfinished Areas
- **Dashboard Metrics:** `kylo-dashboard/src/components/MetricsGraph.tsx` has TODO for fetching from heartbeat.json
- **Maintenance Mode:** README states "Maintenance-only repository" and "Development is paused"
- **Legacy Code:** `tools/scripthub_legacy/` - Legacy ScriptHub implementation marked for archiving
- **Duplicate Layouts:** `layout/` folder duplicates `data/layouts/` (marked as archive candidate)

---

## 3) Comparison Report

### Feature Parity Table

| Component | In A (Remodel)? | In B (Kylo)? | Notes |
|-----------|----------------|--------------|-------|
| **Core Processing** |
| CSV Intake | ✅ | ✅ | Both have CSV downloader, processor, deduplication |
| Google Sheets Intake | ✅ | ✅ | Both support Sheets as data source |
| Transaction Deduplication | ✅ | ✅ | Multi-layer deduplication in both |
| Rules Matching | ✅ | ✅ | Triage worker in both |
| Rules Loading | ✅ | ✅ | Sheets loader in both |
| Rules Promotion | ✅ | ✅ | Promoter service in both |
| Sheet Posting | ✅ | ✅ | Batch posting in both |
| **Architecture** |
| Watcher System | ❌ | ✅ | Kylo has watcher; Remodel is event-driven only |
| Hub Supervisor | ❌ | ✅ | Kylo has hub to manage watcher instances |
| Kafka Event Bus | ✅ | ✅ | Both use Kafka/Redpanda |
| Multi-DB Architecture | ✅ | ✅ | Global + per-company DBs in both |
| Multi-Schema Support | ✅ | ❌ | Remodel has multi-schema deployment scripts |
| **Configuration** |
| YAML Config System | ❌ | ✅ | Kylo uses YAML; Remodel uses JSON only |
| Instance Configs | ❌ | ✅ | Kylo has instance-specific configs (KYLO_2025, etc.) |
| Company Configs | ✅ | ✅ | Both have company definitions |
| **CLI & Entry Points** |
| Unified CLI (`kylo` command) | ❌ | ✅ | Kylo has `kylo` CLI; Remodel has scattered bin scripts |
| Webhook Server | ✅ | ✅ | Both have FastAPI webhook endpoints |
| **Services** |
| Mover Service | ✅ | ✅ | Data movement between DBs |
| Triage Worker | ✅ | ✅ | Transaction-to-rule matching |
| Replay Worker | ✅ | ✅ | Replay after rule promotion |
| Ops Dashboard | ❌ | ✅ | Kylo has ops dashboard and heartbeat |
| State Store | ❌ | ✅ | Kylo has incremental posting state store |
| **Integrations** |
| Google Sheets API | ✅ | ✅ | Both use google-api-python-client |
| n8n Workflows | ✅ | ✅ | Both have n8n integration |
| Telemetry | ✅ | ✅ | Both have telemetry emitter |
| Syncthing Monitor | ❌ | ✅ | Kylo has syncthing monitor |
| **UI/Dashboard** |
| Electron Dashboard | ❌ | ✅ | Kylo has kylo-dashboard Electron app |
| GUI Monitor (PowerShell) | ❌ | ✅ | Kylo has PowerShell GUI monitor |
| **Testing** |
| pytest Framework | ✅ | ✅ | Both use pytest |
| Test Suite | ✅ | ✅ | Both have scaffold/tests |
| Integration Tests | ✅ | ✅ | Both have integration test markers |
| **Deployment** |
| Docker Compose | ✅ | ✅ | Both have docker-compose files |
| PowerShell Scripts | ❌ | ✅ | Kylo has extensive PowerShell operational scripts |
| CI/CD (GitHub Actions) | ✅ | ✅ | Both have CI workflows |
| **Documentation** |
| Extensive Docs | ✅ | ✅ | Both have comprehensive documentation |
| Runbooks | ✅ | ✅ | Both have operational runbooks |

### Structural Diffs

**Folder Layout Differences:**
- **Remodel:** No `kylo/` package directory (no unified CLI)
- **Kylo:** Has `kylo/` package with CLI, watcher, hub
- **Kylo:** Has `kylo-dashboard/` Electron app subproject
- **Kylo:** Has `scripts/active/` subdirectory for operational scripts
- **Remodel:** Has `db/multi_schema/` for multi-tenant schema deployment
- **Kylo:** Has `db/rules_snapshots/` directory
- **Kylo:** Has `tools/` directory with debug scripts and legacy code
- **Kylo:** Has `syncthing_monitor/` directory

**Naming Conventions:**
- **Remodel:** Uses `services/ingest/` for seed loader; Kylo uses `services/intake/`
- **Remodel:** Config in root `config/`; Kylo has `config/companies/` and `config/instances/` subdirectories
- **Remodel:** Layout files in `layout/` or `data/`; Kylo has both `layout/` and `data/layouts/` (duplicate)

**Contracts:**
- **Remodel:** Event-driven via Kafka/LISTEN-NOTIFY; no watcher contract
- **Kylo:** Watcher-based with state persistence; hub manages instances
- **Both:** Use same Kafka topics (`kylo.txns`, `kylo.promote`)
- **Both:** Use same database schema structure (intake/core/control, app schema)

### Behavioral Diffs

**Pipelines:**
- **Remodel:** Manual/UI-triggered or webhook → intake → mover → triage → posting
- **Kylo:** Watcher monitors → intake → mover → triage → posting (automatic triggering)

**Routing Rules:**
- **Remodel:** Company-based routing via config
- **Kylo:** Year-based routing via `year_workbooks` config and watcher instances (KYLO_2025, KYLO_2026)

**Idempotency:**
- **Both:** Use batch signatures and UNIQUE constraints
- **Kylo:** Has incremental posting with state store for cell-level change detection
- **Remodel:** Uses batch signatures in `control.sheet_posts`

**Schemas:**
- **Remodel:** Has additional DDL files (23 vs 19) including multi-schema support
- **Remodel:** Has `0017_ingest_landing_txns_simple.sql`, `0018_ingest_v_seed_normalized*.sql`, `0019_txns_unique_on_amount.sql`
- **Kylo:** Missing some newer DDL files from Remodel

### Config Diffs

**What Changed:**
- **Remodel:** JSON-only config (`companies.json`, `dsn_map.json`)
- **Kylo:** YAML-based config system (`kylo.config.yaml`, `global.yaml`, instance configs)
- **Kylo:** Has `year_workbooks` config for year-based routing
- **Kylo:** Has instance registry (`config/instances/index.yaml`)

**What's Missing:**
- **Remodel:** Missing YAML config system, instance configs, year-based routing
- **Kylo:** Missing multi-schema deployment configs

**What's Incompatible:**
- **Config Format:** Remodel's JSON vs Kylo's YAML - not directly compatible
- **Instance System:** Kylo's instance-based config system doesn't exist in Remodel
- **Year Routing:** Kylo's `year_workbooks` config not present in Remodel

### DB Diffs

**Migrations:**
- **Remodel:** 23 DDL files
- **Kylo:** 19 DDL files
- **Missing in Kylo:** `0017_ingest_landing_txns_simple.sql`, `0018_ingest_v_seed_normalized*.sql`, `0019_txns_unique_on_amount.sql`, multi-schema files

**Table Names:**
- **Both:** Use same schema structure (intake/core/control, app)
- **Both:** Same table names in core schemas

**Schema Strategy:**
- **Remodel:** Supports both per-company DBs and multi-schema approach
- **Kylo:** Only per-company DBs (no multi-schema)

**Versioning:**
- **Both:** Use raw SQL DDL files, no Alembic
- **Both:** No formal migration versioning system

### External Integration Diffs

**Credentials:**
- **Both:** Use `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- **Both:** Store in `.env` or config files
- **Kylo:** Also supports `google.service_account_json_path` in YAML config

**APIs:**
- **Both:** Google Sheets API with same authentication
- **Both:** Same rate limiting approach (token bucket mentioned in Remodel docs)

**Sheets Layouts:**
- **Remodel:** Layout files in `layout/` or `data/` (same structure)
- **Kylo:** Layout files in both `layout/` and `data/layouts/` (duplicate)
- **Both:** Use same layout JSON format

**Kafka:**
- **Both:** Use same topics and consumer groups
- **Both:** Use Redpanda/Kafka for event bus

### Risk & Effort

**Easy Ports:**
1. **Multi-Schema DDL Files** - Copy `db/multi_schema/` and additional DDL files (0017-0019) from Remodel to Kylo
2. **Triage Worker Improvements** - Remodel's triage worker has batch signature checking - low risk
3. **Documentation** - Remodel has extensive docs that could supplement Kylo's docs
4. **Test Improvements** - Remodel's test structure is similar, easy to port test cases

**Moderate Ports:**
1. **Config System Unification** - Port Remodel's JSON config approach OR port Kylo's YAML system to Remodel (requires refactoring)
2. **Watcher Integration** - Add watcher system to Remodel (significant architectural change)
3. **Ops Dashboard** - Port Kylo's ops dashboard to Remodel (moderate effort)
4. **Incremental Posting** - Port Kylo's state store and incremental posting to Remodel (moderate complexity)
5. **Instance System** - Port Kylo's instance-based config system to Remodel (requires config refactor)

**Risky Ports:**
1. **Year-Based Routing** - Kylo's `year_workbooks` and instance system is tightly coupled to watcher - risky to port to Remodel's event-driven model
2. **Hub Supervisor** - Kylo's hub system manages watcher lifecycle - doesn't fit Remodel's architecture
3. **Electron Dashboard** - Porting `kylo-dashboard/` would require Node.js/TypeScript setup in Remodel
4. **PowerShell Scripts** - Kylo's extensive PowerShell operational scripts are Windows-specific and tightly coupled to watcher/hub
5. **Legacy Code Migration** - Porting Kylo's `tools/scripthub_legacy/` would bring in deprecated code

### Recommended Port Plan

**Phase 1: Low-Risk Improvements (1-2 weeks)**
1. Port multi-schema DDL files from Remodel to Kylo (`db/multi_schema/`, DDL files 0017-0019)
2. Port Remodel's improved triage worker batch signature logic to Kylo
3. Consolidate duplicate layout directories in Kylo (remove `layout/` or `data/layouts/`)

**Phase 2: Documentation & Testing (1 week)**
4. Merge Remodel's extensive documentation into Kylo's docs (especially `REMODEL_PLAN.md`, execution plans)
5. Port any additional test cases from Remodel to Kylo

**Phase 3: Config System Evaluation (2-3 weeks)**
6. Evaluate whether to adopt Remodel's JSON config approach or keep Kylo's YAML system
7. If keeping YAML, document migration path from Remodel's JSON configs
8. If adopting JSON, create migration script from YAML to JSON

**Phase 4: Feature Ports (3-4 weeks)**
9. Port incremental posting state store from Kylo to Remodel (if Remodel needs this feature)
10. Port ops dashboard from Kylo to Remodel (if Remodel needs monitoring)

**Phase 5: Architecture Decision (Major)**
11. **Decision Point:** Choose primary architecture:
    - **Option A:** Keep Kylo's watcher-based system, port Remodel improvements into Kylo
    - **Option B:** Migrate Kylo to Remodel's event-driven architecture, lose watcher system
    - **Option C:** Hybrid - Keep watcher for monitoring, use event-driven for processing

**Rationale:**
- Phase 1-2 are low-risk and provide immediate value
- Phase 3 requires architectural decision about config system
- Phase 4 adds features that may or may not be needed
- Phase 5 is a major architectural decision that should be made after evaluating both systems in production

---

## 4) Evidence Appendix

### Repo A (Remodel) - Key Files Analyzed

**Configuration:**
- `config/companies.json`
- `dsn_map.json`
- `scaffold/example.env`
- `README.md` (main)
- `docs/REMODEL_PLAN.md`

**Entry Points:**
- `services/bus/kafka_consumer_*.py`
- `services/triage/worker.py`
- `services/replay/worker.py`
- `services/webhook/server.py`
- `bin/csv_intake.py`
- `scaffold/tools/sheets_cli.py`

**Database:**
- `db/ddl/` (23 SQL files)
- `db/multi_schema/` (multi-schema deployment)
- `setup_db.py`

**Services:**
- `services/intake/` (csv_downloader.py, csv_processor.py, deduplication.py, storage.py)
- `services/mover/` (service.py, models.py, sql.py)
- `services/sheets/` (poster.py, projection.py)
- `services/rules_loader/` (loader.py, sheets_loader.py)
- `services/rules_promoter/` (service.py)

**Deployment:**
- `docker-compose.yml`
- `docker-compose.kafka.yml`
- `docker-compose.kafka-consumer.yml`
- `Dockerfile.kafka-consumer`
- `.github/workflows/ci.yml`

**Tests:**
- `pytest.ini`
- `scaffold/tests/` (26 test files)
- `scaffold/requirements.txt`

### Repo B (Project Kylo) - Key Files Analyzed

**Configuration:**
- `config/kylo.config.yaml`
- `config/global.yaml`
- `config/companies.json`
- `config/instances/` (KYLO_2025.yaml, etc.)
- `config/dsn_map.json`
- `pyproject.toml`

**Entry Points:**
- `kylo/cli.py` (main CLI)
- `kylo/watcher_runtime.py` (watcher main)
- `kylo/hub.py` (hub supervisor)
- `kylo/watcher.py`
- `services/bus/kafka_consumer_*.py`
- `services/webhook/server.py`
- `bin/*.py` (30+ utility scripts)

**Database:**
- `db/ddl/` (19 SQL files)
- `db/rules_snapshots/` (SQL snapshots)
- `setup_db.py`

**Services:**
- `services/intake/` (csv_downloader.py, csv_processor.py, deduplication.py, sheets_intake.py, storage.py)
- `services/mover/` (service.py, models.py, sql.py)
- `services/posting/` (jgdtruth_poster.py, assurance.py)
- `services/rules/` (jgdtruth_provider.py, listener.py)
- `services/sheets/` (poster.py, projection.py)
- `services/ops/` (dashboard.py, heartbeat.py)
- `services/state/` (store.py)

**Watcher System:**
- `kylo/watcher_runtime.py` (main watcher logic)
- `kylo/watcher.py`
- `kylo/hub.py` (instance management)

**Deployment:**
- `docker-compose.yml`
- `docker-compose.kafka.yml`
- `docker-compose.kafka-consumer.yml`
- `Dockerfile.kafka-consumer`
- `.github/workflows/ci.yml`
- `scripts/active/*.ps1` (PowerShell operational scripts)

**UI/Dashboard:**
- `kylo-dashboard/` (Electron app)
- `scripts/active/kylo_monitor_gui.ps1`

**Tests:**
- `pytest.ini`
- `scaffold/tests/` (39 Python files)
- `tools/tests_manual/` (15+ test files)
- `scaffold/requirements.txt`

**Documentation:**
- `README.md`
- `MAINTENANCE.md`
- `COMMAND_REFERENCE.md`
- `docs/EXECUTIVE_SUMMARY.md`
- `docs/README.md`

---

**Report Generated:** 2026-01-27  
**Analysis Method:** File system scanning, code reading, grep searches, documentation review
