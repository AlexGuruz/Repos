# Growflow API Schema & Response Correlation Matrix

This matrix is the metric contract source of truth for trust gating:

`business metric -> approved query template -> raw JSON -> validation report -> trusted output`

References used in this file:

- `lib/growflow_graphql.py`
- `lib/growflow_queries.py`
- `lib/transfer_receipt_export.py`
- `scripts/_sales_today.py`
- `scripts/build_projection_by_category_brand.py`
- `scripts/build_transfer_receipts_db.py`
- `scripts/export_transfer_receipt_units.py`
- `scripts/rank_mj_brands_profit_velocity_sheet.py`
- `scripts/run_growflow_discovery_queries.py`
- `docs/GROWFLOW_API.md`
- `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md`
- `docs/GROWFLOW_SCHEMA_CONFIDENCE_PLAN.md`
- `scripts/README.md`

## Master Matrix

| Metric ID | Business Question Answered | Canonical Script | Query Template ID | GraphQL Operation / Function | Variables Required | Expected JSON Root Path | Required API Fields | Optional API Fields | Parsed/Normalized Output Fields | Validation Checks Needed | Downstream Consumer | Current Confidence | Known Risks / Schema Drift Notes | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sales_today` | What sold today and for how much? | `scripts/_sales_today.py` | `order_items_sales_today_v1` | `OrderItems` via `ORDER_ITEMS_QUERY` | `first`, `where.SoldAt` range | `data.findOrderItems` | `objectId`, `SoldAt`, `GrossPrice`, `NetPrice` | `COG`, `Product.Brand.Name`, `ProductCategory.Name` | `order_item_id`, `sold_at`, `gross_price_cents`, `net_price_cents` + optional `canonical_*` | root, fields, types, drift vs baseline, duplicates | dashboard, prepared context, AI, par | **high** (numeric `confidence_score` on reports) | Residual ambiguity isolated to **inferred** / **unstable** fields in `contracts/sales_today.json` | **trusted** |
| `sales_by_brand_category` | What are brand/category sales levels and velocity? | `scripts/build_projection_by_category_brand.py` | `order_items_brand_category_v1` | `OrderItems` via `ORDER_ITEMS_QUERY` | `first`, `where.SoldAt` range | `data.findOrderItems` | `objectId`, `SoldAt`, `GrossPrice`, `ProductCategory.Name` | `COG`, `Product.Brand.Name` | normalized + `canonical_brand` / `canonical_category` | root, types, drift, mapping layer | dashboard, prepared context, AI, par | **high** | Brand string and category rules: see `config/brand_category_normalization.json` | **trusted** |
| `inventory_on_hand` | What inventory is currently on hand? | `scripts/projection_dashboard_to_sheet.py` (`--with-packages`) | `packages_on_hand_v1` | `Packages` via `PACKAGES_TABLE_QUERY_WITH_BRAND` | `first`, `where.createdAt` range | `data.findPackages` | `objectId`, `CurrentQty`, `Product.Name`, `Product.ProductCategory.Name` | `OriginalQty`, `Cost`, `Product.Brand.Name` | package rows + optional canonicals | root, types, drift, qty checks | dashboard, prepared context, par | **high** | `Product.Brand.Name` = **unstable**; optional economics fields **inferred** | **trusted** |
| `transfer_receipts` | What transfer receipts landed and when? | `scripts/build_transfer_receipts_db.py` | `transfer_receipts_accepted_v1` | `TransferReceiptsPaged` via `TRANSFER_RECEIPTS_PAGED_QUERY` | `first`, `where.Status`, `where.ReceivedAt` | `data.findTransfers` | `objectId`, `Status`, `ReceivedAt`, `FromName` | `Store`, `ReceivingStore`, `Packages` | header-level normalized | root, types, drift | dashboard, prepared context, AI, par | **high** | `Packages` / nested product lines = **unstable** in contract | **trusted** |
| `transfer_units` | How many package units were received and at what cost? | `scripts/export_transfer_receipt_units.py` | `transfer_units_from_receipts_v1` | `TransferReceiptsPaged` via `TRANSFER_RECEIPTS_PAGED_QUERY` | `first`, `where.Status`, `where.ReceivedAt` | `data.findTransfers` | `objectId`, `Status`, `ReceivedAt`, `Packages` | package `Product` fields, `FromName` | line-level normalized | root, types, drift | dashboard, prepared context, par, AI | **high** | Package/product nullability tracked as **unstable** / **inferred** | **trusted** |
| `brand_profit_velocity` | Which MJ brands rank highest on profit/day + units/day? | `scripts/rank_mj_brands_profit_velocity_sheet.py` | `order_items_brand_profit_velocity_v1` (+ `products_brand_supplier_mj_v1`) | `OrderItems` + `ProductsBrandSupplierMj` | SoldAt range for order items; `first` for products | `data.findOrderItems` | `objectId`, `SoldAt`, `GrossPrice`, `Product.Brand.Name` | `COG`, `ProductCategory.Name` | normalized + canonicals | root, types, drift | sheet/dashboard, prepared context, AI | **high** | `Product.Brand.Name` **unstable**; COG/category **inferred**; supplier join experimental template | **trusted** |
| `projection_by_category_brand` | How should fixed capital be allocated by brand/category? | `scripts/build_projection_by_category_brand.py` | `order_items_projection_buy_plan_v1` | `OrderItems` via `ORDER_ITEMS_QUERY` | `first`, `where.SoldAt` range | `data.findOrderItems` | `objectId`, `SoldAt`, `GrossPrice`, `ProductCategory.Name` | `COG`, `Product.Brand.Name`, `Product.objectId` | normalized + canonicals | root, types, drift, empty fail | dashboard, prepared context, AI, par | **high** | Format buckets / line-unit model = **inferred** on top of confirmed API lines | **trusted** |
| `schema_discovery` | Which schema roots/fields are currently valid? | `scripts/run_growflow_discovery_queries.py` | `schema_discovery_runner_v1` | `discover_*.graphql` runner | none required | `data` | none | all discovery payload | passthrough | drift + errors only | validation ops and docs | **discovery** | Not promoted to trusted business metrics | **discovery** |

## Field confidence annotations (`contracts/*.json` → `field_confidence`)

Per-field tiers (not guesswork on undocumented API names beyond these tiers):

| Tier | Meaning |
| --- | --- |
| `confirmed` | Selection matches `lib/growflow_queries.py` / `transfer_receipt_export.py` and is exercised in repo scripts; types validated at gateway. |
| `inferred` | Present in query but semantics depend on business rules (COG, optional joins, mapping rules) or downstream heuristics. |
| `unstable` | Known token/schema variance (e.g. `Product.Brand` absent), nested arrays, or partner-doc-only stability. |

## Inferred / uncertain inventory (explicit)

| Metric | Inferred | Unstable |
| --- | --- | --- |
| `sales_today` | `COG`, `ProductCategory.Name` | `Product.Brand.Name` |
| `sales_by_brand_category` | `COG`, `NetPrice` (optional) | `Product.Brand.Name` |
| `inventory_on_hand` | `OriginalQty`, `Cost` | `Product.Brand.Name` |
| `transfer_receipts` | `Store.*`, `ReceivingStore.*` | `Packages` |
| `transfer_units` | nested `Packages[].Product.objectId` | `Packages`, `Packages[].Product.Brand.Name` |
| `brand_profit_velocity` | `COG`, `ProductCategory.Name` | `Product.Brand.Name` |
| `projection_by_category_brand` | `COG`, `SKU` | `Product.Brand.Name` |
| `schema_discovery` | n/a (no trusted promotion) | entire payload |

Canonical brand/category outputs use `lib/brand_category_normalize.py` + `config/brand_category_normalization.json` (exact maps = **confirmed** mapping tier; unmatched = **inferred**).

---

## Metric Detail: `sales_today`

1. Business question: current local-day sales volume and value.
2. Script: `scripts/_sales_today.py`.
3. Query/template: `order_items_sales_today_v1` using `ORDER_ITEMS_QUERY`.
4. Expected raw shape: `data.findOrderItems.edges[].node`.
5. Required fields: `objectId`, `SoldAt`, `GrossPrice`, `NetPrice`.
6. Normalization: one row per order item with id/date/gross/net.
7. Target-data proof: SoldAt dates overlap requested local-day UTC range.
8. Consumers: dashboard tiles, prepared context, AI, par.
9. Risks: no quantity field, possible Brand field fallback.
10. Trust: **trusted** at metric level; strict gateway + `confidence_score`; brand optional path **unstable**.

## Metric Detail: `sales_by_brand_category`

1. Business question: brand/category sales contribution over window.
2. Script: `scripts/build_projection_by_category_brand.py`.
3. Query/template: `order_items_brand_category_v1`.
4. Raw shape: `data.findOrderItems.edges[].node`.
5. Required fields: `objectId`, `SoldAt`, `GrossPrice`, `ProductCategory.Name`.
6. Mapping: row -> brand/category/gross/date (+ cogs when present).
7. Proof rules: required fields + date overlap + dedupe.
8. Consumers: dashboard, prepared context, AI, par.
9. Risks: string-level brand/category normalization.
10. Trust: **trusted**; canonical dimensions from normalization layer.

## Metric Detail: `inventory_on_hand`

1. Business question: how much inventory is live now.
2. Script: `scripts/projection_dashboard_to_sheet.py` package pull path.
3. Query/template: `packages_on_hand_v1`.
4. Raw shape: `data.findPackages.edges[].node`.
5. Required fields: `objectId`, `CurrentQty`, `Product.Name`, `Product.ProductCategory.Name`.
6. Mapping: package id/current qty/brand/category/cost.
7. Proof rules: non-negative qty, dedupe by package id, root/field/type checks.
8. Consumers: dashboard and par readiness checks.
9. Risks: createdAt slicing vs true on-hand scope.
10. Trust: **trusted**; createdAt caveat in contract risks; optional brand/economics **inferred**/**unstable** per `field_confidence`.

