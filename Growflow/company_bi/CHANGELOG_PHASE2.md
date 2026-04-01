# Changelog — Phase 2 (Refinement, Validation, System Hardening)

Concise record of rules added, formulas changed, reconciliation and dashboard changes, and unresolved issues.

---

## Rules added (config/categories.yaml)

**Labor**
- `SQUARE TIPS` → tips (from other-expense audit).

**Overhead**
- `WITHDRAW`, `TO BANK`, `REG 1 BANK`, `REG 2 BANK`, `REG 3 BANK` → transfer.
- `PROPERTY PAYMENT` → rent (fixed).
- `ESTIMATED SALES TAX`, `SALES TAX`, `MJ TAX`, `TAXES (` → compliance.
- `GAS`, `AT&T` → utilities.
- `FARMERS INS` → insurance.
- `CITI CARD`, `CAPITAL ONE` → credit_card.

---

## Formulas / logic changed

- **Anomaly (sales_drop):** `by_month_sales` had no `trend_pct`; now trend is computed inside `run_anomalies` from prior-month vs current-month gross so sales-drop anomalies fire correctly.
- **Reconciliation:** Added POS-comparable income (register_deposit + square + cash_deposit only). New outputs: `pos_comparable_income`, `difference_pos` (GrowFlow − POS_comparable), `likely_cause`, `confidence`. Flagging: still any unexplained difference ≥ $500; also flag when |GrowFlow − POS_comparable| ≥ $500.
- **Margin:** Added `cogs_source` to margin metrics and report ("api" | "transaction" | "none"). No change to gross/operating margin formulas.
- **Dashboard:** Added columns Status, Diagnosis, Biggest positive, Biggest negative, Follow-up. New status set: healthy | watch closely | unstable | materially distorted by data issues (from `health_status_detailed` in metrics.py).

---

## New / updated modules

- **lib/categorization.py:** `aggregate_income_by_subcategory_by_month()` for reconciliation.
- **lib/reconcile.py:** `POS_COMPARABLE_SUBCATEGORIES`, `_pos_comparable_from_subcategories()`, extended `reconcile_monthly(..., income_by_subcategory_by_month)` with pos_comparable_income, difference_pos, likely_cause, confidence.
- **lib/report.py:** `build_monthly_dashboard(..., anomalies, reconciliation_rows)`; `build_reconciliation_report` extended with POS-comparable, Delta vs GrowFlow, Likely cause, Confidence; `build_margin_report` with COGS source.
- **lib/metrics.py:** `health_status_detailed()` for status/diagnosis/positive/negative/follow-up; margin_metrics now sets `cogs_source`.
- **lib/anomaly.py:** Sales-drop uses computed MoM trend from by_month_sales.
- **scripts/audit_other_expenses.py:** New script for other-expense audit (top descriptions, monthly other, recurring amounts).

---

## New docs

- **docs/PHASE2_SYSTEM_AUDIT.md** — Module map, metric/category flow, weak points, edit targets.
- **docs/OTHER_EXPENSE_AUDIT.md** — Before/after other %, rules added, unresolved/intentionally uncategorized.
- **docs/RECONCILIATION_DIAGNOSTIC.md** — Reconciliation path, income subtypes, POS-comparable, required table, timing caveats.
- **docs/MARGIN_METHOD_AUDIT.md** — Exact formulas, inputs, confirmed vs proxy, weaknesses.
- **docs/LABOR_OVERHEAD_AUDIT.md** — Labor/overhead rules, recurring items, ratios, confidence.

---

## Assumptions

- POS-comparable income = register_deposit + square + cash_deposit only (generic "deposit" excluded).
- Any discrepancy ≥ $500 remains flagged (reconciliation and anomalies).
- Health status "materially distorted" when reconciliation flagged and anomaly count ≥ 3 for that month.
- Transfer (WITHDRAW, REG x BANK, TO BANK) remains in overhead for now; optional exclusion from OpEx for operating margin is documented for future work.

---

## Unresolved issues

- **Reconciliation:** POS-comparable still exceeds GrowFlow every month in current data; likely multiple registers/locations or timing. No change to source systems.
- **Margin:** OpEx includes transfer; operating margin can look very negative. Excluding transfer from OpEx would require overhead-by-subcategory in the pipeline.
- **Other bucket:** SWIFT FINANCIAL, AMAZON, C-STORE, one-off payees left uncategorized; add rules when reusable patterns are confirmed.
- **Sheets rate limit:** Pipeline can hit 429 (Read requests per minute); reduce tabs or add backoff if needed.

---

## Rerun

From Growflow repo root:

```bash
python -m company_bi.run_pipeline --no-sheets --months 6
```

Output: `company_bi/output/*.csv` (dashboard, anomalies, expense_category, margin, reconciliation, labor). Dashboard now has 15 columns including Status, Diagnosis, Biggest positive/negative, Follow-up.
