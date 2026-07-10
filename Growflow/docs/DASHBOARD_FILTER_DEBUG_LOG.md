# Dashboard filter / formula debug log

Auditable record for projection Google Sheet dashboard fixes. Each iteration: hypothesis → evidence → change → deploy → live verify.

---

## Iteration 2026-04-03 — XMATCH, TRIM, M1 validation, Q1

**Hypothesis**

1. `MATCH(TRUE,INDEX(LOWER(h)="brand",1),0)` is unreliable in some Google Sheets builds → `#ERROR!` at `dashboard_data!A2500` and cascade through `$A$2500#`, helpers, AB3 (O1 list), and filter validation errors.
2. Untrimmed `M1`/`O1` (e.g. `"None "`) fails `mode="None"` but does not match `LOWER(mode)="none"`, producing an all-zero `pass` vector → `FILTER` returns nothing → blank dashboard.
3. `M1` data validation `strict: True` surfaces red errors when the cell drifts from the four allowed literals.

**Evidence (pre-fix)**

- Local CSV headers are lowercase `brand` / `category` (see `data/projection_by_category_brand_layer2_recovery.csv` row 1).
- Prior deploy: chart patcher reported `0 of 6` charts matched (titles), separate from formula pipeline.

**Code changes**

| File | Change |
|------|--------|
| `lib/projection_dashboard_sheet_dynamic.py` | Brand/category column: `XMATCH("x",LOWER(...),0)` on `h` and `raw_layer2!$1:$1`. `filtered_layer2`: `mode,val` from `TRIM(M1/O1)`; treat `LOWER(mode)="none"` as no filter. `dynamic_o1_list_formula`: `TRIM(M1)` for mode branches. |
| `scripts/build_projection_dashboard_google_sheet.py` | `M1` validation `strict: False`. `Q1` formula uses `TRIM` / `LOWER(TRIM(M1))` for display. |

**Deploy commands**

```text
PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py
PYTHONPATH=. python scripts/verify_projection_dashboard_sheet.py
```

If verification fails on **embedded chart count**, run:

```text
PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py --full-refresh --confirm-layout-reset
```

**Live verification result**

_(Filled in after runs; see shell output below.)_

| Check | Pass/Fail |
|-------|-----------|
| A2500 formula + spill row 2501 | |
| AC3 numeric (None mode) | |
| Filter tests 1–4 (None / Brand / Category / Brand+Category) | |
| `dashboard` embedded charts > 0 | |

**Next action if failed**

- If A2500/AC3 fail: inspect live `dashboard_data!A2500` error text; consider `XMATCH` availability or header typos on `raw_layer2`.
- If filters fail only: inspect `AB3`, `AD3#`, `AF3#`; confirm O1 value matches pair format `Brand | Category` (space-pipe-space).
- If charts only: one-time `--full-refresh --confirm-layout-reset`.

---

## Command log (append only)

```text
PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py
PYTHONPATH=. python scripts/verify_projection_dashboard_sheet.py
# exit 0: pool None AC3=7308.69, all filter tests pass, 6 embedded charts
```

---

## Iteration 2026-04-03 — Google Sheets compatibility (no A1#, no DROP/TAKE, MAKEARRAY rows≥1, spill reservation)

**Hypothesis**

1. Excel-style spill refs `A2500#` / `AD3#` produce **Formula parse error** in the live spreadsheet (confirmed via scratch cells `=ROWS(A2500#)`).
2. `DROP` and `TAKE` are **Unknown function** in this Sheets tenant (confirmed: AC3 showed `Unknown function: 'DROP'`).
3. `MAKEARRAY(0, …)` is invalid (`parameter 1 value is 0`); AB3 failed on `MAKEARRAY(0,1,…)` for None mode.
4. `LET` received a **double comma** after dropping `F` binding (`LET(_fl_n,..., ,d,…)`), yielding wrong argument count.
5. Dynamic-array spills were **blocked** by the next section title (e.g. GP_TOP) placed inside the ALLOC_TOP spill rectangle → `#REF!` overwrite A21.

**Evidence**

- Live `UNFORMATTED_VALUE` on `dashboard_data!AC3`: parse error on `#`; then `#NAME?` for `DROP`; then `#N/A` wrong `LET` arity; after fixes, numeric KPI.
- Live `AB3`: `#VALUE!` on `MAKEARRAY(0,1,…)`.
- Live `A18`: `#REF!` “would overwrite data in A21” until grid reserved spill rows.

**Code changes**

| File | Change |
|------|--------|
| `lib/projection_dashboard_sheet_dynamic.py` | Replace `$A$2500#` with `_fl_n,COUNTA(A2500:A3299)` + body `OFFSET(A2501,0,0,_fl_n-1,40)`. Replace `AD3#` / etc. with `COUNTA`+`OFFSET` column blocks. Remove trailing comma from rowcount binding; fix `LET({fb},…` composition. Replace `DROP`/`TAKE` with `CHOOSEROWS(…,SEQUENCE(k))`. Replace `MAKEARRAY(0,…)` with `MAKEARRAY(1,…)` via `_make_empty_row_matrix`. KPI empties use `IF(_fl_n<=1,…)`; table `n` uses `MAX(0,_fl_n-1)` where needed. `append_formula_section`: `skip_rows(max(0,data_rows-1))` after each spill formula so later titles do not sit inside the spill range. |
| `docs/DASHBOARD_FILTER_DEBUG_LOG.md` | This iteration + command log. |

**Live verification**

- `scripts/verify_projection_dashboard_sheet.py` exit **0** after deploy: None/Brand/Category/Brand+Category filter tests, AC3 numeric, ALLOC_TOP, 6 charts.

**Caveats**

- Chart source patcher still reports **0 of 6** matched by title; embedded charts exist. If chart ranges look stale in UI, run once: `PYTHONPATH=. python scripts/build_projection_dashboard_google_sheet.py --full-refresh --confirm-layout-reset`.
- Some ALLOC label cells in col A may show `#N/A` in Values API while col B has brand (sparse spill read); verify script uses col B for ALLOC check.
