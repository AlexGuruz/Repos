# Metric Definitions and Formulas

## Confidence labels

- **Confirmed:** Sourced directly from API or transaction data with no inference.
- **Estimated:** Derived from proxies, heuristics, or partial data; documented.
- **Not available:** Data or field missing.

---

## 1. Sales view

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Daily sales | Sum(GrossPrice)/100 for order items where SoldAt date = d | GrowFlow findOrderItems | Confirmed |
| Weekly sales | Sum(daily sales) for days in week | GrowFlow | Confirmed |
| Monthly sales | Sum(GrossPrice)/100 for order items where SoldAt in month | GrowFlow | Confirmed |
| Average ticket | Monthly sales / count(distinct orders) in month | GrowFlow (orders or order items grouped) | Confirmed if orders available |
| Trend direction | (current_month_sales - prior_month_sales) / prior_month_sales | GrowFlow | Confirmed |
| Volatility | std(daily_sales) / mean(daily_sales) over period | GrowFlow | Confirmed |
| Sales spike | Day d where daily_sales(d) > mean + 2*std | GrowFlow | Confirmed |
| Sales dip | Day d where daily_sales(d) < mean - 2*std | GrowFlow | Confirmed |

---

## 2. Expense view

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Monthly expenses total | Sum(\|amount\|) where amount < 0, by month | Transactions/Bank | Confirmed |
| Expense by category | Sum(\|amount\|) where amount < 0 and category = X | Transactions + categorization | Confirmed for matched rules |
| Fixed vs variable | Sum by tag fixed/variable (from category config) | Transactions | Estimated |
| Unusual cost spike | Month M where expense_category(M) - expense_category(M-1) >= threshold $ or % | Transactions | Confirmed (value); cause estimated |

---

## 3. Overhead view

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Recurring operating costs | Sum(expense) where category in overhead subcategories | Transactions | Confirmed where rules match |
| Non-inventory operating | Overhead + labor (exclude inventory) | Transactions | Confirmed |
| Labor | **Primary:** Sum(expense) from DB `core.transactions_unified` where amount_cents &lt; 0 and description matches labor patterns (petty-cash payroll). **Fallback:** Transaction categorization from Sheets. | DB petty-cash payroll (primary); Sheets (fallback) | Confirmed when from DB; inferred when fallback |
| Rent, utilities, etc. | Sum(expense) where subcategory = rent | Transactions | Confirmed/estimated by rule |

---

## 4. Inventory view

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Units created (month) | Sum(OriginalQty) for packages with createdAt in month | GrowFlow findPackages | Confirmed |
| Current stock (units) | Sum(CurrentQty) over packages | GrowFlow | Confirmed |
| Units sold (month) | Count(order items) or sum(qty) in month | GrowFlow | Confirmed |
| Inventory-related cost | Sum(expense) where category = inventory | Transactions | Confirmed |
| Stock depletion pattern | Daily/weekly units sold from order items | GrowFlow | Confirmed |
| Slow-moving | SKUs where (current_stock / avg_monthly_sales) > threshold | GrowFlow | Estimated |
| Inventory-to-sales ratio | Units_created / units_sold or inventory_cost / sales | GrowFlow + Transactions | Confirmed |
| Shrinkage / adjustment | Flag when cost or movement inconsistent with sales | GrowFlow + logic | Estimated |

---

## 5. Margin view

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Gross revenue | Sum(GrossPrice)/100 by month | GrowFlow | Confirmed |
| COGS (GrowFlow) | Sum(COG)/100 per order item in month | GrowFlow | Confirmed if COG populated; else Not available |
| COGS proxy (transactions) | Sum(expense) where category = inventory (e.g. orders) | Transactions | Confirmed for that slice |
| COGS source | "api" \| "transaction" \| "none" | margin_metrics | Confirmed (reported in margin.csv) |
| Operating expenses | Labor + overhead (excludes "other"; includes transfer) | Transactions | Confirmed where categorized |
| Gross margin | (Revenue - COGS proxy) / Revenue | Derived | Confirmed if COG from API; estimated if proxy |
| Operating margin | (Revenue - COGS proxy - OpEx) / Revenue | Derived | Same; note OpEx includes transfer subcategory |
| What is confirmed | Revenue, COGS when from API, expense buckets | — | — |
| What is estimated | COGS when from transaction inventory only; margin when proxy | — | — |

