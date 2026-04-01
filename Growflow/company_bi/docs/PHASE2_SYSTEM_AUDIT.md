# Phase 2 System Audit — Company BI

**Purpose:** Document exactly how current outputs are produced before changing logic. Use this as the edit map for Phase 2 refinement.

---

## 1. Module / file map

| File | Responsibility | Key exports |
|------|----------------|-------------|
| **run_pipeline.py** | Orchestration: load config → fetch GrowFlow + Sheets → normalize → categorize → metrics → reconcile → anomalies → build report rows → write CSV or Sheets | main() |
| **lib/sources.py** | Config load (sources.yaml, categories.yaml); GrowFlow fetch (order items, packages); Sheets service; column detection; parse_amount, parse_date_to_ymd | load_sources_config, load_categories_config, fetch_growflow_order_items, get_sheets_service, detect_transaction_columns, parse_amount, parse_date_to_ymd |
| **lib/normalization.py** | Normalize order items → date_ym, gross, cog; normalize transaction rows → date_ym, amount, source_raw/source_upper; aggregate_sales_by_month | normalize_order_items, normalize_transactions, aggregate_sales_by_month |
| **lib/categorization.py** | Build rules from categories.yaml; tag each transaction (income/labor/overhead/inventory/other); aggregate by category by month; aggregate income by month | _build_rules, categorize_transaction, apply_categorization, aggregate_by_category_month, aggregate_income_by_month |
| **lib/metrics.py** | Sales metrics (gross, trend, volatility, avg_ticket); expense metrics (total, labor, overhead, inventory, other); margin_metrics (revenue, cogs_proxy, op_ex, gross/operating margin %, confidence); labor_metrics; health_rating | sales_metrics, expense_metrics, margin_metrics, labor_metrics, health_rating |
| **lib/reconcile.py** | Monthly reconciliation: GrowFlow sales vs recorded income; difference; flag if ≥ threshold | reconcile_monthly |
| **lib/anomaly.py** | Apply thresholds: reconciliation flagged, expense MoM %, sales drop %, margin red/yellow; return anomaly list + count_by_ym | run_anomalies |
| **lib/report.py** | Build table rows for dashboard, anomaly report, expense category, margin, reconciliation, labor | build_monthly_dashboard, build_anomaly_report, build_expense_category_report, build_margin_report, build_reconciliation_report, build_labor_report |
| **config/sources.yaml** | Transaction spreadsheet IDs (2024/2025/2026), GrowFlow credentials path, sheets output ID, anomaly thresholds | — |
| **config/categories.yaml** | Pattern → category/subcategory (income, labor, inventory, overhead); optional fixed/variable | — |

---

## 2. Current metric flow

```
run_pipeline.main()
  │
  ├─ load_sources_config() → cfg
  ├─ fetch_growflow_order_items(months_back) → order_nodes
  ├─ normalize_order_items(order_nodes) → normalized_items
  ├─ aggregate_sales_by_month(normalized_items) → by_month_sales   [(y,m): { gross, cog, lines, daily_gross }]
  ├─ sales_metrics(by_month_sales, {}) → sales_metrics_by_ym
  │
  ├─ [Sheets] get_sheets_service(); for each year in trans_cfg, fetch tabs → all_txn_rows
  ├─ detect_transaction_columns(all_txn_rows) → date_col, source_col, amount_col, start_row
  ├─ normalize_transactions(...) → normalized_txns (then filter to last N months → normalized_txns)
  ├─ apply_categorization(normalized_txns) → tagged   [each row + category, subcategory, confidence, fixed_variable]
  ├─ aggregate_by_category_month(tagged) → by_cat_month   [(y,m): { labor, overhead, inventory, other }]
  ├─ aggregate_income_by_month(tagged) → income_by_month   [(y,m): sum(amount) where amount>0 and category==income]
  │
  ├─ expense_metrics(by_cat_month) → expense_metrics_by_ym
  ├─ margin_metrics(by_month_sales, by_cat_month, {}) → margin_by_ym
  ├─ labor_metrics(by_cat_month, by_month_sales) → labor_by_ym
  ├─ reconcile_monthly(by_month_sales, income_by_month, threshold) → reconciliation_rows
  ├─ run_anomalies(..., cfg) → anomalies, anomaly_count_by_ym
  ├─ health_rating(margin_by_ym, anomaly_count_by_ym, ...) → health_by_ym
  │
  └─ build_*_report(...) → dashboard_rows, anomaly_rows, expense_rows, margin_rows, recon_rows, labor_rows
       → write CSV or Sheets
```