## Metric Detail: `transfer_receipts`

1. Business question: what transfer receipts were accepted and when.
2. Script: `scripts/build_transfer_receipts_db.py`.
3. Query/template: `transfer_receipts_accepted_v1`.
4. Raw shape: `data.findTransfers.edges[].node` (or paged equivalent).
5. Required fields: `objectId`, `Status`, `ReceivedAt`, `FromName`.
6. Mapping: receipt-level normalized rows with status/timestamps/source.
7. Proof rules: status filter match, date overlap, required fields.
8. Consumers: transfer DB staging, prepared context, AI/par.
9. Risks: transfer schema can drift without introspection.
10. Trust: **trusted**; cross-run fingerprint under `state/schema_fingerprints/`; `Packages` tier **unstable**.

## Metric Detail: `transfer_units`

1. Business question: package-line unit and cost on transfer receipts.
2. Script: `scripts/export_transfer_receipt_units.py`.
3. Query/template: `transfer_units_from_receipts_v1`.
4. Raw shape: transfer nodes with nested `Packages`.
5. Required fields: `objectId`, `Status`, `ReceivedAt`, `Packages`.
6. Mapping: line-level fields (`package_object_id`, `original_qty`, `cost_cents`).
7. Proof rules: required package arrays, dedupe transfer+package, date checks.
8. Consumers: landed cost and sell-through staging.
9. Risks: null `Product`/package attributes on some lines.
10. Trust: **trusted**; nested package paths monitored for drift; null product lines remain **inferred**.

