# Labor Source Correction — Impact Analysis

**Goal:** Show what changed after making DB-ingested petty-cash payroll the primary labor source.

---

## How to produce this report

1. **Before (optional):** Run pipeline with DB disconnected or `labor.database_dsn` commented out; save outputs:
   - `company_bi/output/dashboard.csv`
   - `company_bi/output/labor.csv`
   - Note: labor_source will be `transaction_inference` for all months.
2. **After:** Configure `labor.database_dsn` in `config/sources.yaml` (or set `KYLO_GLOBAL_DSN`) so the pipeline can read `core.transactions_unified`. Run:
   ```bash
   python -m company_bi.run_pipeline --no-sheets --months 24
   ```
3. **Compare:** Fill the tables below from the two runs.

---

## Before / after tables

### Monthly labor totals

| Month | Before (labor total) | After (labor total) | Source used (after) | Change |
|-------|----------------------|---------------------|---------------------|--------|
| …     | …                    | …                   | db_petty_cash_payroll / kylo_budget / transaction_inference | … |

### Labor % of sales

| Month | Before (%) | After (%) | Note |
|-------|------------|-----------|------|
| …     | …          | …         | …    |

### Operating margin %

| Month | Before (%) | After (%) | Note |
|-------|------------|-----------|------|
| …     | …          | …         | …    |

### Risk score / health

| Month | Before (risk_score, health) | After (risk_score, health) | Note |
|-------|-----------------------------|----------------------------|------|
| …     | …                           | …                          | …    |

---

## Source used by month (after run)

| Month | labor_source | confidence |
|-------|--------------|------------|
| …     | …            | …          |

---

## Summary

- **Prior labor:** Understated / Overstated / Similar — (fill after comparison).
- **Months that materially changed:** (list months where labor total or labor % of sales or operating margin moved meaningfully).
- **Validation:** If DB was configured and no month used `db_petty_cash_payroll`, the pipeline raises a validation error; fix by ensuring `core.transactions_unified` has petty-cash data and patterns in `config/categories.yaml` match.

---

*Run the pipeline with and without DB to populate this document.*
