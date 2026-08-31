# Company BI — Reusable Financial & Operational Analysis

Combines **GrowFlow POS** (sales, inventory) and **transaction sheets** (income/expense) into one company-level view: overhead, inventory, margins, labor, sales, monthly expenses, reconciliation, and anomalies.

## Quick run (from Growflow repo root)

`python -m company_bi.run_pipeline` is **retired** (shim exits 2). Use:

```bash
# Company BI report (facts DB + optional sheets_transactions.db)
PYTHONPATH=. python scripts/build_company_bi_report.py --months 6

# Load financial Google Sheets into local SQLite
PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db
```

Output: `data/company_bi_report_latest.json`.

**Automated monthly run (legacy wrapper still calls run_pipeline — prefer orchestrator):**

```bash
PYTHONPATH=. python scripts/build_company_bi_report.py --months 12
```

See `docs/GROWFLOW_OPS_PLATFORM.md`.

## Docs

| Doc | Purpose |
|-----|---------|
| **DESIGN.md** | System layers: source mapping, normalization, metric engine, reconciliation, reporting |
| **METRICS.md** | Metric definitions and formulas (sales, expense, margin, labor, health) |
| **CATEGORIZATION.md** | How transactions are tagged (income, labor, overhead, inventory) |
| **CONFIDENCE_GAPS.md** | What is confirmed vs estimated; missing data; how to strengthen |
| **FIRST_REPORT.md** | First-pass company report (real run); interpretation and anomaly summary |
| **CHANGELOG_PHASE2.md** | Phase 2: rules added, formulas changed, new docs, unresolved issues |
| **docs/PHASE2_SYSTEM_AUDIT.md** | Module map, metric/category flow, weak points, edit targets |
| **docs/OTHER_EXPENSE_AUDIT.md** | Before/after other %, rules added, unresolved items |
| **docs/RECONCILIATION_DIAGNOSTIC.md** | Reconciliation path, POS-comparable income, required table |
| **docs/MARGIN_METHOD_AUDIT.md** | Margin formulas, inputs, confirmed vs proxy |
| **docs/LABOR_OVERHEAD_AUDIT.md** | Labor/overhead rules, recurring items, confidence |
| **docs/LABOR_SOURCE_TRACE.md** | Labor data path: petty-cash CSV → DB → BI; source priority |
| **docs/LABOR_SOURCE_IMPACT.md** | Before/after impact of labor-source correction (run post-change) |
| **docs/AUTOMATION_AND_VALIDATION.md** | Phase 3: validation, trend metrics, inventory intelligence, risk scoring, automation workflow |

## Config

- **config/sources.yaml** — Spreadsheet IDs, GrowFlow settings, **labor** (optional `database_dsn` for DB-ingested petty-cash payroll), anomaly thresholds, output sheet.
- **config/categories.yaml** — Pattern → category rules for labor, overhead, inventory, income.

**Labor source:** Payroll is cash-based and captured via the employee petty cash sheet; petty cash CSV reports are ingested into the database. Company BI uses **DB-ingested payroll as the primary labor source** (optional `labor.database_dsn` or `KYLO_GLOBAL_DSN`); budget and transaction inference are fallbacks. See **docs/LABOR_SOURCE_TRACE.md**.

## Credentials

- GrowFlow: `GROWFLOW_CREDENTIALS_PATH` or `E:/secrets/gcp/growflowapi.txt`
- Google Sheets: `GOOGLE_APPLICATION_CREDENTIALS` or `E:/secrets/gcp/sa.json`
