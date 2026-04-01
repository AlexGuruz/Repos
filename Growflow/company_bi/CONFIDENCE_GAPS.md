# Confidence Gaps and Missing Data

## What is confirmed (from current data)

- **Sales (GrowFlow):** Daily and monthly gross revenue, line count, trend %, volatility. Source: `findOrderItems` (SoldAt, GrossPrice).
- **Expenses (Sheets):** Monthly total expense, and by category **where a categorization rule matches** (labor, overhead, inventory, other). Source: Transactions + Bank tabs; amount sign = income vs expense.
- **Recorded income:** Sum of positive amounts from Transactions/Bank, optionally filtered by income-type patterns (REG DEPOSIT, SQUARE, etc.) for reconciliation.
- **Reconciliation difference:** |GrowFlow sales − recorded income|; flag when ≥ $500.
- **Anomaly flags:** Based on thresholds (expense MoM, sales drop, margin band); the *existence* of a flag is confirmed; the *cause* may need manual review.
- **Labor total (when tagged):** Sum of expenses matching labor rules (PAYROLL, WAGE, etc.). Confidence **high** when rule matches.
- **Inventory-related expense (when tagged):** Sum of expenses matching " ORDER" and similar; matches existing “orders spend” logic.
- **Overhead (when tagged):** Sum of expenses matching rent, utilities, subscriptions, compliance, fees, etc.

## What is estimated or inferred

- **COGS (cost of goods sold):** GrowFlow order items have a `COG` field. If populated, COGS is **confirmed** (cogs_source = api). Else we use **inventory-related transaction expense** as proxy → **estimated** (cogs_source = transaction or none). See docs/MARGIN_METHOD_AUDIT.md.
- **Gross margin:** (Revenue − COGS proxy) / Revenue. **Confirmed** if COG from API; **estimated** if proxy.
- **Operating margin:** (Revenue − COGS − OpEx) / Revenue. OpEx = labor + overhead (includes transfer subcategory). **Estimated** when COGS is proxy; also **overhead includes bank transfers** (WITHDRAW, REG x BANK, TO BANK), which can overstate operating expense for P&L.
- **Labor (when not tagged):** If no labor pattern matches, labor is $0 in the report; we do not guess. To improve: add payroll vendor names or descriptions to `config/categories.yaml` under labor.
- **Fixed vs variable expense:** We tag from category rules (e.g. rent = fixed, utilities = variable). **Estimated**; no GL coding in the feed.
- **Health rating:** Based on operating margin and anomaly count; thresholds are configurable. **Estimated** (judgment-based).

## What is not available from current sources

- **Per-SKU or per-order COGS** unless GrowFlow returns COG per order item and it is populated.
- **Exact labor breakdown** (e.g. by employee or department) unless you add such data to a sheet or feed.
- **Inventory valuation over time** (we have units and package Cost at fetch time, not historical valuation).
- **Tender-level reconciliation** (e.g. cash vs card) unless we use Orders with nested Transactions and map to bank; not yet in pipeline.
- **Refunds and voids** explicitly separated from gross sales in the high-level report (they are in GrowFlow net/gross; bank may show net deposits).

## Minimum additions to strengthen the system

1. **GrowFlow COG:** Ensure COG is populated on order items (or document that it is not). If available, gross margin becomes **confirmed**.
2. **Labor rules:** Add every payroll-related description pattern (vendor names, “PAYROLL”, “941”, etc.) to `config/categories.yaml` under labor so labor total is as complete as possible.
3. **Bank feed consistency:** Use consistent description/source text so categorization rules stay stable month over month.
4. **Optional: GL or category column** in the transaction sheet (e.g. “Category” or “Type”) so we can tag from a code instead of description only; would reduce reliance on pattern matching.
5. **Optional: Tender breakdown** from GrowFlow (Orders with Transactions) and a mapping to bank deposit types to reconcile cash vs card and explain timing differences.
