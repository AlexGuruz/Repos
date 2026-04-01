# Automation and Validation — Phase 3 System

**Goal:** Make the Company BI framework stable, verifiable, and easy to run every month with minimal manual intervention.

---

## 1. Validation layer

**Module:** `company_bi/lib/validation.py`

The pipeline runs validation **after** normalization, categorization, and reconciliation and **before** building reports. On failure it stops and logs a clear error.

### Checks

| Check | What is validated |
|-------|-------------------|
| **growflow_sales_exists** | GrowFlow sales dataset is not empty (normalized_items or by_month_sales). |
| **growflow_no_negative_sales** | No negative gross in order items or monthly sales. |
| **growflow_no_missing_dates** | Every order item has date_ym. |
| **growflow_inventory_structure** | Monthly sales data has expected structure (e.g. gross key). |
| **transactions_date_column** | Tagged transactions have date_ym. |
| **transactions_amount_numeric** | Transaction amount is numeric. |
| **category_known** | Every tagged row has category in {income, labor, overhead, inventory, other}. |
| **reconciliation_sales_totals** | Reconciliation rows have growflow_sales where expected. |
| **reconciliation_pos_comparable** | Reconciliation row has pos_comparable_income. |
| **reconciliation_difference_numeric** | Difference column is numeric. |

**Usage:** Validation is invoked from `run_pipeline.py`. On `ValidationError`, the pipeline exits with code 1 and prints the check name and message.

---

## 2. Trend metrics

**Module:** `company_bi/lib/metrics.py` — `calculate_trend_metrics()`

### Computed per month

- **sales_trend_pct** — Month-over-month sales % change (from sales_metrics.trend_pct).
- **expense_trend_pct** — (current total expense − prior) / prior × 100.
- **labor_trend_pct** — Month-over-month labor % change (from labor_metrics).
- **margin_trend_pct** — Operating margin percentage point change vs prior month.

### Interpretation flags

- **negative_sales_trend** — sales_trend_pct ≤ −15%.
- **labor_pressure** — labor % of sales > 40%.
- **margin_instability** — operating margin < 0 for the month.

These feed the dashboard (trend columns) and risk scoring.

---

## 3. Inventory intelligence

**Module:** `company_bi/lib/metrics.py` — `inventory_intelligence_metrics()`, `sku_revenue_summary()`

### Monthly metrics (by month)

- **inventory_turnover_estimate** — revenue / inventory_cost (transaction category “inventory”) when both > 0.
- **inventory_sales_ratio** — inventory_cost / revenue.
- **slow_inventory_indicator** — True when inventory_sales_ratio > 0.5.

### SKU summary (from order items)

- **total_gross** — Sum of gross per SKU.
- **line_count**, **months_active** — Count of lines and distinct months.
- **slow_selling** — True when total_gross < $500 or months_active ≤ 1.

**Output:** `company_bi/output/inventory_analysis.csv` (monthly block + SKU block). See **METRICS.md** for formulas.

---

## 4. Risk scoring

**Module:** `company_bi/lib/metrics.py` — `calculate_risk_score()`

### Formula (0–100)

Points are summed (capped at 100):

- Operating margin < −10%: +40; < 0%: +25; < 5%: +10.
- Sales trend ≤ −15%: +20.
- Expense trend > 25%: +10.
- Labor pressure (labor % of sales > 40%): +15.
- Per anomaly: +5 (max +25).
- Reconciliation flagged: +10.

### Risk categories

| Score | Category |
|-------|----------|
| 0–30 | healthy |
| 31–60 | watch closely |
| 61–80 | unstable |
| 81–100 | operational risk |

Dashboard columns: **Risk score**, **Risk category**.

---

## 5. Automation workflow

**Script:** `company_bi/scripts/monthly_run.py`

### Steps

1. **Run pipeline** — `python -m company_bi.run_pipeline --no-sheets --months N` (validation runs inside).
2. **Archive** — Copy dashboard, anomalies, margin, reconciliation, expense_category, labor, inventory_analysis (and category_rule_suggestions if present) to `company_bi/archive/YYYY-MM/`.
3. **Category suggestions** (optional) — `python -m company_bi.scripts.suggest_category_rules --months N`; output to `output/category_rule_suggestions.csv` and copy to archive.

### Usage

```bash
# From Growflow repo root
python -m company_bi.scripts.monthly_run --months 12
python -m company_bi.scripts.monthly_run --months 6 --skip-suggestions
```

### Archive layout

```
company_bi/archive/
  2026-03/
    dashboard.csv
    anomalies.csv
    margin.csv
    reconciliation.csv
    expense_category.csv
    labor.csv
    inventory_analysis.csv
    category_rule_suggestions.csv  # if run
```

---

## 6. Category rule suggestions (no auto-edit)

**Script:** `company_bi/scripts/suggest_category_rules.py`

- Loads transactions, categorizes with current `categories.yaml`, filters to “other” (expenses).
- Groups by normalized description; ranks by total amount and count.
- Suggests category from keyword hints (labor, overhead, inventory); confidence low/medium.
- **Writes** `company_bi/output/category_rule_suggestions.csv` only. **Does not modify** `categories.yaml`; operator reviews and edits YAML manually.

---

## 7. Operator dashboard columns (Phase 3)

Dashboard CSV columns:

Month, Sales, POS income, Total expense, Labor, Overhead, Inventory cost, COGS, Gross margin %, Operating margin %, Health, Anomalies, Sales trend %, Expense trend %, Labor trend %, Margin trend %, Risk score, Risk category, Status, Diagnosis, Biggest positive, Biggest negative, Follow-up.

All new metrics are documented in **METRICS.md** and **DESIGN.md** (Phase 3 system architecture).
