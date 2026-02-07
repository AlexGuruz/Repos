# KYLO & SCRIPTHUB COMMAND REFERENCE

**Last Updated:** 2025-01-XX  
**Purpose:** Quick reference for all operational commands across Kylo, ScriptHub, and COG systems

---

## 📦 PROJECT-KYLO - DOCKER SERVICES

### Start All Services
```powershell
cd D:\Project-Kylo
.\start_all_services.ps1
```

### Start All Services (With Logs)
```powershell
cd D:\Project-Kylo
.\start_all_services_with_logs.ps1
```

### Start Services (Simple)
```powershell
cd D:\Project-Kylo
.\start_with_logs_simple.ps1
```

### Restart All Services
```powershell
cd D:\Project-Kylo
.\restart_all_services.ps1
```

### Stop All Services
```powershell
cd D:\Project-Kylo
.\scripts\active\stop_all_services.ps1
```

### Individual Docker Services
```powershell
# Start PostgreSQL
cd D:\Project-Kylo
docker compose -f docker-compose.yml up -d

# Start Kafka/Redpanda
cd D:\Project-Kylo
docker compose -f docker-compose.kafka.yml up -d

# Start Kafka Consumers
cd D:\Project-Kylo
docker compose -f docker-compose.kafka-consumer.yml up -d

# Stop PostgreSQL
docker compose -f docker-compose.yml down

# Stop Kafka/Redpanda
docker compose -f docker-compose.kafka.yml down

# Stop Kafka Consumers
docker compose -f docker-compose.kafka-consumer.yml down
```

### Create Kafka Topics
```powershell
cd D:\Project-Kylo
.\scripts\active\kafka_topics.ps1
```

### Start Kafka Consumers (Python)
```powershell
cd D:\Project-Kylo
.\scripts\active\start_kafka_consumers.ps1
```

---

## 👀 PROJECT-KYLO - WATCHERS

### Start Dual Watchers (2025 + 2026) - RECOMMENDED
```powershell
cd D:\Project-Kylo
.\scripts\active\start_watchers_by_year.ps1
```
**What it does:** Starts two separate watcher instances (KYLO_2025 and KYLO_2026) in separate PowerShell windows. Each processes ALL companies (NUGZ, EMPIRE, PUFFIN, JGD) but only monitors transactions for their assigned year.

### Start Single Watcher (2025)
```powershell
cd D:\Project-Kylo
$env:KYLO_WATCH_INTERVAL_SECS = "300"
$env:PYTHONUNBUFFERED = "1"
python -u -m bin.watch_all --years 2025 --instance-id KYLO_2025
```

### Start Single Watcher (2026)
```powershell
cd D:\Project-Kylo
$env:KYLO_WATCH_INTERVAL_SECS = "300"
$env:PYTHONUNBUFFERED = "1"
python -u -m bin.watch_all --years 2026 --instance-id KYLO_2026
```

### Start Watcher (All Years)
```powershell
cd D:\Project-Kylo
.\bin\watch.ps1
```

### Start Watcher (Custom Interval)
```powershell
cd D:\Project-Kylo
.\bin\watch.ps1 -IntervalSeconds 300
```

### Start Watcher (Read-Only Mode - No Posting)
```powershell
cd D:\Project-Kylo
$env:KYLO_READ_ONLY = "1"
python -m bin.watch_all --years 2025 --instance-id KYLO_2025
```

### Disable Posting for Specific Instances
```powershell
$env:KYLO_DISABLE_POSTING_FOR = "JGD_2025,NUGZ_2026"
```

### Disable Posting for Specific Companies
```powershell
$env:KYLO_DISABLE_POSTING_COMPANIES = "JGD,NUGZ"
```

### Clear Environment Variables
```powershell
Remove-Item Env:\KYLO_READ_ONLY -ErrorAction SilentlyContinue
Remove-Item Env:\KYLO_DISABLE_POSTING_FOR -ErrorAction SilentlyContinue
Remove-Item Env:\KYLO_DISABLE_POSTING_COMPANIES -ErrorAction SilentlyContinue
```

---

## 🧪 PROJECT-KYLO - TEST SUITES

