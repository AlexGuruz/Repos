# Kylo Maintenance Guide

This repo is in maintenance-only mode. Use this guide to keep systems running and recover after crashes.

## Core Services

Start all services:
```powershell
.\start_all_services.ps1
```

Start watchers (2025 + 2026):
```powershell
.\scripts\active\start_watchers_by_year.ps1
```

Stop all services:
```powershell
.\scripts\active\stop_all_services.ps1
```

## Health Checks

Docker status:
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Logs:
```powershell
docker compose -f docker-compose.yml -f docker-compose.kafka.yml -f docker-compose.kafka-consumer.yml logs -f
```

## Watcher Logs

- `./.kylo/instances/KYLO_2025/logs/watcher.log`
- `./.kylo/instances/KYLO_2026/logs/watcher.log`

## ScriptHub (External)

ScriptHub runtime lives outside this repo:
- `D:\Project-Kylo\tools\scripthub_legacy`

Use `COMMAND_REFERENCE.md` for ScriptHub commands.

## Structured Folders

- `tools/` - debug scripts, manual tests, one-offs, legacy ScriptHub copies
- `archive/` - historical data and reports

## Runtime-Critical Files (Do Not Move)

- `telemetry/` (used by runtime and Docker image build)
- `pg_hba_fixed.conf` (mounted in docker-compose.yml)

## Troubleshooting

- If watchers stop: restart with `scripts\start_watchers_by_year.ps1`
- If Kafka/DB down: rerun `start_all_services.ps1`
- If Python processes hang: use `scripts\kill_python_processes.ps1`

## References

- `COMMAND_REFERENCE.md`
- `docs/README.md`
- `docs/KAFKA_EVENT_BUS_RUNBOOK_WINDOWS.md`
