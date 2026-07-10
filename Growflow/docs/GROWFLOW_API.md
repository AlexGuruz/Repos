# GrowFlow Retail API — documentation index (source-of-truth workflow)

**Production GraphQL is not a schema source:** `__schema` / `__type` introspection is typically **blocked** on org Retail endpoints (e.g. `nugzdispensary`). Treat the items below as the canonical references for integration and planner work—**not** guessed field names.

| Artifact | Purpose |
|----------|---------|
| [GROWFLOW_RETAIL_SCHEMA_MAP.md](./GROWFLOW_RETAIL_SCHEMA_MAP.md) | Schema map: introspected when possible, else **fallback** with exact `findOrderItems` / `findPackages` from `lib/growflow_queries.py` + playground discovery templates. Regenerate: `PYTHONPATH=. python scripts/introspect_growflow_schema.py --write-docs` |
| [GROWFLOW_PLANNER_DATA_MAPPING.md](./GROWFLOW_PLANNER_DATA_MAPPING.md) | Maps planner inputs → GraphQL queries; documents current limits vs target state. |
| [GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md](./GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md) | **Cartel infused preroll multipack (8.4g):** how to identify the SKU on **`findTransfers` packages** and **`findOrderItems`** (Cartel Oil Co + Infused Pre-Roll Bundle + 8.4G); code pointers for future runs. |
| [GROWFLOW_PLANNER_SCENARIO_CONTROLS.md](./GROWFLOW_PLANNER_SCENARIO_CONTROLS.md) | Scenario flags (`--pool`, `--velocity-days`, filters, `--compare-modes`) without new schema assumptions. |
| [GROWFLOW_NEXT_DATA_REQUEST.md](./GROWFLOW_NEXT_DATA_REQUEST.md) | Checklist of data to request from GrowFlow (SDL, integrations introspection, or sample payloads). |
| [../scripts/growflow_discovery_queries/README.md](../scripts/growflow_discovery_queries/README.md) | Minimal **test** GraphQL operations for priority `find*` roots; run when schema access exists. |
| [../lib/growflow_queries.py](../lib/growflow_queries.py) | **Implemented** production queries only: `findOrderItems`, `findPackages`. |
| [../lib/growflow_graphql.py](../lib/growflow_graphql.py) | Auth + HTTP POST to Retail GraphQL. |

**Rule for agents:** Do not extend the buy planner with new `find*` field selections until validated in the **integrations** playground, an **SDL export**, or successful runs of the discovery harness.

**Inventory lines:** On `findPackages`, **`CurrentQty`** is live on-hand; **`OriginalQty`** is the package’s opening quantity. See **“Package line quantities”** in [GROWFLOW_RETAIL_SCHEMA_MAP.md](./GROWFLOW_RETAIL_SCHEMA_MAP.md) before interpreting UI “items” counts.
