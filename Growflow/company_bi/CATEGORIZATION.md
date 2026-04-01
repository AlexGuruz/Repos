# Categorization and Tagging Logic

## Goal

Classify each **financial transaction** (Transactions + Bank sheets) into:

- **income** (positive amount; subtype for reconciliation)
- **labor** (payroll, wages, payroll tax)
- **overhead** (rent, utilities, subscriptions, compliance, fees, etc.)
- **inventory** (purchase orders, inventory-related payments)
- **fixed** / **variable** (when derivable)
- **other** (unmatched)

Rules are **pattern → category** (and optional subcategory). First match wins; longer patterns tried first to avoid false positives.

---

## Income (positive amounts)

Used for reconciliation with GrowFlow sales.

| Pattern (substring, case-insensitive) | Category | Subcategory | Notes |
|--------------------------------------|----------|-------------|-------|
| REG 1 DEPOSIT | income | register_deposit | Till 1 |
| REG 2 DEPOSIT | income | register_deposit | Till 2 |
| REG 3 DEPOSIT | income | register_deposit | Till 3 |
| SQUARE | income | square | Card sales |
| CASH DEPOSIT | income | cash_deposit | |
| DEPOSIT | income | deposit | Generic (may catch some non-sales) |

---

## Labor

| Pattern | Category | Subcategory |
|---------|----------|-------------|
| PAYROLL | labor | payroll |
| PAY ROLL | labor | payroll |
| WAGE | labor | wages |
| SALARY | labor | salary |
| 941 | labor | payroll_tax |
| TAX DEPOSIT | labor | payroll_tax |
| SQUARE PAYROLL | labor | payroll |
| ADP | labor | payroll |
| PAYCHEX | labor | payroll |
| DIRECT DEPOSIT | labor | payroll |

Confidence: **high** for explicit payroll/wage/salary; **medium** for tax/941; **low** for generic DEPOSIT (not used as labor unless above).

---

## Inventory-related (COGS proxy)

| Pattern | Category | Subcategory |
|---------|----------|-------------|
| ORDER | inventory | orders |
| PURCHASE ORDER | inventory | orders |
| INVENTORY | inventory | inventory |
| SUPPLIER | inventory | supplier |
| VENDOR | inventory | vendor |

Note: " ORDER" (with space) avoids matching "ORDER" in other words. Orders spend = negative amounts with " ORDER" in description (per existing logic).

---

## Overhead (subcategories)

| Pattern | Category | Subcategory |
|---------|----------|-------------|
| RENT | overhead | rent |
| LEASE | overhead | rent |
| UTILITIES | overhead | utilities |
| OG&E | overhead | utilities |
| ELECTRIC | overhead | utilities |
| GAS | overhead | utilities |
| WATER | overhead | utilities |
| SUBSCRIPTION | overhead | subscriptions |
| INSURANCE | overhead | insurance |
| LICENSE | overhead | compliance |
| OMMA | overhead | compliance |
| COMPLIANCE | overhead | compliance |
| BANK FEE | overhead | bank_fees |
| SERVICE CHARGE | overhead | bank_fees |
| ATM | overhead | bank_fees |
| SQUARE (when negative) | overhead | payment_processing |
| TRANSFER | overhead | transfer |

Fixed vs variable (optional tag):

- **Fixed:** rent, lease, subscription, insurance, compliance (license).
- **Variable:** utilities, bank fees, some payment processing.

---

## Order of application

1. **Amount sign:** If amount > 0 → income branch; if amount < 0 → expense branch.
2. **Income:** Match REG DEPOSIT, SQUARE, CASH DEPOSIT, DEPOSIT.
3. **Expense:** Match in order (longest patterns first within each category):
   - labor
   - inventory ( ORDER, PURCHASE ORDER, etc.)
   - overhead (rent, utilities, subscriptions, …)
4. **Unmatched expense** → category = other, subcategory = uncategorized.

---

## Implementation

- Rules live in `config/categories.yaml` as list of `{ pattern, category, subcategory, fixed_or_variable }`.
- Code in `lib/categorization.py` compiles rules, sorts by pattern length descending, and applies to each transaction row (Date, Company, Source, Amount).
- Output: same row + `category`, `subcategory`, `confidence` (high/medium/low), optional `fixed_variable`.
