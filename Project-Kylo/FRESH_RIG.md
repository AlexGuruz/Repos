# Project-Kylo: Fresh Rig Setup

One-time setup for a new machine. After this, use `start_all_services.ps1` and `scripts\active\start_watchers_by_year.ps1`.

## Prerequisites

- **Docker Desktop** – Running (required for Postgres, Redpanda, Kafka consumers)
- **Python 3.11+** – For watchers and ScriptHub (install from [python.org](https://python.org) or via `winget install Python.Python.3.11`)

## Boot Sequence (Already Done)

1. **Start Docker services** (Postgres, Redpanda, Kafka, consumers)
   ```powershell
   cd e:\Repos\Project-Kylo
   .\start_all_services.ps1
   ```

2. **Bootstrap database** (creates `kylo_global`, company DBs, applies DDL)
   ```powershell
   .\scripts\bootstrap_fresh.ps1
   ```

3. **Install Python deps** (for watchers)
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```

4. **Add Google service account** (for Sheets posting)
   - Place `service_account.json` in `.secrets\`
   - Ensure it has access to the spreadsheets in `config/global.yaml`

5. **Start watchers** (optional; requires Python)
   ```powershell
   .\scripts\active\start_watchers_by_year.ps1
   ```

## Current Status

- ✅ Docker network `remodel_default` created
- ✅ Postgres (kylo-pg) on port 5433
- ✅ Redpanda (Kafka) on port 9092
- ✅ Kafka Console UI at http://localhost:8080
- ✅ Kafka consumer containers running
- ✅ Database `kylo_global` and company DBs bootstrapped

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `D:\REMODEL\secrets` not found | Use `docker-compose.kafka-consumer.override.yml` (already in repo) so `.secrets` is used |
| Python not found | Install Python 3.11+, ensure it's in PATH (not the Windows Store stub) |
| Watchers need Sheets | Add `service_account.json` to `.secrets\` and set `KYLO_SECRETS_DIR` (done automatically by watcher script) |

## Quick Start (Next Time)

```powershell
.\start_all_services.ps1
.\scripts\active\start_watchers_by_year.ps1
```
