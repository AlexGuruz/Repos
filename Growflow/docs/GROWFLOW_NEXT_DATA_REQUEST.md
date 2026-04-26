# What to request from GrowFlow — schema & catalog validation

**Context:** Our production Retail endpoint returns **HTTP 400** for standard GraphQL introspection (`__schema`, `__type`). The buy planner therefore ships with `schema_validated=false` and `schema_source=fallback_docs_or_code` until we have one of the sources below.

Use this list when emailing GrowFlow / partner support (e.g. `apipartners@growflow.com`).

---

## Priority (pick one or more)

### 1. Best — SDL or full schema export

- **Ask for:** GraphQL schema SDL (or introspection JSON) for **our org’s allowed Retail operations**, redacted if needed.
- **Why:** Single artifact to diff, review in repo, and drive codegen or docs without hitting production.

### 2. Also good — introspection-enabled endpoint

- **Ask for:** Access to run **`__schema` / `__type`** against the **integrations** playground **or** a dedicated sandbox tied to our app credentials.
- **Why:** Lets `scripts/introspect_growflow_schema.py` populate `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md` automatically.

### 3. Minimum acceptable — sample queries + sample responses

For each operation, we need **one working query** and **one anonymized JSON response** (success path) so we can lock field names and nesting.

| Operation | Why we need it |
|-----------|----------------|
| **findProducts** | SKU/product identity, active flags, brand/category linkage for moving beyond brand×bucket |
| **findBrands** | Normalize brand dimension vs raw `Product.Brand` strings |
| **findProductCategories** | Replace inferred format buckets with API category truth |
| **findTransfers** | Separate internal stock movement from sell-through |
| **findTransactions** | Optional: tender vs order-line revenue reconciliation |
| **findStores** | Multi-store scope; filter order/package pulls by location if applicable |

---

## After delivery — validation checklist

1. Run `scripts/run_growflow_discovery_queries.py` (or paste each file from `scripts/growflow_discovery_queries/` into the playground) and fix any field errors using the samples.
2. Re-run `scripts/introspect_growflow_schema.py --write-docs` if introspection is enabled.
3. Update `lib/growflow_planner_metadata.py`: set `SCHEMA_VALIDATED` / `SCHEMA_SOURCE` only when the team agrees the schema is contractually validated (avoid premature `true`).
4. **Then** plan a planner grouping upgrade (product/SKU vs brand×category)—not before.

---

## References

- Partner overview: `Growflow Retail GraphQL API Documentation.txt` (repo parent / portable paths) — **not** authoritative for field-level shape.
- Implemented queries: `lib/growflow_queries.py`.