### Run All Tests (Quick)
```powershell
cd D:\Project-Kylo
python -m pytest -q scaffold
```

### Run All Tests (Excluding Integration)
```powershell
cd D:\Project-Kylo
python -m pytest -q -m "not integration"
```

### Run Integration Tests (Requires Docker)
```powershell
cd D:\Project-Kylo
python -m pytest -q -m integration
```

### Run Specific Test Files
```powershell
cd D:\Project-Kylo
python -m pytest -q scaffold/tests/test_csv_intake.py
python -m pytest -q scaffold/tests/test_full_workflow_integration.py
python -m pytest -q scaffold/tests/triage/test_triage_edge_cases.py
python -m pytest -q scaffold/tests/mover/test_rules_snapshot.py
```

### Run Tests with Verbose Output
```powershell
cd D:\Project-Kylo
python -m pytest -v scaffold/tests
```

---

## 🔄 SCRIPTHUB - SYNC SYSTEMS (LOCAL)

### Run All Syncs (Bundled) - RECOMMENDED
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python run_both_syncs.py
```
**What it does:** Runs sync scripts in sequence:
1. JGDTRUTH Dynamic Columns (header/date mapping)
2. Sync Bank (Kylo_Config → CLEAN TRANSACTIONS)

### Run Sync Bank (Kylo_Config → BANK + CLEAN TRANSACTIONS) - EASY
```powershell
# From repo root (recommended)
cd E:\Repos\Project-Kylo
.\scripts\active\run_sync_bank.ps1

# Dry run (preview only)
.\scripts\active\run_sync_bank.ps1 -DryRun

# Limit rows (e.g. first 500)
.\scripts\active\run_sync_bank.ps1 -Limit 500
```
**What it does:** Reads rules from Kylo_Config tab (columns K/L), writes Company IDs to BANK sheet and to CLEAN TRANSACTIONS tab. Uses repo `.venv` and `.secrets\service_account.json`.

### Sync Bank (Kylo_Config → CLEAN TRANSACTIONS) - Manual
```powershell
cd "E:\Repos\Project-Kylo\tools\scripthub_legacy"
.\run_sync_bank.ps1
# Or: $env:PYTHONPATH = $PWD; python sync_bank.py
```
**What it does:** Same as above; run from `tools\scripthub_legacy` if you prefer.

### Sync Company IDs (BANK → CLEAN TRANSACTIONS)
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python sync_company_ids.py
```
**What it does:** Syncs Company IDs from BANK sheet to CLEAN TRANSACTIONS sheet.

### Dynamic Columns JGDTRUTH (Header/Date Mapping)
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python dynamic_columns_jgdtruth.py --summary
```
**What it does:** Maps headers and dates for JGDTRUTH sheets dynamically.

### Rule Loader JGDTRUTH
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python rule_loader_jgdtruth.py --save-json
```
**What it does:** Loads rules from JGDTRUTH and saves to JSON.

### Start All ScriptHub Scripts (4 Scripts)
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
.\startup_all_scripts.ps1
```
**What it does:** Starts all 4 scripts in separate windows:
1. Sync Bank
2. Company ID Sync
3. Dynamic Columns JGDTRUTH
4. Rule Loader JGDTRUTH

### ScriptHub FastAPI Server (Webhook)
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```
**What it does:** Starts webhook server for real-time updates from Google Sheets Apps Script.

### ScriptHub Server (With Logging)
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
$logDir = ".\.logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logFile = "$logDir\server_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> $logFile
```

### Task Scheduler GUI
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python gui_scheduler.py
```
**What it does:** Opens GUI to manage scheduled tasks for sync scripts.

---

## 📊 COG ALLOCATION SYSTEM

### Google Drive Watcher (Run Once)
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\drive_watcher.py --run-once
```
**What it does:** Checks Google Drive watch folder once, processes any new CSV files, then exits.

### Google Drive Watcher (Continuous)
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\drive_watcher.py
```
**What it does:** Continuously monitors Google Drive watch folder every 5 minutes, processes new CSV files automatically.

