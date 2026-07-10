# GrowFlow Retail GraphQL — schema map

**Doc index:** `docs/GROWFLOW_API.md` — **next data to request:** `docs/GROWFLOW_NEXT_DATA_REQUEST.md` — **discovery harness:** `scripts/run_growflow_discovery_queries.py`

**Generated:** 2026-04-04 21:26:44 UTC
**Endpoint tested:** `https://retail.growflow.com/c/nugzdispensary/graphql`

## Introspection status

Live `__schema` / `__type` introspection **failed** for this endpoint (typical for production Retail).

> Error: `GraphQL network error (Bad Request). Check GROWFLOW_GRAPHQL_URL, GROWFLOW_CONNECT_IP, or connectivity.`

**What to do:**

1. Open the **integrations** playground (`https://retail.growflow.com/c/integrations/graphql`) if GrowFlow gave you access, paste the introspection document from GraphiQL “Docs” or run this script with `GROWFLOW_GRAPHQL_URL` pointed there.
2. Or export the schema from the playground’s **schema** tab / SDL and commit a redacted fragment under `docs/` if policy allows.
3. Until then, treat field names in **sample** queries below as **hypotheses** — confirm each selection in the playground for your org.

---

## Implemented in this repo (exact queries)

These are **not guessed** — they ship in `lib/growflow_queries.py` and power the buy planner, inventory, and BI scripts.

### `findOrderItems` (with `Product.Brand`)

```graphql
query OrderItems($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        SKU
        OriginId
        Package { objectId }
        ProductCategory { Name }
        Product {
          objectId
          Name
          SKU
          createdAt
          Brand { Name }
        }
        NetWeight
        NetWeightUOM
        UnitWeight
        UnitWeightUOM
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
```

### `findOrderItems` (no Brand — schema fallback)

```graphql
query OrderItems($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        SKU
        OriginId
        Package { objectId }
        ProductCategory { Name }
        Product {
          objectId
          Name
          SKU
          createdAt
        }
        NetWeight
        NetWeightUOM
        UnitWeight
        UnitWeightUOM
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
```

### `findPackages`

```graphql
query Packages($first: Int, $after: String, $where: PackagesWhereInput) {
  findPackages(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        id
        createdAt
        OriginalQty
        CurrentQty
        Cost
        SKU
        Product {
          SKU
          Name
          ProductCategory { Name }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
```

### Package line quantities: `OriginalQty` vs `CurrentQty` (`findPackages`)

These are **different fields on the same package row**. Do not interchange them when reporting inventory.

| Field | Meaning | Typical use in this repo |
| --- | --- | --- |
| **`OriginalQty`** | Quantity on the package **when it was created / first received** (original batch size for that line). | Intake sizing, landed-cost math with `Cost`, transfer receipt history, “how big was this lot.” |
| **`CurrentQty`** | **Live remaining quantity** on that line after sales, adjustments, splits, transfers, etc. | **On-hand inventory**, sell-through, “what we have **now**.” |

**UI / exports:** A column labeled “Items” (or similar) may reflect **original** package quantity, **current** quantity, or another scope (location, sellable subset). When reconciling numbers to the API, confirm which field the screen uses. Scripts that answer “how much do we have in inventory?” must sum **`CurrentQty`** (usually with `CurrentQty > 0`), not `OriginalQty`.

### `findPackages` (with `Product.Brand`)

```graphql
query Packages($first: Int, $after: String, $where: PackagesWhereInput) {
  findPackages(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        id
        createdAt
        OriginalQty
        CurrentQty
        Cost
        SKU
        Product {
          SKU
          Name
          ProductCategory { Name }
          Brand { Name }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
```

### Order line ↔ inventory package

| Field | Use |
| --- | --- |
| **`Package.objectId`** on `OrderItems` | Join to **`Packages.objectId`** on a transfer receipt for cohort sell-through (`scripts/transfer_cohort_sellthrough.py`). |
| **`OriginId`** on `OrderItems` | Compliance / source tag (e.g. Metrc-style `1A40E…`); **not** the Retail package `objectId`. |