**Data dependencies:**
- **GrowFlow sales:** `by_month_sales[ym].gross`, `by_month_sales[ym].cog` (from order items SoldAt, GrossPrice, COG).
- **Recorded income:** Only positive transactions with `category == "income"`. Positive amounts that match no income pattern still get category `income` (subcategory `other`) in categorization.py, so in practice recorded income = sum of all positive amounts in tagged.
- **Expenses:** From `by_cat_month`; category comes from first matching pattern (labor → inventory → overhead); else `other`.

---

## 3. Current category flow

| Step | Where | What happens |
|------|--------|--------------|
| Rule load | **categorization.py** `_build_rules()` | Load categories.yaml; build income_r (income patterns) and expense_r (labor + inventory + overhead), sorted by pattern length desc. |
| Per-row tag | **categorization.py** `categorize_transaction(amount, source_upper, income_r, expense_r)` | If amount > 0: match income patterns → category income; else default income/other. If amount < 0: match expense rules in order (labor, inventory, overhead) → category; else other/uncategorized. |
| Apply | **categorization.py** `apply_categorization(normalized_transactions)` | For each row, add category, subcategory, confidence, fixed_variable. |
| Income agg | **categorization.py** `aggregate_income_by_month(tagged)` | Sum row["amount"] for rows where amount > 0 and category == "income". |
| Expense agg | **categorization.py** `aggregate_by_category_month(tagged)` | For amount < 0, by (y,m) sum abs(amount) by category (labor, overhead, inventory, other). |

**Column used for matching:** `source_upper` (description/source column from Sheets, uppercased). Header detection in sources.py: SOURCE, DESCRIPTION, DESC map to source_col.

---

## 4. Where margin logic is calculated

| Metric | File:Function | Formula / logic |
|--------|--------------|------------------|
| Revenue | **metrics.py** `margin_metrics` | `revenue = by_month_sales[ym].gross` |
| COGS proxy | **metrics.py** `margin_metrics` | `cog_api = by_month_sales[ym].cog`; `inv_cost = by_cat_month[ym].inventory`; `cogs_proxy = cog_api if cog_api > 0 else inv_cost` (prefer API when both present). |
| OpEx | **metrics.py** `margin_metrics` | `op_ex = labor + overhead` (from by_cat_month; does not include inventory or other). |
| Gross margin % | **metrics.py** `margin_metrics` | `(revenue - cogs_proxy) / revenue * 100` if revenue > 0. |
| Operating margin % | **metrics.py** `margin_metrics` | `(revenue - cogs_proxy - op_ex) / revenue * 100` if revenue > 0. |
| Confidence | **metrics.py** `margin_metrics` | `"confirmed" if cog_api > 0 else "estimated"`. |

**Note:** `margin_metrics(by_month_sales, by_cat_month, package_by_month)` is called with `package_by_month = {}` from run_pipeline; third argument is unused in current implementation.

---

## 5. Where reconciliation logic is calculated

| Step | File:Function | Logic |
|------|----------------|-------|
| Inputs | **reconcile.py** `reconcile_monthly` | `by_month_sales` (GrowFlow gross by month), `income_by_month` (sum of positive amounts with category income, by month). |
| Difference | **reconcile.py** | `diff = abs(gross - income)` (not signed; note is set from gross vs income comparison). |
| Flag | **reconcile.py** | `flagged = diff >= threshold_dollars` (default 500 from config). |
| Note | **reconcile.py** | If gross > income: "Recorded income less than GrowFlow sales; possible timing (deposits next month), refunds, or fees." Else: "Recorded income greater than GrowFlow sales; possible other income or timing." |

**Recorded income source:** `aggregate_income_by_month(tagged)` = sum of amount for tagged rows where amount > 0 and category == "income". Because categorization assigns category "income" to all positive amounts (either by pattern or default), this is effectively **all positive transaction amounts** by month.

---

## 6. Where anomaly thresholds are applied

| Anomaly | File:Function | Config key | Logic |
|---------|--------------|------------|--------|
| Reconciliation | **anomaly.py** `run_anomalies` | reconciliation_diff_dollars (500) | Every reconciliation row with flagged=True → one anomaly; note from reconcile. |
| Expense MoM | **anomaly.py** | expense_mom_pct (25), expense_mom_dollars (500) | For labor, overhead, inventory, other: if (c_curr - c_prev)/c_prev*100 >= 25 or (c_curr - c_prev) >= 500 → anomaly. |
| Sales drop | **anomaly.py** | sales_drop_pct (15) | by_month_sales trend_pct <= -15 → anomaly. (Note: trend_pct comes from sales_metrics, which uses by_month_sales; run_pipeline does not pass sales_metrics_by_ym into run_anomalies; anomaly reads by_month_sales directly but trend_pct is in sales_metrics, not in by_month_sales. So currently sales_drop is broken — by_month_sales has gross, cog, lines, daily_gross but no trend_pct.) |
| Margin red | **anomaly.py** | margin_red_threshold_pct (0) | operating_margin_pct < 0 → anomaly. |
| Margin yellow | **anomaly.py** | margin_yellow_threshold_pct (5) | operating_margin_pct < 5 (and >= 0) → anomaly. |

