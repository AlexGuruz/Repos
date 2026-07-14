# GrowFlow API Field Registry — Retail Dashboard

Source: live probes (`scripts/probe_retail_dashboard_fields.py`, `data/retail_dashboard_probe.json`).

## Order lines (`findOrderItems`)

| Field | Status | Notes |
|-------|--------|-------|
| `objectId` | confirmed | Line PK |
| `SoldAt` | confirmed | UTC ISO; filter via `OrderItemsWhereInput.SoldAt` |
| `GrossPrice`, `NetPrice`, `Price`, `OriginalPrice` | confirmed | Cents |
| `COG` | confirmed | Native COG cents |
| `Taxes { ... on Element { value } }` | confirmed | Used by `growflow_line_pricing` |
| `Store { objectId Name }` | confirmed | Line-level store |
| `Product { objectId Name SKU SalesPrice Brand ProductCategory }` | confirmed | Catalog join |
| `ProductCategory { Name }` | confirmed | Line-level category fallback |
| `Package { objectId }` | confirmed | Package link |
| `Orders { ... on Orders { ... } }` | confirmed | **Required** for budtender + order economics |

### Orders union fragment (on line)

| Field | Status | Notes |
|-------|--------|-------|
| `objectId` | confirmed | Order PK |
| `User { objectId username FullName }` | confirmed | **Budtender** — use `FullName`, not firstName/lastName |
| `Total`, `Subtotal`, `Discounts` | confirmed | Order-level cents |
| `Type`, `Status` | confirmed | Returns detection |
| `PreOrderType` | confirmed | **Channel proxy**: null → in-store; non-null → online |
| `CompletedAt` | confirmed | Order completion time |
| `Store { objectId Name }` | confirmed | Order-level store |

### Not available on lines

| Field | Status |
|-------|--------|
| `Order` (singular nested) | **failed** — use `Orders` union |
| `Channel`, `IsOnline`, `Source` | **failed** |
| `findUsers` root | **permission denied** |

## Orders root (`findOrders`)

Same scalar + `User` / `Store` fields as union fragment. Useful for returns probes without line detail.

## Dimensions

| Operation | Status |
|-----------|--------|
| `findStores` | confirmed |
| `findProducts` | confirmed |
| `findBrands` | confirmed |
| `findProductCategories` | confirmed |

## Filters

| Filter | Status |
|--------|--------|
| `OrderItemsWhereInput.Store` | confirmed |
| `OrderItemsWhereInput.store` (lowercase) | failed |

## Returns

Recent 100-order sample: all `Type=Sale`, `Status=Completed`. Negative line amounts and `Type` containing "return"/"refund" used as fallback heuristics in normalize.

## Channel

No native channel on lines. **Proxy:** `Orders.PreOrderType` → `in_store` | `online` in `lib/retail_dashboard/normalize.py`.

## Landed cost

Not from GrowFlow API directly. Join `product_landed_cost_current` from `data/transfer_receipts.db` at ingest time by `Product.objectId`.

## Query templates

| template_id | Query constant |
|-------------|----------------|
| `order_items_retail_dashboard_v1` | `ORDER_ITEMS_RETAIL_DASHBOARD_QUERY` |
| `orders_retail_dashboard_v1` | `ORDERS_RETAIL_DASHBOARD_QUERY` |
| `products_catalog_v1` | `PRODUCTS_CATALOG_QUERY` |
| `stores_v1` | `STORES_QUERY` |

Registry: `lib/growflow_query_registry.py`
