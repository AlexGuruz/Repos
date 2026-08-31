# Growflow Ops Platform

Internal production platform for Nugz retail + company ops (SaaS-ready seams; not multi-tenant yet).

## Architecture

```
GrowFlow GraphQL (scheduled only)
  → growflow_facts.db / transfer_receipts.db / consignment.db / sales_projection.db / sheets_transactions.db
  → domain builders → data/*_latest.json + platform_status_latest.json
  → Platform API :8791 (/api/retail/* + /api/v1/*)
  → ai-lab proxy :8000 → Command Center + Operator Desk
```

## AI read order

1. [`ai-lab/registry/growflow_read_surfaces/catalog.json`](../../ai-lab/registry/growflow_read_surfaces/catalog.json)
2. Operator Desk tools (`operator_growflow_*`)
3. GET APIs only — never Desk refresh / GraphQL at ask-time

## Production start

```powershell
cd E:\Repos\Growflow
.\scripts\reinstall_growflow_scheduled_tasks.ps1   # includes install_platform_scheduler.ps1
.\scripts\start_retail_command_center.ps1
```

Manual refresh:

```powershell
$env:PYTHONPATH="."
python scripts/run_platform_orchestrator.py --kind full --days 30 --preset last_30_days
python scripts/build_company_bi_report.py
```

Release gate:

```powershell
python scripts/run_platform_release_gate.py --skip-build --allow-fixture   # CI sample
python scripts/run_platform_release_gate.py --preset last_30_days --compare  # promote
```

## Host matrix

| Host | Role |
|------|------|
| **Acheron** | Primary: facts, retail API, CC, Desk, platform schedulers |
| **power-1** | Petty cash + Balance/Misc sheet snapshots (deploy scripts) |
| Credentials | GrowFlow OAuth + stashbox SA on the host that runs GraphQL/sheets jobs |

## Company BI

`python -m company_bi.run_pipeline` is a **shim** that exits 2. Use:

- `scripts/build_company_bi_report.py`
- `python -m company_bi.scripts.build_sheets_transactions_db`

## SaaS seams (present, inactive)

- `org_id` in `config/platform.yaml`, fact-store `schema_meta`, JSON `meta.org_id`
- `GrowflowPlatformConfig` path injection (`GROWFLOW_REPO_ROOT`, `GROWFLOW_DATA_DIR`, …)
- `PlatformJob` in `run_platform_orchestrator.py`

Phase 5 (IdP / multi-tenant / hosted workers) is deferred until Phase 0–4 SLOs are green for 2+ weeks.

## SLOs

| Domain | Max age |
|--------|---------|
| Retail dashboard | 4h store hours |
| Consignment ops | 24h |
| Capital | 48h |
| EOD projection | 12h |

Fixture detector: `order_count <= 3` and `store_net_sales < 100` → not healthy unless `meta.fixture=true` / `--allow-fixture`.
