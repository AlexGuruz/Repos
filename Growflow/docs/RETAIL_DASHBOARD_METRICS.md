# Retail Dashboard Metrics

Implementation: `lib/retail_dashboard/metrics.py`  
Build: `scripts/build_retail_dashboard.py`  
Validation: `validate_sums()` — budtender, brand, and daily net must match store total (±$1).

## Global filters

| Parameter | Values | Source |
|-----------|--------|--------|
| Period | `last_7_days`, `last_30_days`, `last_90_days`, custom | `sold_date_local` in fact store |
| Store | store `objectId` or all | `order_lines.store_object_id` |
| Channel | `all`, `in_store`, `online` | `order_lines.channel` (PreOrderType proxy) |
| Compare prior | on/off | Same-length window immediately before period |

## Store-level KPIs (meta)

| Metric | Formula |
|--------|---------|
| `store_net_sales` | Σ `net_price_cents` (returns negative) |
| `effective_discount_pct` | 100 × Σ `discount_cents` / Σ menu basis |
| `order_count` | distinct `order_object_id` |

Menu basis per line: `original_price_cents` or fallback `collected_otd_cents`.

## Widget 1 — Budtender Sales

Per budtender (`budtender_name` from `User.FullName`):

| Column | Formula |
|--------|---------|
| `net_sales` | Σ line net (USD) |
| `order_count` | distinct orders |
| `aov` | net / order_count |
| `effective_discount_pct` | 100 × budtender discount / budtender menu |
| `pct_orders_discounted` | orders with line discount > 0 / order_count |
| `pct_net_sales` | budtender net / store net |
| `flags` | Coaching: `high_discount_vs_store`, `low_aov_vs_store`, `low_aov_and_high_discount` |

Coaching thresholds (config): +15pp discount vs store; AOV −20% vs store.

## Widget 2 — Discounts Over Time

Daily series for each date in period:

| Column | Formula |
|--------|---------|
| `net_sales` | Σ line net for date |
| `effective_discount_pct` | 100 × daily discount / daily menu |
| `pct_orders_discounted` | discounted orders / daily orders |

## Widget 3 — Budtender by Category

Per `(category_canonical, budtender)`:

| Column | Formula |
|--------|---------|
| `gross_sales` | Σ gross (returns negative) |
| `net_sales` | Σ net |
| `item_count` | line count |

Category: `category_canonical` from brand/category normalize.

## Widget 4 — Brand Summary

Per `brand_canonical`:

| Column | Formula |
|--------|---------|
| `net_sales` | Σ line net |
| `returns_pct` | 100 × return abs net / (abs net + returns) |
| `effective_discount_pct` | 100 × brand discount / brand menu |
| `native_margin_pct` | 100 × (net − Σ COG) / net |
| `landed_margin_pct` | 100 × (net − Σ landed_cost) / net |
| `cog_vs_landed_delta_pct` | landed_margin − native_margin |
| `profit_velocity_rank` | rank by net sales desc |

## Period compare KPIs

When `--compare`: `net_sales`, `effective_discount_pct`, `order_count`, `pct_orders_discounted` vs prior window with `delta_abs` and `delta_pct`.

## Alerts

| Code | Trigger |
|------|---------|
| `discount_spike` | Effective discount > prior + 3pp |
| `budtender_outliers` | Any budtender with coaching flags |

## Sum validation gate

```
sum(budtender.net_sales) == store_net_sales
sum(brand.net_sales) == store_net_sales
sum(daily.net_sales) == store_net_sales
```

Tolerance: ±$1.00 (rounding).

## Reconciliation gate (release)

Before relying on Operations metrics in production, run the reconciliation script against a trusted native GrowFlow export.

**Script:** `scripts/reconcile_retail_dashboard.py`  
**Library:** `lib/retail_dashboard/reconcile.py`  
**Default report:** `data/retail_reconciliation_latest.json`  
**Config:** `config/retail_dashboard.yaml` → `reconciliation` block

### What is compared

