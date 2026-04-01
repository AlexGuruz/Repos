# Company BI: Reusable Financial and Operational Analysis System

## Purpose

Single company-level view combining **GrowFlow POS** (sales, inventory) and **income/expense transaction data** (Transactions + Bank sheets). Reusable monthly; supports overhead, inventory, margins, labor, sales, expenses, anomalies, and reconciliation.

---

## Layer 1 — Source Mapping

### 1.1 GrowFlow API (POS)

| Source | Connection | Key fields | Use |
|--------|------------|------------|-----|
| **Order items** | `findOrderItems` | SoldAt, GrossPrice, NetPrice, COG, SKU, ProductCategory, Product.Name | Daily/monthly sales, gross revenue, COGS proxy, category mix |
| **Orders** | `findOrders` | CompletedAt, Total, Subtotal, Taxes, Discounts | Order-level sales, tender not in order items |
| **Orders + Transactions** | `findOrders` (nested Transactions) | Tender, Amount | Cash vs card vs other income alignment |
| **Packages** | `findPackages` | createdAt, OriginalQty, CurrentQty, Cost, Product.SKU, ProductCategory | Inventory units, cost of goods, units created/depleted |
| **Transfers** | `findTransfers` (optional) | ReceivedAt, Packages (Cost, OriginalQty, CurrentQty) | Inter-store movement, cost flow |

**Date filters:** `SoldAt` (order items), `CompletedAt` (orders), `createdAt` (packages). All ISO 8601; normalized to UTC then company date.

### 1.2 Financial transaction data (Sheets)

| Source | Spreadsheet ID | Tabs | Key columns | Use |
|--------|----------------|------|-------------|-----|
| **2025 income/expense** | `1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE` | Transactions, Bank | Date, Company, Source (description), Amount | All income and expenses; categorization drives overhead, labor, inventory |
| **2024** | `1D0VcDbzstF-W8hvbg256ooxpc18zCF2qlb1KvWehF2A` | Petty Cash | Initials, Date, Company, Source, Amount | Historical expense/income |
| **Report workbooks** | 2024: `1k3z8813YYmi4PJb4qKEPwolwXMpx0rFNrgSFEwWAX1w`; 2025: `1oPzJXt32sKm854ZXjCZTx9cWmEbq0sZIETrsDK6W_zg` | 2024 Monthly, 2025 Monthly | Month, Income, Expense, Net | Optional read-back for validation |

**Amount convention:** Positive = income, negative = expense. Amounts stored as dollars (not cents).

### 1.3 Derived / internal

- **Company date:** All timestamps normalized to company date (UTC or configured timezone).
- **Fiscal month:** (year, month) for all aggregations.
- **Category tags:** Applied to each transaction from `Source` (description) via rules in `config/categories.yaml`.

---

## Layer 2 — Normalization

### 2.1 Dates

- **GrowFlow:** `SoldAt`, `CompletedAt`, `createdAt` → parse ISO, keep as date (YYYY-MM-DD) for daily, (year, month) for monthly.
- **Sheets:** Detect column by header (DATE, Date). Parse: ISO (YYYY-MM-DD), US (M/D/YYYY), Excel serial → (year, month) and date string.
- **Output:** All metrics use (year, month) and optional date for daily views.

### 2.2 Transaction types

- **Income:** amount > 0. Subtypes: REG 1/2/3 DEPOSIT, SQUARE*, CASH DEPOSIT, etc. (from categorization).
- **Expense:** amount < 0. Subtypes: labor, overhead, inventory-related, other (from categorization).
- **Neutral:** amount = 0 or unparseable → skip or flag.

### 2.3 Category names

- Standard set: `income`, `labor`, `overhead`, `inventory`, `fixed`, `variable`, `other`.
- Subcategories (when identifiable): e.g. `payroll`, `rent`, `utilities`, `subscriptions`, `compliance`, `orders` (inventory-related), `bank_fees`, `transfers`.
- All category logic in `config/categories.yaml`; code applies first-match rules (longer pattern first).

