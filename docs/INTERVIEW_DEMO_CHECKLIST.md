# Interview demo checklist

**Updated:** 2026-07-10 (post Phases 2–6 professionalization)

## GitHub repos to show

| Priority | Path in monorepo | Why |
|----------|------------------|-----|
| 1 | `ai-lab/` | Live-work orchestration, worker registry, command center |
| 2 | `Project-Kylo/` | Kafka/event-bus finance pipeline, watchers, audit |
| 3 | `cog-allocation-system/` | Allocation / COG analytics |
| 4 | `geomapper app/` | Geospatial / mapping application |
| 5 | `Growflow/` (selected scripts) | Retail BI integrations (avoid raw CSV dumps in demo) |

Monorepo: [AlexGuruz/Repos](https://github.com/AlexGuruz/Repos) — branch **`main`**.

## Demo commands (run from repo root)

### ai-lab

```powershell
cd ai-lab
python -m pytest tests/test_live_work_orchestration.py tests/test_live_work_timetable.py -q
python scripts/check_worker_connectivity.py
```

Command center (if deps installed): see `ai-lab/command-center/command-center/README.md` or `npm run dev` under frontend after backend `uvicorn`.

### geomapper app

```powershell
cd "geomapper app"
# Follow local README for stack; typical:
npm install
npm run dev
```

### cog-allocation-system

```powershell
cd cog-allocation-system
python -m pytest -q
```

### Project-Kylo (audit / dry-run only for interviews)

```powershell
cd Project-Kylo
python -m kylo.config_validate
# Do NOT enable live posting in demo; config runtime.mode should stay audit.
```

## Do NOT show

- `**/service_account.json`, `.env`, `D:\REMODEL\secrets`, `worker_tunnels.local.json`
- `E:\secrets` or any credential vault paths
- `_rollback/` tarballs, full COG CSV dumps, `PettyCash_Migration_Package/` bulk data
- `ai-lab/Empire/` (nested experiments / personal)
- `Growflow/docs/*Investor*.docx` and internal payroll exports unless redacted
- Accidental drive-root git backup: `E:\.git.backup-pre-professionalization`

## Three-machine alignment (post-sync)

| Machine | Path | `main` HEAD |
|---------|------|-------------|
| Acheron | `E:\Repos` | `cd6b493` |
| worker-node | `C:\worker\repos` | `cd6b493` |
| power-1 | `C:\worker\repos` | `cd6b493` |

**Notes:** Submodule `activepieces` may show ` m` on workers — expected if submodule pointer differs locally. Legacy standalone **`C:\Project-Kylo`** on worker-node (own `.git`); on power-1 junction → `C:\worker\repos\Project-Kylo`.

## Pre-demo smoke (5 min)

1. `git -C E:\Repos status -sb -uno` — clean tracked tree on Acheron
2. Open GitHub `main` at `cd6b493` and spot-check recent commits (ai-lab, Kylo, docs)
3. Run one pytest module per flagship project above