See **docs/MARGIN_METHOD_AUDIT.md** for exact formulas and weaknesses.

---

## 6. Labor view

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Labor total (month) | Sum(expense) where category = labor | Transactions | Confirmed/estimated by rules |
| Labor % of sales | Labor / monthly_sales * 100 | Derived | Confirmed if labor tagged |
| Labor trend | MoM change in labor $ and % | Derived | Same |
| Labor pressure | Flag if labor % > threshold (e.g. 30%) or rising | Derived | Confirmed |

---

## 7. Monthly business health

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Sales | As in Sales view | GrowFlow | Confirmed |
| Inventory-related cost | As in Inventory view | Transactions | Confirmed |
| Labor | As in Labor view | Transactions | Confirmed/estimated |
| Overhead | As in Overhead view | Transactions | Confirmed |
| Total expenses | Sum all expense categories | Transactions | Confirmed |
| Estimated gross margin | As in Margin view | Derived | Estimated |
| Estimated operating margin | As in Margin view | Derived | Estimated |
| Major anomalies | From anomaly engine (reconciliation, spikes, margin) | Derived | Confirmed (flag) |
| Health rating | green / yellow / red from margin + anomalies | Derived | Estimated (threshold-based) |
| **Status** | healthy \| watch closely \| unstable \| materially distorted by data issues | metrics.health_status_detailed | Estimated |
| **Diagnosis** | One-liner: op margin + anomaly count/types | Same | Estimated |
| **Biggest positive** | e.g. Sales +X% MoM or Op margin when >5% | Same | Estimated |
| **Biggest negative** | e.g. Op margin or reconciliation delta | Same | Estimated |
| **Follow-up** | Reconcile POS vs bank, or Review anomalies, or — | Same | Estimated |

---

## 8. Trend metrics (Phase 3)

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Sales trend % | (current_month_sales - prior_month_sales) / prior_month_sales * 100 | sales_metrics.trend_pct | Confirmed |
| Expense trend % | (current_total_expense - prior) / prior * 100 | expense_metrics by month | Confirmed |
| Labor trend % | (current_labor - prior_labor) / prior_labor * 100 | labor_metrics | Confirmed |
| Margin trend % | operating_margin_pct(current) - operating_margin_pct(prior) (percentage points) | margin_metrics | Confirmed |
| Negative sales trend | True when sales_trend_pct ≤ -15% | calculate_trend_metrics | Confirmed |
| Labor pressure | True when labor % of sales > 40% | Same | Confirmed |
| Margin instability | True when operating margin < 0 | Same | Confirmed |

---

## 9. Inventory intelligence (Phase 3)

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| inventory_turnover_estimate | revenue / inventory_cost (txn category inventory) | by_month_sales, by_cat_month | Estimated |
| inventory_sales_ratio | inventory_cost / revenue | Same | Estimated |
| slow_inventory_indicator | True when inventory_sales_ratio > 0.5 | Same | Estimated |
| SKU total_gross | Sum(gross) per SKU from order items | normalized_items | Confirmed |
| slow_selling (SKU) | total_gross < 500 or months_active ≤ 1 | sku_revenue_summary | Estimated |

---

## 10. Risk score (Phase 3)

| Metric | Formula | Source | Confidence |
|--------|---------|--------|------------|
| Risk score | 0-100 from margin, sales trend, expense trend, labor pressure, anomaly count, reconciliation flag | calculate_risk_score | Estimated |
| Risk category | healthy (0-30) \| watch closely (31-60) \| unstable (61-80) \| operational risk (81-100) | Same | Estimated |

Scoring: op margin < -10% (+40), < 0% (+25), < 5% (+10); sales trend ≤ -15% (+20); expense trend > 25% (+10); labor pressure (+15); per anomaly +5 (max 25); reconciliation flagged (+10). Capped at 100.

---

## Anomaly thresholds (configurable)

| Rule | Default | Description |
|------|---------|-------------|
| Reconciliation difference | >= $500 | \|GrowFlow_sales - recorded_income\| |
| Expense category MoM | >= 25% or >= $500 | Increase in any category |
| Labor/overhead MoM | >= 25% or >= $500 | Increase |
| Sales material drop | >= 15% MoM | Revenue decline |
| Margin low | < 0% or < 5% | Gross or operating |
| Volatility spike | e.g. 2x prior month | Daily sales std/mean |