### 2.4 Labor tagging and source priority

- **Payroll is cash-based** and captured via the **employee petty cash sheet**; petty cash CSV reports are **ingested into the database** (Project-Kylo: `core.transactions_unified`). That DB is the **primary labor truth source** for BI.
- **Labor source priority:** (1) **DB-ingested petty-cash payroll** (`core.transactions_unified`, labor patterns on description); (2) Kylo budget sheet–derived labor totals if available; (3) **Transaction-based labor inference** from Sheets categorization only as last resort.
- Labor = sum of expense amounts where description matches labor patterns (PAYROLL, WAGE, SALARY, 941, TAX DEPOSIT, etc.). When using DB: same patterns from `config/categories.yaml` applied to `description` in DB. Confidence: **confirmed** when from DB; **fallback** when from budget; **inferred** when from transaction categorization.
- Outputs expose **Labor source** and **Confidence** (dashboard, labor.csv) so provenance is auditable. No double counting across DB, budget, and transaction inference.

### 2.5 Overhead tagging

- Overhead = operating expenses not labor and not inventory-related: rent, utilities, subscriptions, compliance, bank fees, insurance, etc.
- Fixed vs variable: heuristic by category (rent=fixed; utilities can be variable). Optional; labeled when derivable.

### 2.6 Inventory-related tagging

- Inventory-related = COGS-like or stock-related: “ ORDER” (purchase orders), inventory transfers (if in transactions), supplier payments tagged as inventory.
- Orders spend (negative, description contains “ ORDER”) = primary inventory-related expense in transaction data.

---

## Layer 3 — Metric Engine

### 3.1 Sales (GrowFlow)

- **Daily sales:** Sum(GrossPrice) per day from order items (SoldAt). Units: dollars (GrossPrice/100).
- **Weekly sales:** Sum over 7-day windows (configurable start-of-week).
- **Monthly sales:** Sum(GrossPrice) per (year, month). **Confirmed** from API.
- **Average ticket:** Sum(GrossPrice) / count(distinct Order) per period. Order inferred from order items (same order id or CompletedAt grouping). **Confirmed** if orders fetched.
- **Trend:** Month-over-month or week-over-week % change. **Confirmed.**
- **Volatility:** Std dev of daily sales in period / mean. **Confirmed.**
- **Spikes/dips:** Days where daily sales > mean + 2*std or < mean - 2*std. **Confirmed.**

### 3.2 Expenses (Transactions)

- **Monthly expenses total:** Sum(|amount|) where amount < 0, by (year, month). **Confirmed** from sheets.
- **Expense categories:** Sum by category (labor, overhead, inventory, other). **Confirmed** where categorization rule matches; **estimated** where fallback “other”.
- **Fixed vs variable:** Sum by tag fixed/variable when assigned. **Estimated** (heuristic).
- **Unusual spikes:** Month-over-month increase > threshold (e.g. 25% or $500). **Confirmed** from numbers; cause may need manual review.

### 3.3 Overhead

- **Recurring operating costs:** Sum(expense) where category in overhead subcategories. **Confirmed** where rules match.
- **Non-inventory operating:** Overhead + labor (exclude inventory-related). **Confirmed** with same caveats.
- **Labor:** Sum(expense) where category = labor. **Confirmed** if labor rules present; else **estimated** with confidence label.
- **Rent, utilities, subscriptions, compliance:** Subcategory sums when rules exist. **Confirmed/estimated** by rule quality.

### 3.4 Inventory (GrowFlow + Transactions)

