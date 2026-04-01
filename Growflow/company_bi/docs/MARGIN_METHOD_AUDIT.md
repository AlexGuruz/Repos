# Margin Method Audit — Phase 4

**Goal:** Document exact margin formulas, data inputs, and what is confirmed vs proxy vs estimated.

---

## 1. Current inputs (metric engine)

| Input | Source | Used in |
|-------|--------|---------|
| **Revenue** | `by_month_sales[ym].gross` | GrowFlow findOrderItems, sum(GrossPrice)/100 per month | Confirmed |
| **COG (API)** | `by_month_sales[ym].cog` | GrowFlow order items, sum(COG)/100 per month | Confirmed if populated |
| **Inventory (txn)** | `by_cat_month[ym].inventory` | Transaction category "inventory" (e.g. ORDER, PURCHASE ORDER) | Confirmed for that slice |
| **Labor** | `by_cat_month[ym].labor` | Transaction category "labor" | Confirmed where rules match |
| **Overhead** | `by_cat_month[ym].overhead` | Transaction category "overhead" (rent, utilities, transfer, compliance, etc.) | Confirmed where rules match |

---

## 2. Exact formulas (lib/metrics.py margin_metrics)

```
revenue     = by_month_sales[ym].gross
cog_api     = by_month_sales[ym].cog
inv_cost    = by_cat_month[ym].inventory
labor       = by_cat_month[ym].labor
overhead    = by_cat_month[ym].overhead

cogs_proxy  = cog_api if cog_api > 0 else inv_cost
            (if both > 0, prefer cog_api)

op_ex       = labor + overhead   # does NOT include "other" or inventory

gross_margin_pct     = (revenue - cogs_proxy) / revenue * 100   if revenue > 0
operating_margin_pct = (revenue - cogs_proxy - op_ex) / revenue * 100   if revenue > 0

confidence  = "confirmed" if cog_api > 0 else "estimated"
```

---

## 3. What is confirmed vs proxy vs unresolved

| Metric | Confirmed when | Proxy / estimated when | Unresolved |
|--------|----------------|------------------------|------------|
| **Revenue** | Always (GrowFlow) | — | — |
| **COGS** | GrowFlow COG populated on order items | Transaction inventory category used when cog_api == 0 | If neither available, COGS = 0 (overstates gross margin) |
| **Gross margin %** | When COG from API > 0 | When COGS = transaction inventory only | — |
| **OpEx** | Labor and overhead where categorization rules match | "Other" expense not included in op_ex; if "other" is operating expense, operating margin is overstated | Transfer (bank movements) included in overhead; may overstate true operating expense |
| **Operating margin %** | When COGS and OpEx both confirmed | When COGS is proxy or when "other" or transfer distorts OpEx | — |

---

## 4. Known weaknesses

1. **OpEx excludes "other":** Operating expense = labor + overhead only. Unclassified "other" expense is real cash flow; if it is operating, operating margin is overstated.
2. **Overhead includes transfers:** After Phase 2, WITHDRAW, REG 1/2/3 BANK, TO BANK are overhead/transfer. These are cash movements, not necessarily operating expense. Including them in op_ex can make operating margin very negative.
3. **COGS = 0 if neither API nor inventory:** If GrowFlow COG is not populated and no transaction line matches "inventory", cogs_proxy = 0 → gross margin = 100%.
4. **No subcategory split in margin_metrics:** We cannot exclude "transfer" from op_ex without either passing tagged transactions and summing overhead where subcategory != "transfer", or adding overhead_by_subcategory to the pipeline.

---

## 5. Recommendations

- **Keep current formula** for auditability; document clearly in METRICS.md and CONFIDENCE_GAPS.md.
- **Label confidence in output:** Already "confirmed" vs "estimated" by COG source; consider adding "cogs_source": "api" | "transaction" in margin report for clarity.
- **Future refinement:** Optionally compute op_ex_excluding_transfer (e.g. sum overhead subcategories except transfer) and report both operating margin (current) and operating margin ex-transfer when subcategory data is available.

---

## 6. Margin report output (current)

Columns: Month, Revenue, COGS proxy, OpEx, Gross margin %, Operating margin %, Confidence.

Confidence = "confirmed" when GrowFlow COG > 0 for that month; else "estimated".
