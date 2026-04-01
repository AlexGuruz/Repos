# Other Expense Audit — Phase 2

**Goal:** Shrink the "other" expense bucket using reusable, defensible categorization rules.

---

## 1. Before (baseline)

**Source:** First pipeline run (6 months); `python -m company_bi.scripts.audit_other_expenses --months 6`.

| Metric | Value |
|--------|--------|
| Other expense total (6 months) | $538,026.71 |
| Other as % of total expense | 52.9% |
| Transactions in "other" | 934 |

**Monthly other (before):**

| Month | Other $ | % of expense (from FIRST_REPORT) |
|-------|---------|-----------------------------------|
| Sep 2025 | $123,680.94 | 65.09% |
| Oct 2025 | $82,451.99 | 48.85% |
| Nov 2025 | $83,599.49 | 53.18% |
| Dec 2025 | $67,001.35 | 46.33% |
| Jan 2026 | $64,485.61 | 44.65% |
| Feb 2026 | $91,130.17 | 59.65% |
| Mar 2026 | $25,677.16 | 43.36% |

**Top contributors to "other" (by total $):**

1. WITHDRAW — $219,950.50 (55 txns) — bank movements
2. REG 1 BANK — $57,596.00 (193 txns) — register-to-bank
3. REG 2 BANK — $56,700.00 (190 txns) — register-to-bank
4. TO BANK — $18,765.00 (13 txns) — transfers
5. SWIFT FINANCIAL — $17,000.00 (3 txns) — financing (left uncategorized)
6. PUFFIN PROPERTY PAYMENT — $13,783.77 (7 txns) — rent-style
7. SALES TAXES (AUG), (SEP), (DEC), etc. — tax payments
8. REG 3 BANK — $8,100.00 (28 txns)
9. SQUARE TIPS — $6,983.56 (14 txns) — labor (tips)
10. CITI CARD, CAPITAL ONE — card payments
11. AT&T — utilities
12. FARMERS INS — insurance
13. MJ TAXES — compliance
14. TESLA PAYMENT, AGRI CREDIT, AMAZON, etc. — various (left in other or not added as one-off)

---

## 2. Rules added (config/categories.yaml)

**Labor**

| Pattern | Subcategory | Rationale |
|---------|-------------|-----------|
| SQUARE TIPS | tips | Tips to staff; labor. |

**Overhead**

| Pattern | Subcategory | Fixed | Rationale |
|---------|-------------|-------|-----------|
| WITHDRAW | transfer | false | Cash withdrawals / bank movements. |
| TO BANK | transfer | false | Transfers to bank. |
| REG 1 BANK | transfer | false | Register 1 to bank. |
| REG 2 BANK | transfer | false | Register 2 to bank. |
| REG 3 BANK | transfer | false | Register 3 to bank. |
| PROPERTY PAYMENT | rent | true | Property/rent-style payments (e.g. Puffin). |
| ESTIMATED SALES TAX | compliance | false | Tax compliance. |
| SALES TAX | compliance | false | Sales tax payments. |
| MJ TAX | compliance | false | Cannabis/MJ tax. |
| TAXES ( | compliance | false | "SALES TAXES (AUG)" style. |
| GAS | utilities | false | Gas utility (design doc). |
| AT&T | utilities | false | Telecom/utilities. |
| FARMERS INS | insurance | true | Insurance. |
| CITI CARD | credit_card | false | Credit card payments. |
| CAPITAL ONE | credit_card | false | Credit card payments. |

**Not added (intentionally):**

- SWIFT FINANCIAL — financing; could add "SWIFT" → overhead/other_finance later if recurring.
- One-off payees (STONED PROJECTS, STUART & CLOVER, JEN PAY, OKC NOVELTY, TESLA PAYMENT, AGRI CREDIT) — not reusable; would overfit.
- AMAZON, C-STORE — could be inventory or supplies; description too generic; left for manual or future rule.

---

## 3. After (post–rule run)

**Source:** Pipeline re-run after updating `config/categories.yaml`.

| Metric | Before | After |
|--------|--------|--------|
| Other expense total (6 months) | $538,026.71 | ~$62,617 (sum of monthly other below) |
| Other as % of total expense | 52.9% | 2–14% by month (see table) |
| Transactions in "other" | 934 | *(re-run audit_other_expenses to get count)* |

**Monthly other (after):**

| Month | Other $ | % of expense |
|-------|---------|--------------|
| Sep 2025 | $27,066.73 | 14.24% |
| Oct 2025 | $8,020.03 | 4.75% |
| Nov 2025 | $3,335.46 | 2.12% |
| Dec 2025 | $11,444.46 | 7.91% |
| Jan 2026 | $12,991.94 | 9.00% |
| Feb 2026 | $5,787.82 | 3.79% |
| Mar 2026 | $1,971.04 | 3.33% |

**Note:** Much of the former "other" was reclassified to **overhead/transfer** (WITHDRAW, REG 1/2/3 BANK, TO BANK). Those are cash movements, not necessarily operating expense. Operating margin now includes them in OpEx (labor + overhead), so margin appears more negative. Consider excluding the **transfer** subcategory from OpEx for operating margin in a future refinement (see MARGIN_METHOD_AUDIT / Phase 4).

---

## 4. Items still unresolved

- **SWIFT FINANCIAL** — merchant financing; add pattern if confirmed recurring.
- **AMAZON, C-STORE, OKC NOVELTY** — supplies/inventory possible; need consistent description or GL code to avoid overfitting.
- **TESLA PAYMENT, AGRI CREDIT** — vehicle/loan; could add "TESLA", "CREDIT" later with care (CREDIT could match many).
- **Generic card payments** — only CITI CARD and CAPITAL ONE added; other card names as they appear and are reusable.

---

## 5. Items intentionally left uncategorized

- One-off vendors and legal/project names (e.g. STUART & CLOVER, STONED PROJECTS, JEN PAY) until a reusable pattern emerges.
- Small recurring round amounts ($300, $10, $20) without a consistent description — likely till/cash; could add "CASH" or "TILL" if descriptions become consistent.

---

## 6. How to regenerate

```bash
# From Growflow repo root
python -m company_bi.scripts.audit_other_expenses --months 6 --out company_bi/docs/other_expense_analysis.csv
```

Then re-run pipeline and compare `company_bi/output/expense_category.csv` and `dashboard.csv` for before/after other totals and %.
