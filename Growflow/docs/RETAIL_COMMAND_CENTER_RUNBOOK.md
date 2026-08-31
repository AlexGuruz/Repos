# Retail Command Center — Live Runbook

Bring up the Retail Intelligence stack locally (or on a single host) for Command Center use.

**“Live” here means:** Command Center webapp running with Growflow retail API reachable via ai-lab proxy — not a separate hosted deployment.

---

## Architecture

```
Command Center UI (Vite :5173)
    → ai-lab API (:8000) /api/retail/*
        → Growflow Retail API (:8791) /api/retail/*
            → data/*_latest.json (pre-built)
```

No GraphQL on request-time paths. GraphQL runs only in `ingest_growflow_facts.py` and background capital projection jobs.

---

## Prerequisites

| Requirement | Location |
|-------------|----------|
| Python 3.11+ | Growflow + ai-lab backends |
| Node 18+ | Command Center frontend |
| `growflow_facts.db` | `data/growflow_facts.db` (from ingest) |
| GrowFlow credentials | `config/config.yaml` / credentials path |

---

## Environment variables

### ai-lab Command Center backend

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROWFLOW_RETAIL_API_URL` | `http://127.0.0.1:8791` | Growflow FastAPI base URL |

Add to `command-center/backend/.env`:

```
GROWFLOW_RETAIL_API_URL=http://127.0.0.1:8791
```

For a remote Growflow host:

```
GROWFLOW_RETAIL_API_URL=http://192.168.1.50:8791
```

### Command Center frontend

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `http://127.0.0.1:8000` | ai-lab API (use 127.0.0.1 when Vite binds 127.0.0.1) |
| `VITE_WS_URL` | `ws://127.0.0.1:8000/ws/events` | WebSocket events (approvals) |

Copy `frontend/.env.example` to `frontend/.env` if missing.

**CORS:** ai-lab backend `CORS_ORIGINS` must include `http://127.0.0.1:5173` when using `--host 127.0.0.1`.

---

## Startup sequence

### Terminal 1 — Growflow Retail API

```powershell
cd e:\Repos\Growflow
.\scripts\run_retail_dashboard_api.ps1
```

Verify:

```powershell
curl http://127.0.0.1:8791/api/health
```

### Terminal 2 — Build data (first time or after ingest)

```powershell
cd e:\Repos\Growflow
$env:PYTHONPATH="."
python scripts/ingest_growflow_facts.py --days 30
python scripts/build_retail_dashboard.py --preset last_30_days --compare --strict --reconcile
python scripts/build_retail_capital.py
python scripts/build_retail_consignment.py
```

Optional release gate with reference:

```powershell
python scripts/run_retail_release_gate.py --preset last_30_days --compare `
  --reference-csv data/reference/growflow_retail_dashboard_export.csv
```

### Terminal 3 — ai-lab Command Center backend

```powershell
cd e:\Repos\ai-lab\command-center\command-center\backend
# activate venv if used
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Verify retail proxy:

```powershell
curl http://localhost:8000/api/retail/health
curl http://localhost:8000/api/retail/reconciliation
```

### Terminal 4 — Command Center frontend

```powershell
cd e:\Repos\ai-lab\command-center\command-center\frontend
npm install
npm run dev
```

Open: `http://localhost:5173` → Retail Intelligence panel.

---

## API route map (verified)

| Growflow `:8791` | ai-lab proxy | Frontend `api.js` |
|------------------|--------------|-------------------|
| `GET /api/health` | `/api/retail/health` | `retailHealth` |
| `GET /api/retail/dashboard` | `/api/retail/dashboard` | `retailDashboard` |
| `GET /api/retail/reconciliation` | `/api/retail/reconciliation` | `retailReconciliation` |
| `GET /api/retail/stores` | `/api/retail/stores` | `retailStores` |
| `POST /api/retail/refresh` | `/api/retail/refresh` | `retailRefresh` |
| `GET /api/retail/jobs/{id}` | `/api/retail/jobs/{id}` | `retailJob` |
| `GET /api/retail/capital` | `/api/retail/capital` | `retailCapital` |
| `GET /api/retail/consignment` | `/api/retail/consignment` | `retailConsignment` |
| `POST /api/retail/capital/scenario` | same | `retailCapitalScenario` |
| `POST .../{id}/execute` | `POST .../{id}/approve` | `retailCapitalApprove` |
| `POST .../{id}/deny` | same | `retailCapitalDeny` |

---

## Trust / reconciliation in UI

Operations tab shows:

1. **Reconciliation strip** — pass/fail/warning/missing from `retail_reconciliation_latest.json`
2. **Sum validation strip** — from dashboard `meta.validation`

If reconciliation is `missing`, run `scripts/reconcile_retail_dashboard.py` or the release gate. Empty dev environments are expected until first build.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `503 Growflow retail API unreachable` | Start `run_retail_dashboard_api.ps1`; check `GROWFLOW_RETAIL_API_URL` |
| `404 No dashboard built yet` | Run ingest + `build_retail_dashboard.py` |
| Reconciliation `missing` | Run reconcile or release gate after build |
| Capital tab empty | Run `build_retail_capital.py` or approve a scenario |
| Consignment empty | Populate `data/consignment.db` + `build_retail_consignment.py` |
| CORS errors | Ensure Growflow CORS includes frontend origin; ai-lab `CORS_ORIGINS` |

---

## Production notes

- Growflow API binds `127.0.0.1:8791` by default — expose only via ai-lab proxy on a trusted network.
- Set `GROWFLOW_RETAIL_API_URL` to the Growflow host if API runs on another machine.
- Run `run_platform_release_gate.py` (or `run_retail_release_gate.py`) before promoting dashboard JSON.
- Reference export remains a manual operator step unless you add automation later.
- Set `GROWFLOW_RETAIL_ORG` (e.g. `nugzdispensary`) or `GROWFLOW_GRAPHQL_URL` before ingest — otherwise GraphQL returns `ENDPOINT_NOT_FOUND`.
- Prefer `scripts/run_platform_orchestrator.py` for scheduled full refresh; see `docs/GROWFLOW_OPS_PLATFORM.md`.
- AI agents: start at `ai-lab/registry/growflow_read_surfaces/catalog.json`.

See also: `docs/RETAIL_RECONCILIATION_SOP.md`, `docs/GROWFLOW_OPS_PLATFORM.md`, `docs/SAAS_PHASE_DEFERRED.md`
