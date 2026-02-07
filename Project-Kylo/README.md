# Project-Kylo

Maintenance-only repository for the Kylo processing system. Development is paused; keep the system running as-is.

## Quick Start (Maintenance)

```powershell
# Start core services (Postgres + Kafka/Redpanda + consumers)
.\start_all_services.ps1

# Start watchers for 2025 + 2026
.\scripts\active\start_watchers_by_year.ps1

# Stop all services
.\scripts\active\stop_all_services.ps1
```

## Key Docs

- `COMMAND_REFERENCE.md` - all operational commands
- `MAINTENANCE.md` - handoff guide for maintainers
- `docs/README.md` - operational documentation index

## Repository Structure

Active runtime code:
- `services/`, `kylo/`, `bin/`
- `config/`, `db/`, `data/`, `workflows/`
- `telemetry/` (used by runtime and Docker build)

Structured non-runtime assets:
- `tools/` - debug scripts, manual tests, one-offs, legacy ScriptHub duplicates
- `archive/` - historical data and documentation

## Notes

- Runtime-critical files kept in place: `telemetry/`, `pg_hba_fixed.conf`
- Historical planning and reports are under `archive/docs/`
