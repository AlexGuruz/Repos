# Inventory vs Sales Analysis and Monitoring

Scripts use Growflow order items (sales) and packages (inventory) to distinguish **supply-driven** vs **demand/outside-factor** drops in sales. **All scripts default to ALL product categories** unless you pass `--category "substring"`.

## Data limitations

Growflow gives **current** package quantities (`CurrentQty`) and `createdAt`, but not a full time-series of inventory. So any “was it supply?” call is **heuristic**, not exact.

- **Sales:** We have actual monthly/daily gross and line counts from `findOrderItems` (SoldAt).
- **Supply proxy:** Per month we use **units created** (sum of `OriginalQty` for packages with `createdAt` in that month) and **current** inventory (which SKUs have `CurrentQty > 0` today).

## Scripts

### 1. `all_categories_inventory_and_daily_rebuild.py` (all categories + daily inventory reconstruction)

**Purpose:** Full company view: all categories, monthly classification, and **backward reconstruction of daily inventory** by SKU.

**Data:**
- **Order items:** Last 6 months, no category filter.
- **Packages:** Fetched in **6-month chunks** (e.g. 4 chunks = 2 years) so **older packages with stock** are included; each chunk avoids API timeouts (520). Baseline = sum of current `CurrentQty` per SKU across all chunks (deduped by package id).
- **Sales quantity:** 1 unit per order line (API has no line quantity).

**Reconstruction:** Start from today’s inventory by SKU. For each past day (newest to oldest):  
`inventory_end[day][sku]` = current[sku]; then `current[sku] += sales_that_day[sku]`.  
So “inventory at end of day” is derived by adding that day’s sales back onto the next day’s starting inventory.

**Sheets written:**
1. **Inventory vs Sales (6m) All** – Month, Gross ($), Sales lines, Units created, Classification, Note (all categories).
2. **Daily Inventory Reconstructed** – Date, Total inv (end of day), Total sales (units), Gross ($), then one column per category (sales that day).
3. **Daily Inventory by SKU** – (optional, omit with `--no-daily-by-sku`) Date, SKU, Inventory end of day, Sales that day (last ~3 months).

**Usage:**
```bash
python all_categories_inventory_and_daily_rebuild.py
python all_categories_inventory_and_daily_rebuild.py --no-daily-by-sku
```

---

### 2. `inventory_vs_sales_last_6_months.py` (one-off, optional category filter)

**Purpose:** Same monthly classification as above, with optional `--category` filter (default: all categories).

**Logic:**
- Same 6-month window; optional category filter (default: all).
- **Sales:** Gross and order line count per month from `findOrderItems`.
- **Supply:** From `findPackages` (created in same window), per month: sum `OriginalQty`; and today: how many distinct SKUs still have `CurrentQty > 0`.
- **Heuristic:**
  - **Likely supply-constrained:** Sales down vs prior month **and** units created down or zero **and** many SKUs have no current inventory.
  - **Likely demand/outside factor:** Sales down vs prior month **and** units created similar or higher **and** inventory still present.

**Output:**
- Table printed to console.
- New sheet tab **"Inventory vs Sales (6m)"** in the same spreadsheet as “Last 6 Months Gross” (unless `--no-sheet`).

**Usage:**
```bash
python inventory_vs_sales_last_6_months.py
python inventory_vs_sales_last_6_months.py --category "prepackaged" --no-sheet
```

---

### 3. `inventory_sales_monitor.py` (ongoing monitor)

**Purpose:** Run daily or weekly to flag **demand** vs **supply** signals over a rolling window (default 90 days).

**Logic:**
- Fetches order items and packages for the last N days.
- Computes daily gross and a simplified **inventory status** (total current units and SKUs with stock from packages in that window).
- **Demand signal:** Rolling (e.g. 14-day) sales drop ≥ threshold (e.g. 25%) while inventory is **healthy** → likely demand or outside factor.
- **Supply signal:** Sales drop with **low** inventory, or inventory at/below a low-units threshold → possible stockout or supply bottleneck.

**Output:**
- **CSV** (default: `inventory_sales_alerts_YYYYMMDD.csv`) with columns: date, category, sales_trend, inventory_status, reason_code, note.
- Optional sheet tab **"Inventory vs Sales Alerts"** with `--write-sheet`.

**Usage:**
```bash
python inventory_sales_monitor.py
python inventory_sales_monitor.py --days 60 --sales-drop-pct 25 --output alerts.csv
python inventory_sales_monitor.py --write-sheet
```

**Scheduling:** Run via Task Scheduler (Windows) or cron (e.g. daily). Optionally wire the CSV or sheet into email/Slack for alerts.

## Thresholds (tunable in code)

- **inventory_vs_sales_last_6_months.py:** `SALES_DROP_PCT`, `UNITS_DROP_PCT`, `SKU_STOCKOUT_THRESHOLD`.
- **inventory_sales_monitor.py:** `DEFAULT_ROLLING_DAYS`, `SALES_DROP_PCT_DEFAULT`, `ROLLING_WINDOW_DAYS`, `LOW_INVENTORY_UNITS`.

## Credentials

Same as other Growflow/Sheets scripts: `--growflow-credentials`, `--sheets-service-account`, or env `GROWFLOW_CREDENTIALS_PATH` and `GOOGLE_APPLICATION_CREDENTIALS` / `STASHBOX_SERVICE_ACCOUNT`.
