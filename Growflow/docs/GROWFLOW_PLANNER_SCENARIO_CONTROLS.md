# Buy planner — scenario controls (no new schema assumptions)

These flags only change **how the same pulled order lines** are filtered, scored, and split. They do **not** add catalog fields or SKU truth. See `docs/GROWFLOW_PLANNER_DATA_MAPPING.md` for data limits.

**Tool:** `scripts/build_projection_by_category_brand.py` (repo root: `PYTHONPATH=. python scripts/...`).

---

## Pool size (`--pool`)

- **Effect:** Total capital to deploy (USD). **throughput** / **gross-share** use the full pool (largest-remainder cents). **buy-plan** may deploy **less** than the pool when every funded line hits its **cash-cycle** COG cap first.
- **Example scenarios:** `--pool 10000`, `--pool 18000`, `--pool 25000`.
- **Does not change:** API pull window unless you also change `--days`.

---

## Trailing sales window (`--days`)

- **Effect:** How far back **store-local** days are fetched and how **gross-share** / **throughput** layer2 math annualizes velocity.
- **Interaction:** `--velocity-days` is capped by `--days`.

---

## Buy-plan: cash cycle (`--cash-cycle-days`)

- **Default:** `14` — deployed COG per line should recover within **14 days** at **recent daily** unit burn (order-line count as units).
- **Effect:** Among top `--buy-plan-max-rows` qualifiers, allocator assigns `min(pool_remaining, max_cog_allowed)` per line in **score order**, where `max_cog_allowed = avg_units/day × cash_cycle_days × avg_cog/unit`. **No** second pass that exceeds that cap; leftover budget is **unallocated** (see markdown + `remaining_pool_unallocated_usd` in CSV).
- **Metrics:** `cash_recovery_days`, `cash_cycle_status` (SAFE / WARNING / CAPITAL RISK vs fixed **≤14 / 14–21 / >21** d), `max_cog_allowed_usd`, `capped_by_cash_cycle`, plus demand windows `units_needed_7d` / `14d` / `21d`, `days_of_cover`, `cover_status` (URGENT / THIN / HEALTHY / HEAVY). Legacy columns `coverage_weeks` / `days_of_inventory` remain as sell-through ratios (not on-hand inventory).

---

## Buy-plan: recent velocity window (`--velocity-days`)

- **Effect:** Store-local days used for **recent** units/gross/COG per cell, scoring, min-units/week filter, and sell-through weeks.
- **Example scenarios:** `42` (~6 wks), `49` (default, ~7 wks), `56` (~8 wks).
- **Does not change:** Full-window gross tables in the markdown report (still `--days`).

---

## Buy-plan: activity filter (`--min-units-per-week`)

- **Effect:** Hard floor on average units/week in the velocity window; rows below get **$0** pool.
- **Stricter:** Higher value → fewer qualifying lines (e.g. `5`).
- **Looser:** Lower value → more lines can qualify (e.g. `1` or `2`).

---

## Buy-plan: concentration (`--buy-plan-max-rows`)

- **Effect:** Maximum **brand × category** lines that receive any pool dollars; rest get **$0**.
- **Smaller:** More concentrated deployment.
- **Larger:** Dollars spread across more lines (still score-ranked).

---

## Buy-plan: minimum line size (`--min-allocated-usd`)

- **Effect:** **buy-plan:** **ignored** — merging small lines would violate the per-row **cash-cycle** COG cap. **throughput** / **gross-share:** after split, allocations below this **USD** are reabsorbed and redistributed (0 = disable).

---

## Throughput mode only (`--pool-top-n`)

- **Effect:** Full pool on top **N** cells by implied **monthly COG throughput** (full `--days` window), proportional split among picks.
- **Ignored** for **buy-plan** (use `--buy-plan-max-rows` instead).
- **gross-share:** use `--pool-top-n 0` per script help (legacy).

---

## Brand exclusions (`--exclude-brands`)

- **Effect:** Comma-separated labels excluded from the pool denominator and allocations (default includes `(no brand)`, **Puffin Pure**, **710 Empire**, consignment vendors **Doc Furgsen** / **Doc Ferguson**, **Deadhead Farms**, **Arctic Extracts**, **Rooted Right Farms**).
- **Empty string:** Include all brands.

---

## Allocation mode (`--allocation-mode`)

| Mode | Behavior (same data) |
|------|----------------------|
| `buy-plan` | Recent velocity + score; top `--buy-plan-max-rows` funded lines. |
| `throughput` | Top `--pool-top-n` cells by implied monthly COG throughput (full window). |
| `gross-share` | Proportional to trailing gross across **all** cells. |

---

## Internal comparison (`--compare-modes`)

- **Effect:** After the main report, writes **`<stem>_allocation_compare.md`** (or `--compare-modes-out`) with **buy-plan**, **throughput**, and **gross-share** side by side: funded row counts, weighted recovery (different definitions per mode), total projected revenue/GP, top 10 rows per mode.
- **Use:** Directional evaluation only — **not** proof of optimality (see file header disclaimer).

---

## Output metadata (every layer2 CSV row)

Repeated columns (downstream: Sheets, BI): `allocation_mode`, `velocity_window_days_run`, `cash_cycle_days_run`, `remaining_pool_unallocated_usd` (buy-plan unused budget), `grouping_level` (`brand_category`), `schema_validated` (`false` until SDL/playground), `schema_source` (`fallback_docs_or_code`), `unit_model_note` (one order line = one unit until validated). Per-row buy-plan fields include `avg_units_per_day`, `days_of_inventory`, `coverage_weeks`, `units_needed_7d` / `14d` / `21d`, `days_of_cover`, `cover_status`, `cash_recovery_days`, `max_cog_allowed_usd`, `capped_by_cash_cycle`, `cash_cycle_status`.

Markdown **Summary → Planning metadata** mirrors the same ideas.

---

## Related docs

- `docs/GROWFLOW_API.md` — doc index  
- `docs/GROWFLOW_PLANNER_DATA_MAPPING.md` — planner ↔ GraphQL mapping  
- `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md` — schema / fallback map  