### Extract Unique Brands
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\extract_unique_brands.py
```
**What it does:** Extracts unique brand names from CSV files and syncs to Google Sheet "DROP DOWN HELPER" column E.

### Extract Brands (Dry Run)
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\extract_unique_brands.py --dry-run
```

### Extract Brands (Remove Excluded)
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\extract_unique_brands.py --remove-excluded-brands
```
**What it does:** Removes brands if ALL their categories are excluded (based on column H flags).

### Calculate Daily COG
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\calculate_daily_cog.py --csv-files "data/csv_dump/file.csv"
```
**What it does:** Processes CSV sales data, calculates daily COG per brand, writes to "COG" sheet.

### Calculate Daily COG (Dry Run)
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\calculate_daily_cog.py --csv-files "data/csv_dump/file.csv" --dry-run
```

### Populate Categories
```powershell
cd D:\ScriptHub\cog-allocation-system
python scripts\populate_categories.py
```
**What it does:** Extracts categories from CSV files and populates Google Sheet "DROP DOWN HELPER" column G with category inclusion flags in column H.

---

## 🛠️ PROJECT-KYLO - UTILITY COMMANDS

### CSV Intake
```powershell
cd D:\Project-Kylo
python bin\csv_intake.py --spreadsheet-id "SPREADSHEET_ID" --db-url "postgresql://postgres:postgres@localhost:5433/kylo_global" --dry-run
```

### CSV Intake (Stats)
```powershell
cd D:\Project-Kylo
python bin\csv_intake.py --stats --db-url "postgresql://postgres:postgres@localhost:5433/kylo_global"
```

### Validate Config
```powershell
cd D:\Project-Kylo
python bin\validate_config.py
```

### Kylo Hub
```powershell
cd D:\Project-Kylo
python bin\kylo_hub.py
```

### Ops Dashboard
```powershell
cd D:\Project-Kylo
python bin\ops_dashboard.py
```

### List Transactions
```powershell
cd D:\Project-Kylo
python bin\list_txns.py
```

### Check Pending Rules
```powershell
cd D:\Project-Kylo
python bin\check_pending_rules.py
```

### Verify Rules Usage
```powershell
cd D:\Project-Kylo
python bin\verify_rules_usage.py
```

### Diagnose Rules
```powershell
cd D:\Project-Kylo
python bin\diag_rules.py
```

### Load Rules
```powershell
cd D:\Project-Kylo
python bin\load_rules.py
```

### End-to-End Test
```powershell
cd D:\Project-Kylo
python bin\end_to_end_test.py
```

### Test Full Workflow
```powershell
cd D:\Project-Kylo
python bin\test_full_workflow.py
```

### Test Rule Change Reprocessing
```powershell
cd D:\Project-Kylo
python bin\test_rule_change_reprocessing.py
```

---

## 📈 MONITORING & LOGS

### Show Watcher Logs
```powershell
cd D:\Project-Kylo
.\scripts\show_watcher_logs.ps1
```

### System Monitor
```powershell
cd D:\Project-Kylo
.\scripts\system_monitor.ps1
```

### Kylo Monitor GUI
```powershell
cd D:\Project-Kylo
.\scripts\kylo_monitor_gui.ps1
```

### Check Docker Status
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### View Docker Logs (All Services)
```powershell
cd D:\Project-Kylo
docker compose -f docker-compose.yml -f docker-compose.kafka.yml -f docker-compose.kafka-consumer.yml logs -f
```

### View PostgreSQL Logs
```powershell
docker compose -f docker-compose.yml logs -f kylo-pg
```

### View Redpanda Logs
```powershell
docker compose -f docker-compose.kafka.yml logs -f kylo-redpanda
```

### View Kafka Consumer Logs
```powershell
docker compose -f docker-compose.kafka-consumer.yml logs -f
```

---

## 🚀 QUICK START (ALL SYSTEMS)

### Start Everything (Kylo + ScriptHub)
```powershell
# Step 1: Start Kylo Docker Services
cd D:\Project-Kylo
.\start_all_services.ps1

# Step 2: Start Kylo Watchers (2025 + 2026)
cd D:\Project-Kylo
.\scripts\active\start_watchers_by_year.ps1

