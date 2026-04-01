# Company BI — Business Summary (Sales, Inventory, Expenses, Payroll)

This doc summarizes what the BI pipeline is measuring and what the current output tells us about the business. Data sources: **GrowFlow** (POS/inventory), **Google Sheets** (Transactions/Bank, PAYROLL), optional **SQLite** for cached order items.

**Local AI feed:** The ai-lab command-center (Guru) loads this file as evidence when you ask about business, sales, expenses, payroll, or inventory. Ask things like *"business summary"*, *"sales and expenses overview"*, *"how's the business"* to get answers grounded in this data. Refresh: re-run the pipeline and update this doc (or regenerate it from the latest CSVs); optional env `COMPANY_BI_SUMMARY_PATH` can point to another snapshot path.

---

## What the system tracks

| Area | Source | What we get |
|------|--------|-------------|
| **Sales** | GrowFlow API (order items) | Gross sales by month; COGS from API; gross margin % |
| **Inventory** | Same order items | COGS, inventory cost; turnover estimate; SKU-level revenue and slow-selling flags |
| **Expenses** | Sheets (Transactions / Bank tabs) | Categorized spend: labor, overhead (rent, compliance, utilities, transfers, etc.), inventory, other |
| **Payroll** | Sheets (PAYROLL tab) or DB | Labor total by month; labor % of sales; merged with expense categorization |

---

## Latest snapshot (Feb–Mar 2026)

### Sales (GrowFlow)
- **Feb 2026:** ~$39.0k sales; **Mar 2026:** ~$39.1k (flat MoM).
- **Gross margin %:** ~57–58% (revenue − COGS from API).
- **COGS:** ~$16.5–16.7k/month from GrowFlow order items.

### Expenses (from bank/transactions)
- **Total expense:** Feb ~$177.7k → Mar ~$76.9k (large drop; likely timing or one‑offs in Feb).
- **Overhead** is the largest bucket: ~63–68% of expense (rent, compliance, transfers, utilities, insurance, subscriptions, etc.).
- **Labor (expense side):** ~$14–26k/month from categorized transactions (tips, payroll, wages, etc.).
- **Labor (PAYROLL tab):** Feb ~$50.6k, Mar ~$27.0k (confirmed from Kylo PAYROLL sheet); labor % of sales 69–130% in this window.

### Recurring overhead (from categorized recurring bills)
- **Transfers** dominate (till/bank moves): Feb ~$65k, Mar ~$23k.
- **Compliance:** Feb ~$22k, Mar ~$4k.
- **Rent:** ~$10.4k both months.
- **Utilities, insurance, subscriptions, fuel, credit card** make up the rest.

### Inventory (from order items)
- **Turnover estimate:** Feb 2.27, Mar 5.07 (improvement in Mar).
- **Inventory/sales ratio:** Feb 0.44, Mar 0.20.
- **SKU view:** Many SKUs with 1–2 months active; slow-selling flag on single‑month SKUs is expected. Top revenue SKUs and line counts are in **BI Inventory Analysis**.

### Reconciliation (GrowFlow vs recorded income)
- **Recorded income (POS-comparable)** is **higher** than GrowFlow sales in both months (Feb ~$98k vs $39k; Mar ~$45k vs $39k).
- **Flagged:** Difference above threshold ($500). Likely causes: other income in POS/bank (non-GrowFlow), timing (deposits in different months), or duplicate recording. **Follow-up:** Reconcile POS vs bank deposits and confirm what “POS-comparable income” includes (e.g. only dispensary POS or multiple streams).

### Anomalies
- **Reconciliation:** Large positive difference (recorded > GrowFlow) both months.
- **Margin:** Operating margin deeply negative (−340% Feb, −115% Mar) because **total expense is much higher than revenue** in this window (expense includes one-off or timing-heavy items; labor from PAYROLL is high relative to sales).

---

## Does the system “make sense” of the business?

**Yes, with caveats:**

1. **Sales & COGS** — Clear from GrowFlow: monthly gross, COGS, gross margin %.
2. **Inventory** — Turnover and SKU-level revenue/slow-selling support ordering and assortment decisions.
3. **Expenses** — Categories (labor, overhead, inventory, other) and recurring breakdown (rent, compliance, transfers, utilities, etc.) give a clear expense structure.
4. **Payroll** — PAYROLL sheet is the labor source when configured; labor is merged into dashboard and labor report.

**What needs interpretation:**

- **Reconciliation:** “Recorded income” vs “GrowFlow sales” will only align if the bank/POS data represents the same revenue stream as GrowFlow and in the same period. If there are multiple locations, other revenue, or timing differences, the flag is expected; the system is correctly highlighting a gap to explain.
- **Operating margin** is (revenue − total expense) / revenue. When expense is very high (e.g. Feb) or labor is a large share of sales, operating margin will be negative; the pipeline is reflecting that, not mis-measuring.
- **Labor:** Distinction between “labor from transactions” (categorized GREG PAY, JEN PAY, payroll, etc.) and “labor from PAYROLL tab” is by design; the dashboard uses the configured source (e.g. Kylo PAYROLL) when available.

---

## Recommended next steps

1. **Reconciliation:** Document what goes into “POS-comparable income” (which sheets/tabs, which deposits) and whether multiple revenue streams or locations are included. Adjust logic or labels so “GrowFlow sales” is compared to the right benchmark.
2. **Operating margin:** Use the dashboard for trend (e.g. expense and labor % of sales over time). If one-off spikes are known (e.g. big transfer month), consider tagging or excluding for “underlying” margin view.
3. **Inventory:** Use **BI Inventory Analysis** for slow-moving SKUs and to cross-check COGS and ordering.
4. **Refreshes:** Run `ingest_growflow_to_db` periodically and `run_pipeline --from-db` so BI stays current; optionally run with Sheets to update the live spreadsheet.

---

*Generated from BI pipeline output (dashboard, margin, reconciliation, expense category, labor, inventory analysis, anomalies).*
