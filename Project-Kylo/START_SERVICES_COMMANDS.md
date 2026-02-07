# Individual Service Start Commands

## Services Currently NOT Running

### 1. Kylo Watcher
**Description:** Monitors for changes and triggers intake/mover/posting services

**Command:**
```powershell
cd D:\Project-Kylo
$env:KYLO_WATCH_INTERVAL_SECS = "300"
$env:PYTHONUNBUFFERED = "1"
python -u -m bin.watch_all *> .\.kylo\watch.log
```

**Or as background process:**
```powershell
cd D:\Project-Kylo
$env:KYLO_WATCH_INTERVAL_SECS = "300"
$env:PYTHONUNBUFFERED = "1"
Start-Process powershell.exe -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "cd D:\Project-Kylo; `$env:KYLO_WATCH_INTERVAL_SECS = '300'; `$env:PYTHONUNBUFFERED = '1'; python -u -m bin.watch_all *> .\.kylo\watch.log"
```

**Dual-watchers (2025 + 2026) in separate windows (recommended for year routing):**

This starts **two watcher instances** (instance IDs `KYLO_2025` and `KYLO_2026`) that process **ALL companies** (NUGZ, EMPIRE, PUFFIN, JGD) but only monitor/post transactions for their assigned year (2025 or 2026) based on `year_workbooks` config.

Each instance will have isolated files:
- **watcher log**: `.kylo\instances\<INSTANCE_ID>\logs\watcher.log`
- **watcher state**: `.kylo\instances\<INSTANCE_ID>\state\watch_state.json`
- **posting state**: `.kylo\instances\<INSTANCE_ID>\state\posting_state.json`
- **heartbeat**: `.kylo\instances\<INSTANCE_ID>\health\heartbeat.json`

```powershell
cd D:\Project-Kylo
.\scripts\active\start_watchers_by_year.ps1
```

To stop them, run:

```powershell
cd D:\Project-Kylo
.\scripts\active\stop_all_services.ps1
```

**Single watcher (scoped + instance-id):**

```powershell
cd D:\Project-Kylo
python -m bin.watch_all --years 2025 --instance-id JGD_2025
```

---

## Layered configuration (global → company → instance)

If `config/global.yaml` exists and you set `KYLO_INSTANCE_ID`, Kylo will automatically load:
- `config/global.yaml`
- `config/companies/<COMPANY>.yaml`
- `config/instances/<INSTANCE_ID>.yaml` (if present)

Then it merges them in that order: **instance overrides company overrides global**.

Notes:
- Lists are **replaced** (no implicit union).
- You can point `KYLO_CONFIG_PATH` at `config/global.yaml` if you want to be explicit.

---

## Safe mode / kill switch (damage prevention)

These controls are **fast toggles**. They are also surfaced in the heartbeat JSON:
`.kylo\instances\<INSTANCE_ID>\health\heartbeat.json`

### Global read-only mode (monitor only, no posting)

```powershell
cd D:\Project-Kylo
$env:KYLO_READ_ONLY = "1"
python -m bin.watch_all --years 2025 --instance-id JGD_2025
```

To turn it off:

```powershell
Remove-Item Env:\KYLO_READ_ONLY -ErrorAction SilentlyContinue
```

### Disable posting for specific instances

```powershell
$env:KYLO_DISABLE_POSTING_FOR = "JGD_2025,NUGZ_2026"
```

### Disable posting for specific companies

```powershell
$env:KYLO_DISABLE_POSTING_COMPANIES = "JGD,NUGZ"
```

To clear either disable list:

```powershell
Remove-Item Env:\KYLO_DISABLE_POSTING_FOR -ErrorAction SilentlyContinue
Remove-Item Env:\KYLO_DISABLE_POSTING_COMPANIES -ErrorAction SilentlyContinue
```

### Circuit breaker (auto-pause on repeated failures)

Configured in YAML (layered config compatible):

```yaml
runtime:
  circuit_breaker:
    max_consecutive_failures: 5
    pause_minutes: 30
```

---

### 2. ScriptHub FastAPI Server (local folder)
**Description:** Webhook server for ScriptHub services

**Command:**
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Or with logging:**
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
$logDir = ".\.logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logFile = "$logDir\server_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> $logFile
```

**Or as background process:**
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
$logDir = ".\.logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logFile = "$logDir\server_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
Start-Process powershell.exe -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "cd 'D:\Project-Kylo\tools\scripthub_legacy'; `$env:PYTHONPATH = 'D:\Project-Kylo\tools\scripthub_legacy'; python -m uvicorn server:app --host 0.0.0.0 --port 8000 *> '$logFile'"
```

---

### 3. ScriptHub Sync Scripts (local folder)
**Description:** Runs JGDTRUTH Dynamic Columns and Sync Bank

**Command:**
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
python run_both_syncs.py
```

**Or with logging:**
```powershell
cd "D:\Project-Kylo\tools\scripthub_legacy"
$env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
$logDir = ".\logs"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$syncLog = "$logDir\sync_log_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
$errorLog = "$logDir\sync_error_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
python run_both_syncs.py *> $syncLog 2> $errorLog
```

---

## Note on Intake, Mover, and Posting Services

These services are **NOT standalone services**. They are triggered automatically by:
- **Watcher** (`watch_all.py`) - Monitors for changes and triggers intake/mover/posting
- **Kafka Consumers** (already running in Docker) - Process transactions and trigger mover
- **Webhooks** - External triggers via n8n or other systems

You don't need to start them individually - they run when triggered by the watcher or Kafka consumers.

---

## Quick Start All (Alternative)

If you want to start everything at once, you can use the existing startup script:

```powershell
cd D:\Project-Kylo
.\scripts\active\auto_start_kylo.ps1
```

This will start all services including the watcher and ScriptHub server.
