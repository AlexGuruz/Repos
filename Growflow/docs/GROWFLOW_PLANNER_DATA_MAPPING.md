# GrowFlow buy planner — data mapping

This document ties **planner inputs** to **GraphQL sources**. Exact field names must match your org’s live schema.

**Source-of-truth workflow:** See `docs/GROWFLOW_API.md` (index). Schema map: `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md` (regenerate with `scripts/introspect_growflow_schema.py --write-docs` when introspection works). What to request from GrowFlow: `docs/GROWFLOW_NEXT_DATA_REQUEST.md`. Validate priority `find*` operations with `scripts/run_growflow_discovery_queries.py` once playground or SDL confirms shapes. **Scenario flags** (pool, velocity window, compare modes): `docs/GROWFLOW_PLANNER_SCENARIO_CONTROLS.md`.

**Production Retail is not a schema source** when `__schema` / `__type` are blocked — do not extend the planner from guessed catalog fields.

---

## 1. Planner need → query → fields (target state)

| Need | Query | Intended fields / objects | Status in repo |
|------|--------|---------------------------|----------------|
| **Sales velocity** | `findOrderItems` | `SoldAt`, `GrossPrice`, `COG`, `Product.objectId` / `SKU`, `ProductCategory`, `Product.Brand`, weights (`NetWeight` / `UnitWeight`) | **Implemented** — `lib/growflow_queries.py` |
| **Cost basis (inventory)** | `findPackages` | `Cost`, `OriginalQty` (opening line qty), `CurrentQty` (**live on-hand**), `createdAt`, `SKU`, `Product` — see `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md` *Package line quantities* | **Implemented** |
| **Landed cost from receipts (SKU)** | `findTransfers` → SQLite `product_landed_cost_current` | Latest `Packages.Cost` / `OriginalQty` per `Product.objectId`; export CSV for BI / Notes | **Implemented** — `lib/product_landed_cost_sqlite.py`, `scripts/build_transfer_receipts_db.py`; **not** auto-merged into layer2 / Sheets until the planner joins it (Notes tab documents presence) |
| **Product / SKU identity** | `findProducts` | Stable id, `name`, `SKU`, active flag, links to brand + category | **Not wired** — confirm in playground, then join to order lines |
| **Brand identity** | `findBrands` | Brand id, display name | **Not wired** — today brand comes from `Product.Brand` on order items |
| **Category identity** | `findProductCategories` | Category id, name, hierarchy if present | **Not wired** — today category inferred from `ProductCategory.Name` + product title rules |
| **Store / location scope** | `findStores` | Store id, name; filter order items / packages by store if API exposes it | **Not wired** — risk if multi-store data mixes in one org |
| **Transfer noise** | `findTransfers` | Received/sent dates, package refs, qty, from/to store | **Not wired** — use to separate internal moves from demand. **Example SKU ID on packages:** Cartel infused 7×1.2g multipack — `docs/GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md`. |
| **Tender / paid revenue** | `findTransactions` | Tender type, amount, link to order if available | **Not wired** — useful for reconciliation, less for unit buy math |
| **Line quantity** | `findOrderItems` | If schema adds line `Qty` / similar, use it; else **1 line = 1 unit** remains a limitation | **Assumption today** |
| **Cash cycle** | (business rule) | Default **14-day** COG recovery cap: per line, `max_cog ≤ avg_units/day × cash_cycle_days × avg_cog/unit`; allocator walks score order with **no** over-cap remainder pass — **pool may stay unallocated**; no on-hand stock in API model | **Implemented** — `--cash-cycle-days` |

---

## 2. Current buy planner (what actually runs)

| Input | Source today | Notes |
|-------|----------------|-------|
| Recent units / $ velocity | `findOrderItems` chunked by `SoldAt` | Recent window = `--velocity-days` (default 7 weeks) |
| COG / retail per “unit” | Same lines: `COG`, `GrossPrice` ÷ line count | Coarse at brand×category grain |
| Allocation grain | Brand × product bucket (Edibles, Cartridges, …) | From `order_line_format_bucket` logic, not `findProductCategories` |
| Pool split | Score on recent velocity + weekly COG $ + rev/$ COG | Top `--buy-plan-max-rows` lines only |

---

## 3. Recommended upgrade path (after schema discovery)

1. **Join catalog**  
   Pull `findProducts` (and `findBrands` / `findProductCategories` if product nodes only expose IDs). Map `OrderItem.Product.objectId` → canonical SKU, brand id, category id.

2. **SKU-level or product-level scoring**  
   Aggregate `findOrderItems` by `Product.objectId` (or `SKU` if stable), then optionally roll up to brand/category for dashboards.

3. **Store filter**  
   If `findOrderItems` supports a store filter, align with `findStores` list; exclude or segment multi-store.

4. **Transfers**  
   Build a time series of transfer-affected SKUs/locations; down-weight or exclude periods where net movement dominated apparent “sales.”

5. **Quantity**  
   If the schema exposes real line quantity, replace `1 line = 1 unit` everywhere in velocity and buy units.

---

## 4. SKU-level planning — can we do it now?

**Not safely without discovery:** the repo already has **product objectIds** on order items, but **does not** fetch `findProducts` to validate active flags, alternate SKUs, or packs. Recommendation:

- **Yes, move toward SKU/product aggregation** using **`Product.objectId`** from existing `findOrderItems` as soon as you confirm ids are stable in the playground.
- **Full “retail-accurate” SKU planning** (active/inactive, duplicate SKUs, true qty) requires **`findProducts`** (and often package linkage) per live schema — **run introspection or playground exploration first** (see schema map doc).

---

## 5. Related files

| File | Role |
|------|------|
| `lib/growflow_queries.py` | Shipped `findOrderItems` / `findPackages` queries |
| `lib/growflow_graphql.py` | Auth + POST to Retail GraphQL |
| `scripts/introspect_growflow_schema.py` | Introspection + regenerates `GROWFLOW_RETAIL_SCHEMA_MAP.md` |
| `scripts/build_projection_by_category_brand.py` | Buy-plan pipeline (velocity + allocation) |
| `scripts/build_transfer_receipts_db.py` | SQLite: raw transfer package lines + **`product_landed_cost_current`** (latest `Packages.Cost` / qty per `Product.objectId`) |
| `lib/product_landed_cost_sqlite.py` | Materialize **`product_landed_cost_current`** from **`transfer_receipt_packages`** |
| `company_bi/DESIGN.md` | Broader BI source map including `findOrders` / `findTransfers` (not all implemented) |