- **Inventory movement:** Units created (sum OriginalQty by createdAt month); current stock (sum CurrentQty). From packages. **Confirmed** from API.
- **Inventory-related cost (transactions):** Sum(expense) where category = inventory (e.g. “ ORDER”). **Confirmed** from sheets.
- **Stock depletion:** Reconstructed daily inventory (existing script) or units sold (order items) vs units created. **Confirmed** (method documented).
- **Slow-moving:** SKUs with low sales vs high current stock (ratio or threshold). **Estimated** (threshold-based).
- **Inventory-to-sales:** Units sold / units created or inventory $ / sales $. **Confirmed** from API + categorization.
- **Shrinkage/adjustments:** Flag when inventory movement or cost doesn’t align with sales (e.g. large negative adjustment). **Estimated** where detectable.

### 3.5 Margins

- **Gross revenue:** Sum(GrossPrice) from GrowFlow. **Confirmed.**
- **COGS proxy (GrowFlow):** Sum(COG) on order items. If API returns COG per line, **confirmed**; else **estimated** (e.g. from package Cost * units sold).
- **COGS proxy (transactions):** Inventory-related expenses (e.g. orders). **Confirmed** for that slice.
- **Operating expenses:** Labor + overhead from transactions. **Confirmed** where categorized.
- **Gross margin:** (Gross revenue − COGS) / Gross revenue. **Estimated** unless COG fully populated; document assumption.
- **Operating margin:** (Gross revenue − COGS − operating expenses) / Gross revenue. **Estimated**; same COGS caveat.
- **What is confirmed:** Revenue, expense totals, categorized expense buckets.
- **What is estimated:** COGS from API vs from transactions, gross/operating margin.
- **What would improve accuracy:** GrowFlow COG per order item; separate labor and inventory GL codes in bank feed.

### 3.6 Labor

- **Labor total by month:** Sum(expense) where category = labor. **Confirmed** if labor rules applied; else **estimated** + confidence.
- **Labor % of sales:** Labor / monthly sales. **Confirmed** (sales) + **confirmed/estimated** (labor).
- **Labor trend:** Month-over-month labor and labor %. **Confirmed/estimated.**
- **Labor pressure:** Labor % above threshold (e.g. > 30%) or rising. **Confirmed** from ratios.

### 3.7 Monthly business health

- **Per month:** sales, inventory-related cost, labor, overhead, total expenses, estimated gross margin, estimated operating margin, anomaly flags, health rating (e.g. green / yellow / red from margin + anomaly).
- **Health rating logic:** Red if margin < 0 or major anomaly; yellow if margin < 5% or anomaly; else green. Thresholds configurable.

---

## Layer 4 — Reconciliation Engine

- **GrowFlow sales (monthly)** vs **recorded income (monthly)** from Transactions/Bank (positive amounts, optionally filtered to REG DEPOSIT + SQUARE + other sales-like descriptions).
- **Difference:** |GrowFlow_sales − recorded_income|. Flag if ≥ $500 (configurable).
- **Likely causes:** Timing (deposits in next month), refunds, fees, other income in bank not in POS. Document in anomaly table.
- **Output:** Reconciliation table: month, GrowFlow_sales, recorded_income, difference, flagged (Y/N), note.

---

## Layer 5 — Reporting Output

### 5.1 Output tables/views

1. **Monthly dashboard:** One row per month: sales, expenses (total + by category), labor, overhead, inventory cost, gross/operating margin, health, anomaly count, **status** (healthy | watch closely | unstable | materially distorted by data issues), **diagnosis**, **biggest positive trend**, **biggest negative trend**, **follow-up**.
2. **Anomaly report:** Rows: date/month, metric, value, prior value, threshold, note.
3. **Expense category report:** Rows: month, category, subcategory, amount, % of expense.
4. **Margin report:** Month, revenue, COGS proxy, gross margin %, operating expense, operating margin %, confidence.
5. **Inventory vs sales report:** Month, units sold, units created, inventory cost (txn), sales $, ratio; optional slow-moving list.
6. **Labor pressure report:** Month, labor $, labor % of sales, trend, flag if above threshold.

### 5.2 Anomaly rules (configurable)

