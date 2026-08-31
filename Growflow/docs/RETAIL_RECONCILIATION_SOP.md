# Retail Reconciliation — Operator SOP

This document describes how to export a trusted reference from native GrowFlow and run the reconciliation release gate before relying on Operations metrics in Command Center.

**Related:** `docs/RETAIL_DASHBOARD_METRICS.md`, `scripts/reconcile_retail_dashboard.py`, `scripts/run_retail_release_gate.py`

---

## When to run

- After `ingest_growflow_facts.py` + `build_retail_dashboard.py`
- Before promoting Operations metrics to production use
- After changing fact ingest, normalization, or dashboard formulas
- On a schedule (e.g. daily) once reference export is automated

---

## Step 1 — Match filters

The reference export **must use the same scope** as the dashboard build:

| Filter | Dashboard flag | Reference must match |
|--------|----------------|----------------------|
| Period | `--preset last_30_days` or `--start` / `--end` | Same date range |
| Store | `--store-id` (if set) | Same store |
| Channel | `--channel all\|in_store\|online` | Same channel |

Default timezone: `America/Chicago` (from `config/retail_dashboard.yaml`).

---

## Step 2 — Export reference from GrowFlow

There is **no automated GrowFlow export API** in this repo. An operator exports from the native dashboard or a manual report.

### Option A — CSV (recommended)

1. In GrowFlow, run/export a report for the **same period** as the dashboard.
2. Convert or map totals into the long-format CSV:

```csv
section,key,metric,value
period,,start,2026-06-01
period,,end,2026-06-30
store,total,net_sales,123456.78
budtender,Alice,net_sales,45000.00
budtender,Bob,net_sales,32000.00
daily,2026-06-01,net_sales,4100.00
daily,2026-06-02,net_sales,3900.00
brand,BrandA,net_sales,25000.00
brand,BrandB,net_sales,18000.00
```

3. Save to:

```
data/reference/growflow_retail_dashboard_export.csv
```

Required columns: `section`, `key`, `metric`, `value`.

Sections: `period`, `store`, `budtender`, `daily`, `brand`, `category_budtender` (optional).

### Option B — JSON snapshot

Save a partial dashboard-shaped JSON (see `tests/fixtures/retail_dashboard/reference_golden.json`) to:

```
data/reference/growflow_retail_dashboard_export.json
```

---

## Step 3 — Build dashboard

```powershell
cd e:\Repos\Growflow
$env:PYTHONPATH="."

python scripts/ingest_growflow_facts.py --days 30

python scripts/build_retail_dashboard.py --preset last_30_days --compare --strict
```

Output: `data/retail_dashboard_latest.json`

### Build + reconcile in one step

```powershell
python scripts/build_retail_dashboard.py `
  --preset last_30_days `
  --compare `
  --strict `
  --reconcile `
  --reference-csv data/reference/growflow_retail_dashboard_export.csv
```

---

## Step 4 — Run reconciliation

### Sum gates only (no external reference)

```powershell
python scripts/reconcile_retail_dashboard.py --latest
```

### Full reconcile vs CSV

```powershell
python scripts/reconcile_retail_dashboard.py `
  --dashboard-json data/retail_dashboard_latest.json `
  --reference-csv data/reference/growflow_retail_dashboard_export.csv `
  --out data/retail_reconciliation_latest.json `
  --money-tolerance 1.00 `
  --pct-tolerance 0.005
```

### Full reconcile vs JSON

```powershell
python scripts/reconcile_retail_dashboard.py `
  --dashboard-json data/retail_dashboard_latest.json `
  --reference-json data/reference/growflow_retail_dashboard_export.json
```

---

## Step 5 — Release gate (CI / pre-promote)

Single command: build (strict) + reconcile:

```powershell
python scripts/run_retail_release_gate.py `
  --preset last_30_days `
  --compare `
  --reference-csv data/reference/growflow_retail_dashboard_export.csv
```

PowerShell wrapper:

```powershell
.\scripts\run_retail_release_gate.ps1 -Preset last_30_days -Compare `
  -ReferenceCsv data\reference\growflow_retail_dashboard_export.csv
```

Require reference file (fail if missing):

```powershell
python scripts/run_retail_release_gate.py --require-reference --reference-csv data/reference/growflow_retail_dashboard_export.csv
```

---

## Interpreting results

| Exit code | Meaning |
|-----------|---------|
| 0 | Pass — metrics reconciled within tolerance |
| 1 | Fail — blocking check exceeded tolerance or build sum validation failed |
| 2 | Invalid input — missing dashboard, bad CSV columns, missing required reference |

Report file: `data/retail_reconciliation_latest.json`

| `status` | Action |
|----------|--------|
| `pass` | Safe to use Operations metrics |
| `fail` | **Do not** rely on Operations metrics; investigate deltas |
| `warning` | Review warnings; optional reference sections missing |

### Blocking checks (release gate fails)

- `sum_gate_budtender_net_sales`
- `sum_gate_brand_net_sales`
- `sum_gate_daily_net_sales`
- `ref_store_net_sales`
- `ref_budtender_net_sales:*`
- `ref_daily_net_sales:*`
- `ref_brand_net_sales:*`

Non-blocking: `ref_category_budtender_net_sales:*` (warning only).

### Tolerance

Pass if **either**:

- `|actual − expected| ≤ $1.00` (default), or
- `|delta_pct| ≤ 0.5%` when expected ≠ 0

Configure in `config/retail_dashboard.yaml` or CLI flags.

---

## Command Center visibility

After reconciliation, Command Center **Operations** tab shows a trust strip sourced from `GET /api/retail/reconciliation` (via ai-lab proxy). Status: pass / fail / warning / missing.

---

## CI integration

No `.github/workflows` in Growflow today. Use this as the CI step:

```bash
cd /path/to/Growflow
export PYTHONPATH=.
python scripts/run_retail_release_gate.py \
  --preset last_30_days \
  --compare \
  --require-reference \
  --reference-csv data/reference/growflow_retail_dashboard_export.csv
```

Sum-gates-only CI (no reference file):

```bash
python scripts/build_retail_dashboard.py --preset last_30_days --strict --reconcile
```