### Menu / out-the-door pricing (tax-inclusive shelf)

Nugz menu prices are **tax-inclusive** (flat OTD on the shelf). **`GrossPrice` alone is not the menu price.**

| Field | Type | Meaning (validated 2026-06) |
| --- | --- | --- |
| **`findProducts.SalesPrice`** | cents | Catalog **menu OTD** (7pk = 3700 → **$37**, 5pk = **$42**, blunt = **$18**, singles **$9–$12**) |
| **`OrderItems.OriginalPrice`** | cents | Menu OTD at sale time; matches **`Product.SalesPrice`** on standard rings |
| **`OrderItems.GrossPrice`** | cents | **Pre-tax** portion rung on the line (e.g. 7pk ≈ **$31.62**) |
| **`OrderItems.Price`** | cents | Pre-tax charge after promos; can be below menu-derived pre-tax |
| **`OrderItems.Taxes`** | `Element.value` JSON | Per-line taxes; use **`taxAmount`** (see `lib/growflow_line_pricing.py`) |
| **Customer OTD collected** | derived | **`GrossPrice` + sum(`taxAmount`)** ≈ menu when no discount |

**Repo helpers:** `lib/growflow_line_pricing.py` — `menu_price_cents()`, `collected_otd_cents()`, `line_tax_cents()`.

**Probe script:** `PYTHONPATH=. python scripts/probe_growflow_retail_price_fields.py`

**Do not use for menu OTD:** `GrossPrice` alone, `NetPrice` (different slice; not shelf OTD).

---

## Priority queries to confirm in playground (not introspected here)

| Query | Planner use | Sample shape (validate fields!) |
| --- | --- | --- |
| `findProducts` | SKU / product identity, brand+category linkage | `findProducts(first: 5) { edges { node { objectId Name SKU } } pageInfo { hasNextPage } }` |
| `findBrands` | Normalize brand dimension | `findBrands(first: 50) { edges { node { objectId Name } } }` |
| `findProductCategories` | Replace inferred categories | `findProductCategories(first: 100) { edges { node { objectId Name } } }` |
| `findOrders` | Order header + nested lines | `Items` is an array union: use `Items { ... on OrderItems { objectId SoldAt GrossPrice OriginId Product { objectId Name Brand { Name } } } }` (see `FIND_ORDERS_ORDER_ITEMS_SAMPLE` in `lib/growflow_queries.py`). No line `Quantity` field here either. |
| `findTransfers` | Inter-store movement vs sales | `findTransfers(first: 20) { edges { node { objectId } } }` — *expand node fields from docs*. **Cartel infused 7×1.2g multipack (8.4g) on transfer lines:** see **`docs/GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md`** (`Product.Brand.Name` + `Product.Name` signifiers; some rows may have `Product: null`). |
| `findTransactions` | Tender vs order-total checks | `findTransactions(first: 20) { edges { node { objectId } } }` — *expand from docs* |
| `findStores` | Multi-store scope | `findStores(first: 20) { edges { node { objectId name } } }` |
| `preorderStatus` | Preorder flow | `query { preorderStatus(orderId: "…") { order { id status orderNumber } } }` |
| `findMenus` | Partner doc sample | `findMenus(menuKey: "…") { menuGroups { name products { name sku } } }` |

Connection pattern is usually `edges { node { … } }`, `pageInfo { hasNextPage endCursor }`, and `count` — match your live schema.

---

## Re-run introspection when allowed

```bash
PYTHONPATH=. python scripts/introspect_growflow_schema.py --write-docs \
  --growflow-credentials E:/secrets/gcp/growflowapi.txt
# Optional: integrations sandbox
# set GROWFLOW_GRAPHQL_URL=https://retail.growflow.com/c/integrations/graphql
```

Successful runs write `data/growflow_schema_introspection.json` (gitignored) and replace this file’s introspected tables when `--write-docs` is used with a working endpoint.