- Unexplained difference (reconciliation) ≥ $500 → flag.
- Month-over-month expense category jump ≥ 25% or ≥ $500 → flag.
- Labor or overhead MoM jump ≥ 25% or ≥ $500 → flag.
- Sales trend: material drop (e.g. > 15% MoM) or volatility spike → flag.
- Margin below threshold (e.g. < 0% or < 5%) → flag.

### 5.3 Delivery

- **Sheets:** Write to a dedicated “Company BI” spreadsheet (configurable ID); one tab per view; overwrite or append by month.
- **CSV:** Optional export of each view for backup or external tools.
- **Run frequency:** Monthly or on-demand via `run_pipeline.py`.

---

## Phase 3 system architecture (automation and validation)

- **Validation** (`lib/validation.py`): Runs after reconcile, before reports. Validates GrowFlow sales (exists, no negative, no missing dates), transaction structure and categories, reconciliation (sales totals, POS-comparable, numeric difference). On failure, pipeline stops with clear error.
- **Trend metrics** (`metrics.calculate_trend_metrics`): Month-over-month sales, expense, labor, margin trend %; flags for negative_sales_trend (≤−15%), labor_pressure (>40% sales), margin_instability. Fed into dashboard and risk score.
- **Inventory intelligence** (`metrics.inventory_intelligence_metrics`, `sku_revenue_summary`): Per-month turnover estimate, inventory_sales_ratio, slow_inventory_indicator; per-SKU total_gross, slow_selling. Output: `output/inventory_analysis.csv`.
- **Risk scoring** (`metrics.calculate_risk_score`): 0–100 score from margin, trends, labor pressure, anomaly count, reconciliation flag. Categories: healthy (0–30), watch closely (31–60), unstable (61–80), operational risk (81+). In dashboard.
- **Automation** (`scripts/monthly_run.py`): Runs pipeline (--no-sheets), archives CSVs to `archive/YYYY-MM/`, optionally runs category rule suggestions. Does not modify YAML.
- **Category suggestions** (`scripts/suggest_category_rules.py`): Writes `output/category_rule_suggestions.csv` from “other” transactions; does not edit categories.yaml.

See **docs/AUTOMATION_AND_VALIDATION.md** for full detail.

---

## File layout

```
company_bi/
  DESIGN.md              (this file)
  METRICS.md             (metric definitions, formulas)
  CATEGORIZATION.md      (rules and tagging logic)
  CONFIDENCE_GAPS.md     (exact vs estimated, missing data)
  config/
    sources.yaml         (sheet IDs, GrowFlow env, output sheet)
    categories.yaml      (description patterns -> category/subcategory)
  lib/
    sources.py           (fetch GrowFlow + Sheets)
    normalization.py    (dates, amounts, types)
    categorization.py   (apply categories to transactions)
    metrics.py          (all calculations, trend, risk, inventory)
    reconcile.py        (sales vs income)
    anomaly.py          (thresholds and flags)
    validation.py       (data integrity checks)
    report.py           (build output tables)
  scripts/
    monthly_run.py      (pipeline + archive + optional suggestions)
    suggest_category_rules.py
    audit_other_expenses.py
  run_pipeline.py       (orchestrate, validate, write)
  archive/              (timestamped monthly outputs)
    YYYY-MM/
      dashboard.csv, anomalies.csv, ...
```

---

## Dependencies

- GrowFlow: existing `lib/growflow_queries.py`, `lib/growflow_graphql.py`, credentials.
- Sheets: Google Sheets API, service account with access to transaction workbooks and (optional) BI output workbook.
- Python 3.10+; PyYAML for config.

---

## Reuse and maintenance

- **Add a source:** Extend `sources.yaml` and Layer 1 in DESIGN.md; add fetch in `lib/sources.py`.
- **Change category:** Edit `config/categories.yaml`; no code change.
- **Change thresholds:** Config or constants in `anomaly.py` / `metrics.py`.
- **New metric:** Add formula in METRICS.md, implement in `metrics.py`, add column to report in `report.py`.