## Metric Detail: `brand_profit_velocity`

1. Business question: which MJ brands have best profit+velocity blend.
2. Script: `scripts/rank_mj_brands_profit_velocity_sheet.py`.
3. Query/template: `order_items_brand_profit_velocity_v1` and supplier query template.
4. Raw shape: `findOrderItems` lines plus `findProducts` supplier rows.
5. Required fields: `objectId`, `SoldAt`, `GrossPrice`, `Product.Brand.Name`.
6. Mapping: normalized rows for brand/date/gross/cog; rank computed in script.
7. Proof rules: date overlap, required fields/types, dedupe.
8. Consumers: sheet ranking, prepared context, AI answers.
9. Risks: MJ category heuristic filter + supplier secondary query.
10. Trust: **trusted**; supplier join is experimental template; MJ filters **inferred** on top of confirmed lines.

## Metric Detail: `projection_by_category_brand`

1. Business question: where should fixed pool capital deploy.
2. Script: `scripts/build_projection_by_category_brand.py`.
3. Query/template: `order_items_projection_buy_plan_v1`.
4. Raw shape: `data.findOrderItems.edges[].node`.
5. Required fields: `objectId`, `SoldAt`, `GrossPrice`, `ProductCategory.Name`.
6. Mapping: normalized line rows, then script computes allocation and layer2 metrics.
7. Proof rules: root/field/type checks, date overlap, duplicate detection, empty fail.
8. Consumers: projection dashboard, prepared context, AI/par.
9. Risks: category heuristics and one-line-equals-one-unit model.
10. Trust: **trusted**; planner buckets **inferred**; core line economics **confirmed**.

## Metric Detail: `schema_discovery`

1. Business question: what schema is currently validated.
2. Script: `scripts/run_growflow_discovery_queries.py`.
3. Query/template: `schema_discovery_runner_v1`.
4. Raw shape: GraphQL per-discovery operation payload.
5. Required fields: none (discovery mode).
6. Mapping: passthrough discovery records.
7. Proof rules: capture errors/root presence, no trusted-output promotion.
8. Consumers: docs/contracts/template promotion workflow.
9. Risks: endpoint permissions, blocked introspection.
10. Safe today: discovery only (not trusted business output).