**Bug:** Sales drop anomaly uses `data.get("trend_pct")` from `by_month_sales`, but `by_month_sales` is produced by `aggregate_sales_by_month` and does not contain `trend_pct`; `trend_pct` is in `sales_metrics_by_ym`. So sales_drop anomalies are never raised unless we pass sales_metrics into run_anomalies or add trend_pct to the structure used by run_anomalies.

---

## 7. Where monthly dashboard / report tables are built

| Report | File:Function | Columns / content |
|--------|----------------|-------------------|
| Monthly dashboard | **report.py** `build_monthly_dashboard` | Month, Sales, Total expense, Labor, Overhead, Inventory cost, Gross margin %, Operating margin %, Health, Anomalies. Sources: sales_metrics_by_ym, expense_metrics_by_ym, margin_by_ym, health_by_ym, anomaly_count_by_ym. |
| Anomaly report | **report.py** `build_anomaly_report` | Month, Metric, Value, Prior value, Threshold, Note. |
| Expense by category | **report.py** `build_expense_category_report` | Month, Category, Amount, % of expense. From by_cat_month. |
| Margin report | **report.py** `build_margin_report` | Month, Revenue, COGS proxy, OpEx, Gross margin %, Operating margin %, Confidence. |
| Reconciliation report | **report.py** `build_reconciliation_report` | Month, GrowFlow sales, Recorded income, Difference, Flagged, Note. |
| Labor report | **report.py** `build_labor_report` | Month, Labor total, Labor % of sales, Labor trend %. |

---

## 8. Known weak points

1. **“Other” expense bucket:** Large share of expenses (44–65% in first report) because many descriptions match no labor/inventory/overhead pattern. No subtyping of “other” (e.g. transfers, one-off vendors).
2. **Recorded income definition:** Reconciliation uses “all positive amounts” (via income category). No split of POS-like vs non-POS (transfers, contributions, loans). So reconciliation delta is hard to interpret.
3. **Sales drop anomaly:** Uses `by_month_sales` which has no `trend_pct`; trend is in `sales_metrics_by_ym`. Sales drop anomalies are currently never triggered.
4. **Margin confidence:** Label is “confirmed” whenever GrowFlow COG > 0. No separate “proxy-based” label when only transaction inventory is used; op_ex excludes “other” so operating margin may be overstated if “other” is operating expense.
5. **Health rating:** Only margin + anomaly count; no “data quality” status (e.g. materially distorted by reconciliation or missing categories).
6. **Dashboard:** No diagnosis, no “biggest trend” or “follow-up” fields; operator-useful narrative missing.
7. **Reconciliation output:** Single difference and note; no POS-comparable income, no breakdown of income subtypes, no explicit “likely cause” or confidence per month.
8. **Column letter for Sheets:** report.py uses `chr(64 + end_col)` for range; fails for > 26 columns (dashboard has 10; OK for now).

---

## 9. Recommended edit targets (by phase)

| Phase | Primary edit targets | Secondary |
|-------|----------------------|-----------|
| Phase 2 (other bucket) | config/categories.yaml; script or one-off to analyze “other” transactions → docs/OTHER_EXPENSE_AUDIT.md | lib/categorization.py only if new category type needed |
| Phase 3 (reconciliation) | lib/reconcile.py (POS-comparable income, subtypes); lib/normalization.py or categorization for income subtypes; lib/report.py build_reconciliation_report; docs/RECONCILIATION_DIAGNOSTIC.md | config/categories.yaml income subcategories; run_pipeline to pass new aggregates |
| Phase 4 (margin) | lib/metrics.py margin_metrics (confidence labels, op_ex vs total expense); lib/report.py build_margin_report; docs/MARGIN_METHOD_AUDIT.md; METRICS.md, CONFIDENCE_GAPS.md | — |
| Phase 5 (labor/overhead) | config/categories.yaml; docs/LABOR_OVERHEAD_AUDIT.md; METRICS.md | lib/metrics.py labor_metrics if new ratios needed |
| Phase 6 (dashboard) | lib/report.py build_monthly_dashboard; new health-status rule set; diagnosis / trend / follow-up fields; DESIGN.md, METRICS.md | lib/metrics.py health_rating if status set expands |
| Phase 7 (docs) | README.md, DESIGN.md, METRICS.md, CATEGORIZATION.md, CONFIDENCE_GAPS.md, FIRST_REPORT.md; CHANGELOG_PHASE2.md | — |

**Anomaly fix:** In run_anomalies, accept sales_metrics_by_ym (or compute trend from by_month_sales inside run_anomalies) so sales_drop uses actual trend_pct.