| Check | Type | Blocks release |
|-------|------|----------------|
| `sum_gate_budtender_net_sales` | internal | yes |
| `sum_gate_brand_net_sales` | internal | yes |
| `sum_gate_daily_net_sales` | internal | yes |
| `ref_store_net_sales` | vs reference | yes |
| `ref_budtender_net_sales:*` | vs reference | yes |
| `ref_daily_net_sales:*` | vs reference | yes |
| `ref_brand_net_sales:*` | vs reference | yes |
| `ref_category_budtender_net_sales:*` | vs reference | no (warning) |

Sum gates always run (even without a reference file). Reference comparisons run when `--reference-csv` or `--reference-json` is supplied.

### Tolerance rules

A check **passes** when either:

- `|actual − expected| ≤ money_tolerance_abs` (default **$1.00**), or
- `|delta_pct| ≤ pct_tolerance` (default **0.005** = 0.5%) when expected ≠ 0

Override via CLI (`--money-tolerance`, `--pct-tolerance`) or `config/retail_dashboard.yaml`.

### Reference CSV format

Long-format CSV with required columns: `section`, `key`, `metric`, `value`.

```csv
section,key,metric,value
period,,start,2026-06-01
period,,end,2026-06-02
store,total,net_sales,12345.67
budtender,Alice,net_sales,5000.00
daily,2026-06-01,net_sales,4000.00
brand,Acme,net_sales,2500.00
category_budtender,Flower|Alice,net_sales,1200.00
```

Export from native GrowFlow dashboard or a manual report using the same period, store, and channel filters as the dashboard build.

### Reference JSON format

Mirror dashboard widget shapes (partial OK):

```json
{
  "period": {"start": "2026-06-01", "end": "2026-06-30"},
  "store": {"net_sales": 12345.67},
  "budtender_sales": [{"budtender": "Alice", "net_sales": 5000.0}],
  "discounts_over_time": [{"date": "2026-06-01", "net_sales": 4000.0}],
  "brand_summary": [{"canonical_brand": "Acme", "net_sales": 2500.0}]
}
```

### CLI examples

```powershell
cd e:\Repos\Growflow
$env:PYTHONPATH="."

# Full reconcile vs CSV export
python scripts/reconcile_retail_dashboard.py `
  --dashboard-json data/retail_dashboard_latest.json `
  --reference-csv data/reference/growflow_retail_dashboard_export.csv `
  --out data/retail_reconciliation_latest.json `
  --money-tolerance 1.00 `
  --pct-tolerance 0.005

# Sum gates only (no reference)
python scripts/reconcile_retail_dashboard.py --latest

# Deterministic fixture test path
python scripts/reconcile_retail_dashboard.py `
  --dashboard-json tests/fixtures/retail_dashboard/dashboard_golden.json `
  --reference-csv tests/fixtures/retail_dashboard/reference_golden.csv
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | pass (or warning-only unless `--strict`) |
| 1 | fail — blocking check exceeded tolerance |
| 2 | invalid/missing inputs or CSV contract error |

### Report contract

Written JSON includes `generated_at`, `status` (`pass` \| `fail` \| `warning`), `period`, `reference`, `tolerance`, `summary`, and per-check `checks[]` with `expected`, `actual`, `delta_abs`, `delta_pct`.

### What failures mean

- **Sum gate fail:** computed dashboard widgets do not add up to store total — likely aggregation bug or bad fact ingest; do not release.
- **Reference fail:** promoted metrics differ from trusted export beyond tolerance — investigate filters, timezone, returns handling, or brand/category normalization.
- **Warning:** optional reference section missing (e.g. no budtender rows in CSV) or non-blocking category/budtender mismatch.

No GraphQL is called during reconciliation; inputs are pre-built dashboard JSON and offline reference files only.

**Operator SOP:** [RETAIL_RECONCILIATION_SOP.md](RETAIL_RECONCILIATION_SOP.md)  
**Live runbook:** [RETAIL_COMMAND_CENTER_RUNBOOK.md](RETAIL_COMMAND_CENTER_RUNBOOK.md)
