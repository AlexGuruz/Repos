# Labor and Overhead Audit — Phase 5

**Goal:** Improve reliability of labor and overhead reporting; document top recurring items, rule changes, and confidence.

---

## 1. Labor

**Labor source (corrected):** Payroll is not missing from the system. Payroll is paid in cash and captured through the **employee petty cash sheet**; those **petty cash CSV reports are already ingested into the database** (e.g. `core.transactions_unified` in Kylo). Company BI uses **DB-ingested petty-cash payroll as the primary labor source**; budget sheet and transaction inference are fallbacks only. See **docs/LABOR_SOURCE_TRACE.md** and **lib/labor_source.py**.

### 1.1 Current rules (config/categories.yaml)

| Pattern | Subcategory | Notes |
|---------|-------------|-------|
| SQUARE TIPS | tips | Added Phase 2 (from other-expense audit). |
| PAYROLL, PAY ROLL, SQUARE PAYROLL | payroll | |
| 941, TAX DEPOSIT | payroll_tax | |
| WAGE, SALARY | wages, salary | |
| ADP, PAYCHEX, DIRECT DEPOSIT | payroll | |

### 1.2 Top recurring labor (from categorization)

Labor total is the sum of expenses matching the above patterns. No subcategory breakdown is written to CSV currently; from FIRST_REPORT and dashboard:

- **Labor % of sales:** 34–48% in the 6-month window (high; industry context matters).
- **Labor trend:** Volatile MoM (e.g. Oct +49%, Nov −30%, Mar −46%).

Recurring labor vendors matched by pattern: payroll (ADP, Paychex, Square Payroll), 941/tax deposit, SQUARE TIPS.

### 1.3 Possible missed / false positives

- **Missed:** Payroll or wage payments whose description does not match any pattern (e.g. unique payee name) → fall to "other". Add vendor-specific patterns as they appear and are reusable.
- **False positives:** "DIRECT DEPOSIT" can match non-payroll deposits; we use it for labor. If bank uses "DIRECT DEPOSIT" for customer refunds, that would be misclassified. Review sample of DIRECT DEPOSIT lines if needed.

### 1.4 Ratios (already in output)

- **Labor total by month:** dashboard.csv, labor.csv.
- **Labor % of sales:** labor.csv (Labor % of sales).
- **Labor trend %:** labor.csv (MoM change).
- **Labor pressure:** Anomaly engine flags expense_mom_labor when increase ≥ 25% or $500.

---

## 2. Overhead

**Source:** Overhead (and thus recurring bills and utilities) is **inferred from the cleaned Transactions and Bank tab data** in the master JGD Google Sheets that Project-Kylo sorts. Company BI reads those tabs, matches each row’s description to `config/categories.yaml`, and assigns a bill type (rent, utilities, insurance, etc.). No separate “bills” sheet is required—the cleaned transaction descriptions and amounts are the source. A **Recurring Bills** report (by subcategory per month) is produced by the pipeline (`recurring_bills.csv` / BI Recurring Bills tab).

### 2.1 Current rules (by subcategory)

| Subcategory | Patterns (examples) | Fixed/variable |
|-------------|---------------------|----------------|
| transfer | TRANSFER, WITHDRAW, TO BANK, REG 1/2/3 BANK | variable |
| rent | RENT, LEASE, PROPERTY PAYMENT | fixed |
| utilities | UTILITIES, OG&E, ELECTRIC, WATER, GAS, AT&T | mixed |
| subscriptions | SUBSCRIPTION | fixed |
| insurance | INSURANCE, FARMERS INS | fixed |
| compliance | OMMA, LICENSE, COMPLIANCE, SALES TAX, MJ TAX, TAXES (, ESTIMATED SALES TAX | mixed |
| bank_fees | BANK FEE, SERVICE CHARGE, ATM | variable |
| credit_card | CITI CARD, CAPITAL ONE | variable |

### 2.2 Top recurring overhead (from data)

- **Transfer** (WITHDRAW, REG x BANK, TO BANK) dominates dollar volume after Phase 2 reclassification.
- Rent (RENT, PROPERTY PAYMENT), utilities (AT&T, OG&E, etc.), compliance (taxes), insurance (FARMERS INS), credit card payments (CITI, CAPITAL ONE) are present and categorized.

### 2.3 Ratios

- **Overhead by month:** dashboard.csv (Overhead column).
- **Overhead % of sales:** Not currently a column; can compute as Overhead / Sales from dashboard. Optional: add to labor report or dashboard (Overhead % of sales).
- **Total operating expense % of sales:** (Labor + Overhead) / Sales from margin/report.

### 2.4 Category rule changes (Phase 2)

See OTHER_EXPENSE_AUDIT.md: added WITHDRAW, TO BANK, REG 1/2/3 BANK (transfer); PROPERTY PAYMENT (rent); SALES TAX, MJ TAX, TAXES (, ESTIMATED SALES TAX (compliance); GAS, AT&T (utilities); FARMERS INS (insurance); CITI CARD, CAPITAL ONE (credit_card).

---

## 3. Confidence notes

- **Labor:** High when a labor pattern matches (PAYROLL, WAGE, SQUARE TIPS, etc.). No inference for unmatched; labor $0 for those.
- **Overhead:** High when an overhead pattern matches. Transfer is correctly categorized but may be excluded from “operating” P&L in future (see MARGIN_METHOD_AUDIT).
- **Overhead % of sales:** Add to reporting if desired (formula: overhead / monthly sales * 100).

---

## 4. Optional: Overhead % of sales in report

To add Overhead % of sales to the dashboard or labor report: compute in metrics (e.g. in expense_metrics or a new helper) and add a column to build_monthly_dashboard or build_labor_report. Not required for Phase 5 deliverable; document here for future use.
