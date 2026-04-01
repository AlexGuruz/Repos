# Reconciliation Diagnostic — Phase 3

**Goal:** Investigate sales vs recorded-income mismatch and provide a POS-comparable income view with likely cause and confidence.

---

## 1. Reconciliation path (current)

| Step | Source | Output |
|------|--------|--------|
| GrowFlow sales | `lib/sources.py` → `fetch_growflow_order_items`; `normalization.py` → `aggregate_sales_by_month` | `by_month_sales[(y,m)].gross` = sum(GrossPrice)/100 per month |
| Recorded income | Sheets (Transactions + Bank tabs); `normalization.py` → `categorization.py` → `aggregate_income_by_month` | Sum of all **positive** amounts with category `income` (all positive amounts are tagged income) |
| POS-comparable income | Same tagged transactions; `aggregate_income_by_subcategory_by_month`; sum only subcategories `register_deposit`, `square`, `cash_deposit` | Excludes generic `deposit` and any other income subtypes |
| Difference | `reconcile.py` | `difference` = \|GrowFlow − recorded_income\|; `difference_pos` = GrowFlow − POS_comparable (signed) |
| Flag | `reconcile.py` | Flagged if \|GrowFlow − recorded_income\| ≥ $500 **or** \|GrowFlow − POS_comparable\| ≥ $500 |

---

## 2. Income subtypes (from categorization)

Positive amounts are tagged **income** with subcategory from first matching pattern:

| Pattern | Subcategory | POS-comparable? |
|---------|-------------|-----------------|
| REG 1/2/3 DEPOSIT | register_deposit | Yes |
| SQUARE | square | Yes |
| CASH DEPOSIT | cash_deposit | Yes |
| DEPOSIT | deposit | No (generic; can include non-POS) |

**POS-comparable income** = register_deposit + square + cash_deposit only. Generic "deposit" and any unmatched positive (income/other) are in **recorded income** but not in **POS-comparable**.

---

## 3. Likely causes (assigned in reconcile.py)

- **POS-comparable aligns with GrowFlow** (|\Delta| < $500): likely cause = "POS-comparable aligns with GrowFlow."; confidence = high.
- **GrowFlow > POS-comparable** (deposits less than sales): timing lag (deposits in next month), or some POS income in "deposit" / other; confidence = medium.
- **POS-comparable > GrowFlow**: duplicate recording or other income in POS buckets; confidence = medium.

---

## 4. Timing and data caveats

- **Daily batching:** GrowFlow uses SoldAt (transaction time); bank deposits may post next day or later.
- **Month-end:** Deposits near month-end can appear in the following month in Sheets/Bank.
- **Multiple registers:** REG 1/2/3 DEPOSIT and SQUARE are all included in POS-comparable; if a register is not in GrowFlow, or vice versa, delta can be structural.
- **Refunds/fees:** GrowFlow gross is pre-refund; bank may show net; Square/bank fees reduce net deposits.

---

## 5. Required table (per month)

Produced by pipeline in **company_bi/output/reconciliation.csv**:

| Month | GrowFlow sales | Recorded income | POS-comparable income | Delta vs GrowFlow | Likely cause | Confidence |
|-------|----------------|-----------------|------------------------|-------------------|--------------|------------|
| Sep 2025 | 66,976.58 | 187,780.78 | 137,355.00 | −70,378.42 | POS deposits exceed GrowFlow; possible duplicate recording or other income in POS buckets. | medium |
| Oct 2025 | 106,219.85 | 173,933.23 | 125,401.17 | −19,181.32 | Same | medium |
| Nov 2025 | 78,701.83 | 151,777.80 | 100,152.43 | −21,450.60 | Same | medium |
| Dec 2025 | 83,724.84 | 148,790.31 | 109,845.48 | −26,120.64 | Same | medium |
| Jan 2026 | 84,451.97 | 148,954.61 | 106,342.58 | −21,890.61 | Same | medium |
| Feb 2026 | 75,551.52 | 147,480.03 | 98,165.24 | −22,613.72 | Same | medium |
| Mar 2026 | 37,179.67 | 60,493.67 | 43,467.49 | −6,287.82 | Same | medium |

**Interpretation:** POS-comparable income (reg + square + cash_deposit) exceeds GrowFlow every month. Likely causes: multiple registers/locations in bank not all in this GrowFlow view, or timing (prior-month sales deposited in current month). All months remain flagged (≥ $500).

Any unexplained discrepancy ≥ $500 remains flagged in the report and in anomalies.

---

## 6. Formula reference

- **Recorded income:** Sum(amount) for all rows where amount > 0 and category == "income" (all positives are income).
- **POS-comparable income:** Sum(amount) for rows where amount > 0, category == "income", and subcategory ∈ {register_deposit, square, cash_deposit}.
- **Delta vs GrowFlow:** GrowFlow_sales − POS_comparable_income (signed).
- **Flagged:** Y if \|GrowFlow − recorded_income\| ≥ 500 or \|GrowFlow − POS_comparable_income\| ≥ 500.