# Step 3: Start ScriptHub Server (in new window)
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
Start-Process powershell.exe -ArgumentList "-NoProfile", "-NoExit", "-Command", "cd 'D:\Project-Kylo\tools\scripthub_legacy'; `$env:PYTHONPATH = 'D:\Project-Kylo\tools\scripthub_legacy'; python -m uvicorn server:app --host 0.0.0.0 --port 8000"

# Step 4: Run Sync Scripts (one-time or scheduled)
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python run_both_syncs.py
```

---

## 🆘 EMERGENCY COMMANDS

### Kill All Python Processes
```powershell
Get-Process python | Stop-Process -Force
```
**⚠️ WARNING:** This will stop ALL Python processes, including other applications.

### Stop All Watchers
```powershell
cd D:\Project-Kylo
.\scripts\active\stop_all_services.ps1
```

### Stop All Docker Services
```powershell
cd D:\Project-Kylo
docker compose -f docker-compose.kafka-consumer.yml down
docker compose -f docker-compose.kafka.yml down
docker compose -f docker-compose.yml down
```

### Check Running Python Processes
```powershell
Get-Process python | Format-Table Id, ProcessName, Path -AutoSize
```

---

## 📝 NOTES

### Repo Structure (Maintenance)
- **tools/**: Debug scripts, manual tests, one-offs, legacy ScriptHub copies
- **archive/**: Historical data and documentation

### Watcher Log Locations
- **2025 Watcher:** `.\.kylo\instances\KYLO_2025\logs\watcher.log`
- **2026 Watcher:** `.\.kylo\instances\KYLO_2026\logs\watcher.log`
- **Single Watcher:** `.\.kylo\watch.log`

### Watcher State Files
- **Watch State:** `.\.kylo\instances\<INSTANCE_ID>\state\watch_state.json`
- **Posting State:** `.\.kylo\instances\<INSTANCE_ID>\state\posting_state.json`
- **Heartbeat:** `.\.kylo\instances\<INSTANCE_ID>\health\heartbeat.json`

### ScriptHub Log Locations
- **Server Logs:** `D:\Project-Kylo\tools\scripthub_legacy\.logs\server_*.log`
- **Sync Logs:** `D:\Project-Kylo\tools\scripthub_legacy\logs\sync_log_*.log`

### COG System State Files
- **Brand State:** `D:\ScriptHub\cog-allocation-system\data\state\brand_state.json`
- **COG State:** `D:\ScriptHub\cog-allocation-system\data\state\cog_state.json`
- **Drive Watcher State:** `D:\ScriptHub\cog-allocation-system\data\state\drive_watcher_state.json`
- **Drive Watcher Log:** `D:\ScriptHub\cog-allocation-system\data\logs\drive_watcher.log`

### Docker Container Names
- **PostgreSQL:** `kylo-pg`
- **Redpanda:** `kylo-redpanda`
- **Kafka Console UI:** `kylo-kafka-console` (port 8080)
- **Kafka Consumer (Txns):** `kylo-kafka-consumer-txns`
- **Kafka Consumer (Promote):** `kylo-kafka-consumer-promote`

### Ports
- **PostgreSQL:** 5433
- **Redpanda:** 9092 (broker), 9644 (admin)
- **Kafka Console UI:** 8080
- **ScriptHub Server:** 8000

---

## 🔧 TROUBLESHOOTING

### Watcher Not Starting
1. Check Docker is running: `docker ps`
2. Check PostgreSQL is up: `docker ps | findstr kylo-pg`
3. Check Redpanda is up: `docker ps | findstr kylo-redpanda`
4. Verify config: `python bin\validate_config.py`

### Sync Scripts Failing
1. Check service account JSON exists: `D:\Project-Kylo\tools\scripthub_legacy\config\service_account.json`
2. Verify Google Sheets are shared with service account
3. Check PYTHONPATH is set: `$env:PYTHONPATH`
4. Run with verbose output to see errors

### Docker Containers Not Starting
1. Check Docker Desktop is running
2. Check for port conflicts: `netstat -ano | findstr :5433`
3. Check Docker logs: `docker compose logs`
4. Try restarting Docker Desktop

---

**End of Command Reference**
